# V2 Image/Vision Support Implementation Plan

**Document Type:** Implementation Design  
**Project:** Benchmark LLM V2  
**Version:** 1.0  
**Date:** 2026-04-03  
**Status:** Draft for Review  

---

## Executive Summary

This document defines the implementation plan for adding image/vision support to the V2 execution system. The system must detect questions with images, extract image paths from question snapshots, encode images as base64 data URLs, and send them to vision-capable models via the OpenRouter API following the multimodal message format specified in the OpenRouter documentation.

**Key Principle:** Unlike V1, where the `vision_enabled` flag was cosmetic and images were sent regardless of variant configuration, V2 will enforce strict vision gating: images are ONLY sent if the model variant explicitly has `enable_vision=True`.

---

## 1. V1 Legacy Analysis

### 1.1 How V1 Handled Images

**Flow in V1:**
```
Question JSON (has_image + assets[]) 
  → Loader extracts has_image + image_path 
  → Snapshot serializes both fields into question_payload
  → Planner passes question_payload to ExecutionEngine
  → ExecutionEngine checks: payload.get("has_image") AND payload.get("image_path")
  → If both truthy AND file exists:
      → MessageBuilder.build_multimodal_message(prompt, image_path)
  → Else:
      → MessageBuilder.build_user_message(prompt)
```

**V1 Message Format (in `src_legacy/api/client.py` lines 50-104):**
```python
{
    "role": "user",
    "content": [
        {"type": "text", "text": prompt},
        {"type": "image_url", "image_url": {"url": data_url}},
    ],
}
```
Where `data_url = f"data:{mime_type};base64,{base64_image}"`

### 1.2 V1 Critical Bugs (MUST NOT be replicated)

| Bug | Description | Impact | V2 Fix |
|-----|-------------|--------|--------|
| **Bug 1** | `vision_enabled` flag was cosmetic - never checked in ExecutionEngine | Text-only models received images | V2 MUST check `model_config.enable_vision` before building multimodal messages |
| **Bug 2** | `ImageHandler` (341 lines) was dead code | Maintenance burden, confusion | V2 will use inline encoding in MessageBuilder (simpler, proven approach) |
| **Bug 3** | `ModelCapabilityChecker` was dead code | Text-only models could receive images | V2 will log warning if vision variant processes question with images but model is not vision-capable |
| **Bug 4** | Silent fallback to text-only if image file missing | Incomplete data sent to model, result still marked success | V2 will mark item as FAILURE if image is missing and vision is enabled |
| **Bug 5** | Inline imports in ExecutionEngine (`from pathlib import Path`) | Hidden dependencies | V2 will use top-level imports |

---

## 2. OpenRouter API Specification

Based on `docs/Manuais_Diversos/openrouterdocs/image_inputs.md`:

### 2.1 Multimodal Message Format

```json
{
  "model": "google/gemini-3-flash-preview",
  "messages": [
    {
      "role": "user",
      "content": [
        {
          "type": "text",
          "text": "What's in this image?"
        },
        {
          "type": "image_url",
          "image_url": {
            "url": "https://example.com/image.jpg"
          }
        }
      ]
    }
  ]
}
```

### 2.2 Supported Image Formats

- `image/png`
- `image/jpeg` (including `.jpg`)
- `image/webp`
- `image/gif`

### 2.3 Image Encoding Options

**Option A: Direct URLs** (preferred for publicly accessible images)
- More efficient (no local encoding required)
- Used when image is accessible via URL

**Option B: Base64-encoded data URLs** (required for local/private images)
- Format: `data:image/jpeg;base64,{base64_string}`
- Used when image is stored locally (our case)

**Our System Uses:** Base64-encoded data URLs (images stored locally in `data/assets/`)

### 2.4 OpenRouter Recommendation

> "Due to how the content is parsed, we recommend sending the text prompt first, then the images. If the images must come first, we recommend putting it in the system prompt."

**V2 Implementation:** Text FIRST, then images (following OpenRouter recommendation)

