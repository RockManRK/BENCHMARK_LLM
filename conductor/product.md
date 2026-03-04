# Initial Concept

Uma ferramenta de benchmark para avaliar a performance de LLMs em respostas a um questionário. O questionário está em formato JSON contendo 100 perguntas. 3 delas contém imagem.

---

# Product Definition

## Target Users

- **Researchers** - AI/ML researchers evaluating different LLM models
- **Developers** - Developers comparing LLMs for integration into applications

## Core Functionality

A Python-based benchmark tool that evaluates LLM performance by administering a 100-question questionnaire (including 3 image-based questions) through the OpenRouter API. The tool collects comprehensive metrics during test execution to enable deep analysis of model performance.

## Key Features

### 1. Test Configuration
- Select specific LLM models to test (supports multiple providers via OpenRouter)
- Configure number of test iterations per model (consistency testing)
- Filter questions by:
  - Question number(s)
  - Specific characteristics/categories from JSON metadata
- Randomize answer order per question (with proper letter remapping)

### 2. Data Collection (Comprehensive)

**Execution Identifiers (for reproducibility and statistical analysis)**
- `run_id` - Unique identifier for a complete test execution
- `model_id` - Identifier for the model being tested
- `iteration` - Repetition number within the same run

These fields are essential for reproducibility and statistical analysis.

**All possible metrics are captured during execution:**
- **Response Data**: Selected answer, full response text
- **Performance Metrics**: Response time/latency
- **Token Usage**: Input tokens, output tokens
- **Error Tracking**: All errors, failures, and edge cases
- **Consistency Data**: Multiple run comparisons when configured
- **Metadata**: Timestamp, model version, configuration used

### 3. Supported LLM Providers (via OpenRouter)
Primary targets:
- ChatGPT 5.2
- Gemini 3.1
- Claude 4.6 (or latest available)
- Qwen
- GLM 5
- Kimi K2.5

Plus local models running on user's network.

### 4. Multimodal Support

**Multimodal Handling Rules**
- Handle text-only questions
- Handle image-based questions (3 questions in the questionnaire)
- Proper encoding and transmission of image data to supporting models
- **If a model does not support images**, the question must be marked as "unsupported" for that model
- System must use only the image path provided in the JSON

**Randomization**
- Randomize answer order per question (with proper letter remapping)
- Global seed required: `random.seed(run_id)` for reproducibility
- Seed ensures same randomization can be reproduced across runs

### 5. Data Persistence

**Logging Separation**
- **Operational Logs** → `.log` files (progress, errors, status)
- **Experimental Data** → SQLite database (input, output, complete metrics)

**Database Requirements**
- SQLite3 database (Python native) for storing all results
- All data saved during execution (no data loss on interruption)
- Raw data stored without randomization (randomization applied only during test execution)
- Images NOT stored in database; only file paths from JSON

**Image Handling**
- System must use only the image path provided in the JSON
- No binary image storage in the database
- Image files referenced by path only

### 6. Reliability Features
- Retry logic for API failures
- Error handling and logging
- All errors stored in database for analysis
- Safe execution with recovery capabilities

### 7. Output & Reporting
- Simple statistical output (phase 1 focus)
- Foundation for future robust dashboard/analytics development

## Technical Requirements

- Python script with modular, clean, and readable functions
- `requirements.txt` with all necessary dependencies
- SQLite3 for local data persistence
- OpenRouter API integration
- Support for multimodal (text + image) inputs
- Logging to files (`.log`) for operational events
- Environment-based configuration (`.env` support)
