"""Simple, deterministic, contract-based answer parser.

This parser analyzes ONLY the first 20 characters of a response to extract
the selected answer letter. It does NOT perform semantic inference or scan
the full text.

Design principles:
- Deterministic and conservative
- Prefer false negatives over false positives
- No NLP libraries
- No meaning inference
"""

import re
import unicodedata
from dataclasses import dataclass
from typing import Optional


# Maximum characters to analyze from the start of the response
ANALYSIS_WINDOW = 20

# Valid answer letters
VALID_ANSWERS = {"A", "B", "C", "D", "E"}


@dataclass
class ParsedAnswer:
    """Result of parsing an LLM response.

    Attributes:
        answer: The extracted answer letter (A-E), or None if not found.
        confidence: One of 'clear', 'ambiguous', 'no_answer', 'low_confidence'.

    Confidence semantics:
        clear         – Exactly one valid alternative found in the analyzed segment.
        ambiguous     – More than one valid alternative found.
        no_answer     – No valid alternative found.
        low_confidence – Response is long/verbose; first 20 chars don't contain a clear answer.
    """

    answer: Optional[str] = None
    confidence: str = "no_answer"

    def __post_init__(self) -> None:
        """Validate confidence level."""
        valid = {"clear", "ambiguous", "no_answer", "low_confidence"}
        if self.confidence not in valid:
            raise ValueError(f"Invalid confidence level: {self.confidence}")


class AnswerParser:
    """Simple, deterministic answer parser.

    Analyzes only the first ANALYSIS_WINDOW characters of the response.
    """

    # Patterns that indicate a verbose/long response (low confidence trigger)
    VERBOSE_INDICATORS = re.compile(
        r"^(let me|vou|vamos|okay|well|hmm|so |i think|i believe|"
        r"deixe|analisando|análise|vamos ver|bom,|então,|ok,)",
        re.IGNORECASE,
    )

    def __init__(self) -> None:
        """Initialize the AnswerParser."""
        pass

    def parse(self, response_text: str) -> ParsedAnswer:
        """Parse an LLM response and extract the answer letter.

        Only the first ANALYSIS_WINDOW characters are analyzed.

        Args:
            response_text: Full text response from the LLM.

        Returns:
            ParsedAnswer with answer and confidence fields.
        """
        # Empty or whitespace-only
        if not response_text or not response_text.strip():
            return ParsedAnswer(confidence="no_answer")

        raw_segment = response_text.strip()

        # Check if response is verbose/long – triggers low_confidence
        if self._is_verbose_response(raw_segment):
            return ParsedAnswer(answer=None, confidence="low_confidence")

        # Extract the analysis window
        segment = raw_segment[:ANALYSIS_WINDOW]

        # Normalize: strip, uppercase, unicode normalize, strip simple markdown
        normalized = self._normalize(segment)

        # Find all valid answer letters in the normalized segment
        found = self._find_valid_answers(normalized)

        if len(found) == 0:
            return ParsedAnswer(answer=None, confidence="no_answer")

        if len(found) > 1:
            # Ambiguous: multiple different letters
            return ParsedAnswer(answer=found[0], confidence="ambiguous")

        # Exactly one valid alternative
        return ParsedAnswer(answer=found[0], confidence="clear")

    def _normalize(self, text: str) -> str:
        """Normalize text for pattern matching.

        Steps:
        1. Strip whitespace
        2. Uppercase
        3. Unicode NFKD normalization (strips accents)
        4. Remove simple markdown markers (*, _, ~, #, `, **)
        """
        text = text.strip()
        text = text.upper()
        text = unicodedata.normalize("NFKD", text)
        # Remove combining characters (accents)
        text = "".join(c for c in text if not unicodedata.combining(c))
        # Remove simple markdown: *, _, ~, #, `, **
        text = re.sub(r"[\*\_~#`]", "", text)
        return text

    def _find_valid_answers(self, text: str) -> list[str]:
        """Find valid answer letters in the normalized text.

        Recognized patterns:
        - Single isolated letter: A, B, C, D, E
        - Quoted letter: "A"
        - Explicit markers: ANSWER: A, \\boxed{A}
        - Simple JSON: { "ANSWER": "A" }
        - Letter followed by ) or . or :
        """
        found: list[str] = []

        # Pattern 1: \boxed{X}
        boxed = re.findall(r"\\BOXED\{([A-E])\}", text)
        found.extend(boxed)

        # Pattern 2: "ANSWER": "X" or "ANSWER":"X" (JSON-style)
        json_match = re.search(r'"ANSWER"\s*:\s*"([A-E])"', text)
        if json_match:
            found.append(json_match.group(1))

        # Pattern 3: ANSWER: X or ANSWER: "X"
        answer_marker = re.findall(r'''ANSWER\s*:\s*"?([A-E])"?''', text)
        found.extend(answer_marker)

        # Pattern 4: Quoted letter "X"
        quoted = re.findall(r'"([A-E])"', text)
        found.extend(quoted)

        # Pattern 5: Isolated letter with common delimiters: X, X), X., X:, (X)
        # Use word boundaries to find standalone A-E letters
        isolated = re.findall(r"\b([A-E])\b", text)
        found.extend(isolated)

        # Deduplicate while preserving order of first occurrence
        seen: set[str] = set()
        result: list[str] = []
        for letter in found:
            if letter not in seen:
                seen.add(letter)
                result.append(letter)

        return result

    def _is_verbose_response(self, text: str) -> bool:
        """Check if the response starts with verbose/filler language.

        Returns True if the response begins with common verbose markers,
        indicating the model is reasoning rather than giving a direct answer.
        """
        if len(text) > 200:
            return True
        return bool(self.VERBOSE_INDICATORS.match(text))


def parse_answer(response_text: str) -> ParsedAnswer:
    """Convenience function to parse an LLM response.

    Args:
        response_text: Full text response from the LLM.

    Returns:
        ParsedAnswer with answer and confidence fields.
    """
    parser = AnswerParser()
    return parser.parse(response_text)