---

## 3. V2 Current State Analysis

### 3.1 What Already Exists ✅

| Component | Status | Details |
|-----------|--------|---------|
| `ModelConfig.enable_vision` | ✅ Exists | Field in `src/core/execution_plan.py` line 194 |
| CLI `--vision` flag | ✅ Exists | In `src/cli/bcllm_experiment.py` and `src/cli/bcllm_model.py` |
| Config resolution | ✅ Exists | `MODEL_VISION` resolved in `src/core/config_resolver.py` |
| Planner vision flag | ✅ Exists | Passed to `ModelConfig` in `src/core/planner.py` line 529 |

### 3.2 What's Missing ❌

| Component | Status | Impact |
|-----------|--------|--------|
| `QuestionPayload.has_image` field | ❌ Missing | Dataclass doesn't expose the field (data already exists in snapshot JSON) |
| `QuestionPayload.image_path` field | ❌ Missing | Dataclass doesn't expose the field (data already exists in snapshot JSON) |
| `MessageBuilder` class | ❌ Missing | No utility to build multimodal messages |
| Vision gating in ExecutionEngine | ❌ Missing | Images not sent even if variant has `enable_vision=True` |
| Image encoding logic | ❌ Missing | No base64 encoding in V2 |
| Missing image error handling | ❌ Missing | No graceful failure for missing images |

**Important Note:** The `has_image` and `image_path` data **already exist** in the `question_snapshots.question_payload` JSON column. For example, question Q005 contains:
```json
{
  "meta": {
    "has_table": false,
    "has_image": true,
    "status": "valid",
    "notes": ""
  },
  "assets": ["data/assets/image_Q005.png"]
}
```

The issue is that `QuestionPayload` dataclass doesn't have fields to **expose** this data to the ExecutionEngine. The Planner needs to extract these fields from the snapshot JSON and populate them into the `QuestionPayload` instance.

---

## 4. Implementation Design

### 4.1 Data Model Changes

#### 4.1.1 Extend `QuestionPayload` Dataclass

**File:** `src/core/execution_plan.py`

**Current:**
```python
@dataclass(frozen=True)
class QuestionPayload:
    stem: str
    options: list[str]
    answer_key: str
```

**Proposed:**
```python
@dataclass(frozen=True)
class QuestionPayload:
    stem: str
    options: list[str]
    answer_key: str
    has_image: bool = False
    image_path: str | None = None
```

**Rationale:**
- Adds image detection capability at the data layer
- Default values ensure backward compatibility with existing text-only questions
- `image_path` is string (not `Path`) to maintain serializability in ExecutionPlan

---

### 4.2 Message Builder Component

#### 4.2.1 Create `MessageBuilder` Class

**File:** `src/api/message_builder.py` (NEW)

**Purpose:** Static utility class for building API messages (text-only and multimodal)

**Design:**
```python
"""Message builder for OpenRouter API messages.

This module provides static methods to construct properly formatted
messages for the OpenRouter chat completion API, supporting both
text-only and multimodal (text + image) content.

Following OpenRouter specification:
- Text content comes FIRST in the content array
- Images come AFTER text (per OpenRouter recommendation)
- Images are base64-encoded as data URLs
"""

from __future__ import annotations

import base64
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Supported image formats and their MIME types
SUPPORTED_IMAGE_FORMATS: dict[str, str] = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
}


class MessageBuilder:
    """Utility class for building API messages.
    
    This class provides static methods to construct properly formatted
    messages for the OpenRouter chat completion API, supporting both
    text-only and multimodal content.
    
    Example:
        >>> text_message = MessageBuilder.build_user_message("Hello!")
        >>> image_message = MessageBuilder.build_multimodal_message(
        ...     text="What's in this image?",
        ...     image_path=Path("image.png")
        ... )
    """

    @staticmethod
    def build_user_message(content: str) -> dict[str, str]:
        """Build a text-only user message.
        
        Args:
            content: The text content of the message.
        
        Returns:
            A dictionary with 'role' and 'content' keys formatted for the API.
        
        Example:
            >>> msg = MessageBuilder.build_user_message("What is 2+2?")
            >>> msg
            {'role': 'user', 'content': 'What is 2+2?'}
        """
        return {"role": "user", "content": content}

    @staticmethod
    def build_multimodal_message(text: str, image_path: Path) -> dict[str, Any]:
        """Build a multimodal user message with text and image.
        
        Creates a message with both text and image content, encoding
        the image as base64 data URL for API transmission.
        
        Following OpenRouter recommendation:
        - Text comes FIRST in the content array
        - Images come AFTER text
        
        Args:
            text: The text content of the message.
            image_path: Path to the image file to include.
        
        Returns:
            A dictionary with 'role' and 'content' keys, where content
            is a list containing text and image_url objects.
        
        Raises:
            FileNotFoundError: If the image file does not exist.
            ValueError: If the image format is not supported.
        
        Example:
            >>> msg = MessageBuilder.build_multimodal_message(
            ...     text="Describe this image",
            ...     image_path=Path("chest_xray.png")
            ... )
        """
        if not image_path.exists():
            logger.error(f"Image file not found: {image_path}")
            raise FileNotFoundError(f"Image file not found: {image_path}")

        # Read and encode image
        image_data = image_path.read_bytes()

        # Determine image format
        suffix = image_path.suffix.lower()
        
        if suffix not in SUPPORTED_IMAGE_FORMATS:
            logger.error(f"Unsupported image format: {suffix}")
            raise ValueError(
                f"Unsupported image format: {suffix}. "
                f"Supported formats: {list(SUPPORTED_IMAGE_FORMATS.keys())}"
            )

        mime_type = SUPPORTED_IMAGE_FORMATS[suffix]
        base64_image = base64.b64encode(image_data).decode("utf-8")
        data_url = f"data:{mime_type};base64,{base64_image}"

        # Per OpenRouter recommendation: text FIRST, then images
        return {
            "role": "user",
            "content": [
                {"type": "text", "text": text},
                {"type": "image_url", "image_url": {"url": data_url}},
            ],
        }
```

**Key Design Decisions:**
1. **Static methods only** - No state, pure utility
2. **Raises exceptions** on failure (not silent fallback) - Allows ExecutionEngine to handle errors explicitly
3. **Text FIRST** - Follows OpenRouter recommendation for better parsing
4. **Format validation** - Prevents unsupported image types from being sent
5. **No ImageHandler dependency** - V1 had 341 lines of dead code; V2 uses inline encoding (simpler, proven)

---

### 4.3 Execution Engine Changes

#### 4.3.1 Add Vision Gating Logic

**File:** `src/core/execution_engine.py`

**Location:** Inside `_execute_item_async()` method, around line ~450 where messages are built

**Current Code (line ~467-473):**
```python
# Build the prompt
user_prompt = self._build_user_prompt(
    item.question_payload.stem,
    options,
    run.prompts_effective.user,
)

# Build messages - filter out None content (system-default means "do not send")
messages = []
if run.prompts_effective.system is not None:
    messages.append({"role": "system", "content": run.prompts_effective.system})
if user_prompt is not None:
    messages.append({"role": "user", "content": user_prompt})
```

**Proposed Replacement:**
```python
# Build user message (text-only or multimodal based on vision config)
user_message = self._build_user_message_for_item(
    item=item,
    options=options,
    user_prompt_template=run.prompts_effective.user,
    model_config=variant.model_config_effective,
)

# Build messages - filter out None content (system-default means "do not send")
messages = []
if run.prompts_effective.system is not None:
    messages.append({"role": "system", "content": run.prompts_effective.system})
if user_message is not None:
    messages.append(user_message)
```

#### 4.3.2 Add `_build_user_message_for_item()` Method

**New method in `ExecutionEngine` class:**

```python
def _build_user_message_for_item(
    self,
    item: PlanItem,
    options: list[str],
    user_prompt_template: str,
    model_config: ModelConfig,
) -> dict[str, Any] | None:
    """Build user message for an item (text-only or multimodal).
    
    This method decides whether to build a text-only or multimodal message
    based on:
    1. Whether the question has images (`has_image` and `image_path`)
    2. Whether the model variant has vision enabled (`enable_vision`)
    
    Vision Gating Logic:
    - If question has images AND variant has enable_vision=True:
        → Build multimodal message with image
        → If image file is missing: raise FileNotFoundError (item will fail)
    - If question has images BUT variant has enable_vision=False:
        → Log warning
        → Build text-only message (image omitted)
    - If question has no images:
        → Build text-only message
    
    Args:
        item: Plan item containing question payload
        options: Answer options (may be randomized)
        user_prompt_template: User prompt template from run configuration
        model_config: Model configuration including vision flag
    
    Returns:
        User message dictionary (text-only or multimodal), or None if
        user_prompt_template is None (system-default behavior)
    
    Raises:
        FileNotFoundError: If question has image, vision is enabled, but
                          image file does not exist.
    """
    from src.api.message_builder import MessageBuilder
    
    has_image = item.question_payload.has_image
    image_path_str = item.question_payload.image_path
    
    # Check if we should send images
    should_send_image = (
        has_image 
        and image_path_str is not None 
        and model_config.enable_vision
    )
    
    # Build text prompt
    text_prompt = self._build_user_prompt(
        stem=item.question_payload.stem,
        options=options,
        user_prompt_template=user_prompt_template,
    )
    
    # If text prompt is None (system-default), return None
    if text_prompt is None:
        return None
    
    # Handle image logic
    if should_send_image:
        image_path = Path(image_path_str)
        
        if not image_path.exists():
            # V2 FIX: Explicit failure instead of silent fallback
            error_msg = (
                f"Image file not found for question {item.question_id}: {image_path}. "
                f"Vision is enabled for this model variant, but the image file is missing. "
                f"This item will fail to ensure data integrity."
            )
            self._logger.error(error_msg)
            raise FileNotFoundError(error_msg)
        
        # Build multimodal message
        self._logger.info(
            f"VISION_ENABLED | question={item.question_id} | "
            f"image={image_path} | building multimodal message"
        )
        return MessageBuilder.build_multimodal_message(
            text=text_prompt,
            image_path=image_path,
        )
    
    # Question has images but vision is NOT enabled for this variant
    if has_image and image_path_str is not None:
        self._logger.warning(
            f"VISION_DISABLED | question={item.question_id} | "
            f"question has image ({image_path_str}) but model variant has "
            f"enable_vision=False. Sending text-only message (image omitted)."
        )
    
    # Build text-only message
    return MessageBuilder.build_user_message(content=text_prompt)
```

**Key Design Decisions:**
1. **Explicit failure on missing image** - V1 silently fell back to text-only, which could result in incorrect benchmarking. V2 will FAIL the item to ensure data integrity.
2. **Warning when vision disabled** - If a question has images but the variant doesn't have vision enabled, we log a warning but continue with text-only (allows text-only models to still process the question)
3. **Logging at decision points** - Every vision-related decision is logged for auditability
4. **Top-level import** - Unlike V1's inline `from pathlib import Path`, V2 uses proper module structure

---

### 4.4 Planner Changes

#### 4.4.1 Extract Image Fields from Question Snapshots

**File:** `src/core/planner.py`

**Location:** Where `QuestionPayload` is created from question snapshots

**Current Code:** Need to find where `QuestionPayload` is instantiated in the Planner

**Proposed Change:**
When building `QuestionPayload` from `question_snapshots.question_payload`, extract `has_image` and `image_path` fields from the existing snapshot JSON:

```python
# Parse question payload from snapshot
question_payload_dict = json.loads(snapshot.question_payload)

# Extract image fields from existing snapshot data
# has_image comes from meta.has_image
has_image = question_payload_dict.get("meta", {}).get("has_image", False)

# image_path comes from assets array (first asset if has_image is true)
image_path = None
if has_image and question_payload_dict.get("assets"):
    image_path = question_payload_dict["assets"][0]

# Create QuestionPayload with image support
question_payload = QuestionPayload(
    stem=question_payload_dict["stem"],
    options=question_payload_dict["options"],
    answer_key=question_payload_dict["answer_key"],
    has_image=has_image,
    image_path=image_path,
)
```

**Data Source Mapping:**
| QuestionPayload Field | Snapshot JSON Path | Example Value |
|----------------------|-------------------|---------------|
| `has_image` | `meta.has_image` | `true` |
| `image_path` | `assets[0]` (if `has_image=true`) | `"data/assets/image_Q005.png"` |

**Backward Compatibility:**
- Older snapshots may not have `meta.has_image` or `assets` fields
- Use `.get()` with defaults to handle this gracefully
- Default: `has_image=False`, `image_path=None`

---

### 4.5 Snapshot Serialization (Already Exists) ✅

**Status:** ✅ Already working correctly

When question snapshots are created, the full question JSON (including `has_image` and `assets` array) is serialized into `question_snapshots.question_payload`. 

**Example of existing data in snapshot:**
```json
{
  "stem": "Homem de 28 anos...",
  "options": {"A": "...", "B": "...", "C": "...", "D": "..."},
  "answer_key": "C",
  "meta": {
    "has_table": false,
    "has_image": true,
    "status": "valid",
    "notes": ""
  },
  "assets": ["data/assets/image_Q005.png"]
}
```

**What needs to happen:** The Planner needs to **extract** these fields when reading the snapshot:
- `has_image` → from `meta.has_image`
- `image_path` → from `assets[0]` (first asset, if `has_image` is true)

**No migration needed** - existing snapshots already contain the required data.

---

## 5. Implementation Phases

### Phase 1: Data Model & Message Builder (Structural)
**Complexity:** Simple  
**Agent:** `coder`

**Tasks:**
1. Extend `QuestionPayload` dataclass with `has_image` and `image_path` fields
2. Create `MessageBuilder` class in `src/api/message_builder.py`
3. Add unit tests for `MessageBuilder`:
   - Test text-only message building
   - Test multimodal message building with valid image
   - Test FileNotFoundError for missing image
   - Test ValueError for unsupported image format
   - Test all supported image formats (PNG, JPG, JPEG, GIF, WEBP)

**Validation:**
```bash
pytest tests/unit/api/test_message_builder.py -v
```

---

### Phase 2: Execution Engine Vision Gating (Structural)
**Complexity:** Medium  
**Agent:** `coder`

**Tasks:**
1. Add `_build_user_message_for_item()` method to `ExecutionEngine`
2. Modify `_execute_item_async()` to call new method instead of inline message building
3. Add comprehensive logging for vision decisions
4. Add unit tests for vision gating:
   - Test: question has image + variant has vision=True → multimodal message
   - Test: question has image + variant has vision=False → text-only message + warning
   - Test: question has no image → text-only message
   - Test: question has image + variant has vision=True + image missing → FileNotFoundError

**Validation:**
```bash
pytest tests/unit/core/test_execution_engine_vision.py -v
```

---

### Phase 3: Planner Image Field Population (Structural)
**Complexity:** Simple  
**Agent:** `coder`

**Tasks:**
1. Modify Planner to extract `has_image` and `image_path` from question snapshots
2. Populate these fields when creating `QuestionPayload` instances
3. Handle backward compatibility (older snapshots without image fields)
4. Add unit tests for Planner image field extraction

**Validation:**
```bash
pytest tests/unit/core/test_planner_images.py -v
```

---

### Phase 4: Integration Testing & Validation
**Complexity:** Medium  
**Agent:** `tester`

**Tasks:**
1. Create integration test with real question that has image (e.g., Q005 from `data/enamed_questions.json`)
2. Test execution with vision-enabled model variant
3. Test execution with vision-disabled model variant
4. Verify API request payload contains correct multimodal format
5. Verify logs contain vision decision information
6. Test error handling for missing image file

**Validation:**
```bash
pytest tests/integration/test_vision_execution.py -v
```

---

### Phase 5: Code Review
**Complexity:** Simple  
**Agent:** `code_reviewer`

**Tasks:**
1. Review all changes for correctness
2. Check for security vulnerabilities (path traversal, file access)
3. Verify adherence to V2 architectural contracts
4. Ensure no V1 bugs were replicated
5. Check code quality and edge case handling

---

### Phase 6: Essence Guardian Validation
**Complexity:** Simple  
**Agent:** `essence-guardian`

**Tasks:**
1. Verify changes respect V2 fundamental contracts
2. Check for conceptual drift
3. Validate architectural consistency
4. Ensure determinism and idempotency are maintained

---

## 6. Error Handling Strategy

### 6.1 Missing Image File

**V1 Behavior:** Silent fallback to text-only, item marked as success  
**V2 Behavior:** Item marked as FAILURE with clear error message

**Rationale:** If vision is enabled and the image is missing, the benchmark data would be incomplete/incorrect. Better to fail explicitly than produce invalid data.

**Error Message:**
```
Image file not found for question Q005: data/assets/image_Q005.png. 
Vision is enabled for this model variant, but the image file is missing. 
This item will fail to ensure data integrity.
```

### 6.2 Unsupported Image Format

**Behavior:** Item marked as FAILURE

**Error Message:**
```
Unsupported image format: .bmp for question Q005. Supported formats: ['.png', '.jpg', '.jpeg', '.gif', '.webp']
```

### 6.3 Question Has Images But Vision Disabled

**Behavior:** Log WARNING, continue with text-only message

**Log Message:**
```
VISION_DISABLED | question=Q005 | question has image (data/assets/image_Q005.png) 
but model variant has enable_vision=False. Sending text-only message (image omitted).
```

**Rationale:** This is a valid scenario - user may want to test text-only performance on questions that happen to have images. The warning ensures the user is aware.

---

## 7. Testing Strategy

### 7.1 Unit Tests

**File:** `tests/unit/api/test_message_builder.py`
- `test_build_user_message_text_only`
- `test_build_multimodal_message_png`
- `test_build_multimodal_message_jpg`
- `test_build_multimodal_message_gif`
- `test_build_multimodal_message_webp`
- `test_build_multimodal_message_missing_file_raises_error`
- `test_build_multimodal_message_unsupported_format_raises_error`

**File:** `tests/unit/core/test_execution_engine_vision.py`
- `test_vision_enabled_question_has_image_builds_multimodal`
- `test_vision_disabled_question_has_image_builds_text_only_with_warning`
- `test_no_image_builds_text_only`
- `test_vision_enabled_image_missing_raises_file_not_found`

**File:** `tests/unit/core/test_planner_images.py`
- `test_planner_extracts_image_fields`
- `test_planner_handles_missing_image_fields_backward_compat`

### 7.2 Integration Tests

**File:** `tests/integration/test_vision_execution.py`
- `test_execute_question_with_image_vision_enabled`
- `test_execute_question_with_image_vision_disabled`
- `test_execute_question_without_image`
- `test_api_receives_multimodal_message_correct_format`

---

## 8. Migration & Backward Compatibility

### 8.1 Existing Question Snapshots

**Issue:** Older snapshots may not have `has_image` or `image_path` fields in `question_payload`

**Solution:** Use `.get()` with defaults when extracting fields:
```python
has_image = question_payload_dict.get("has_image", False)
image_path = question_payload_dict.get("image_path")
```

**No migration needed** - old snapshots will default to text-only behavior, which is correct.

### 8.2 Existing Model Variants

**Issue:** Existing variants may not have `enable_vision` set

**Solution:** `ModelConfig.enable_vision` already defaults to `False`, so existing variants will behave as text-only (correct behavior)

### 8.3 Existing Experiments

**Impact:** None - experiments without image questions continue to work normally

---

## 9. OpenRouter Compliance Checklist

| Requirement | Status | Implementation |
|-------------|--------|----------------|
| Content array format | ✅ Compliant | `MessageBuilder.build_multimodal_message()` |
| Text first, images after | ✅ Compliant | Per OpenRouter recommendation |
| Base64 data URL format | ✅ Compliant | `data:{mime_type};base64,{base64}` |
| Supported image formats | ✅ Compliant | PNG, JPEG, JPG, GIF, WEBP validated |
| Multiple images support | ⏭️ Deferred | Can be added later if needed |
| Model capability check | ⚠️ Warning only | V2 logs warning if vision disabled but question has image |

---

## 10. Risks & Mitigations

| Risk | Severity | Mitigation |
|------|----------|------------|
| Large images cause memory issues | Medium | Consider adding image size validation (V1 had `MAX_IMAGE_SIZE_BYTES = 10MB` in unused `ImageHandler`) |
| Base64 encoding is slow | Low | Encoding is fast for typical question images (<1MB) |
| Missing images cause test failures | High | Explicit failure with clear error message (better than silent incorrect data) |
| Backward compatibility broken | Low | Default values ensure old snapshots work correctly |
| Path traversal security issue | Medium | Validate image paths are within expected `data/assets/` directory |

---

## 11. Future Enhancements (Out of Scope)

- **Image size validation & optimization** - V1 had unused `ImageHandler.resize_image()` capability
- **Model capability checker** - V1 had unused `ModelCapabilityChecker`; could be activated to warn if model is not vision-capable
- **URL-based images** - If questions start using image URLs instead of local paths, support direct URL sending (more efficient)
- **Multiple images per question** - Current design supports single image; can be extended if dataset evolves

---

## 12. File Change Summary

| File | Action | Description |
|------|--------|-------------|
| `src/core/execution_plan.py` | Modify | Add `has_image` and `image_path` fields to `QuestionPayload` dataclass |
| `src/api/message_builder.py` | Create | New MessageBuilder class for text/multimodal messages |
| `src/core/execution_engine.py` | Modify | Add vision gating logic and `_build_user_message_for_item()` method |
| `src/core/planner.py` | Modify | Extract `has_image` from `meta.has_image` and `image_path` from `assets[0]` when creating `QuestionPayload` |
| `tests/unit/api/test_message_builder.py` | Create | Unit tests for MessageBuilder |
| `tests/unit/core/test_execution_engine_vision.py` | Create | Unit tests for vision gating |
| `tests/unit/core/test_planner_images.py` | Create | Unit tests for Planner image field extraction |
| `tests/integration/test_vision_execution.py` | Create | Integration tests for vision execution |

---

## 13. Completion Criteria

A capability is **complete** when:
- [x] CAPABILITY: Code exists and is structurally correct
- [x] ACTIVATION: Can be used with vision-enabled model variants
- [x] VALIDATION: Tests confirm correct behavior

**Validation Gates:**
1. All unit tests pass
2. All integration tests pass
3. Code review completed with no Critical/Major findings
4. Essence Guardian approved (no contract violations)
5. Manual test with real question Q005 (has image) succeeds

---

## 14. References

- V1 Legacy Analysis: `src_legacy/api/client.py` (MessageBuilder, lines 50-104)
- V1 Execution Bug: `src_legacy/core/execution_engine.py` (lines 237-249, vision flag not checked)
- OpenRouter Image Docs: `docs/Manuais_Diversos/openrouterdocs/image_inputs.md`
- V2 ModelConfig: `src/core/execution_plan.py` (line 194, `enable_vision` field)
- V2 Execution Engine: `src/core/execution_engine.py` (message building location)
- Question Dataset Example: `data/enamed_questions.json` (Q005 has image)

---

**End of Document**
