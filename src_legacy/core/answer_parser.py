"""Answer parser module for extracting LLM responses.

This module provides functionality to parse LLM responses and extract
the selected answer letter with confidence classification.

The parser uses a hierarchical pattern matching approach:
1. Explicit patterns (high confidence)
2. Context patterns (medium confidence)
3. Structural patterns (medium-low confidence)
4. Fallback (low confidence → requires manual review)

Pattern Hierarchy and Examples:
================================

**EXPLICIT PATTERNS (clear confidence):**
- "resposta: [A-D]" → "Resposta: B"
- "answer: [A-D]" → "Answer: C"
- "alternativa correta é [A-D]" → "A alternativa correta é D"
- "correta é [A-D]" → "A correta é A"

**CONTEXT PATTERNS (clear confidence):**
- "a resposta é [A-D]" → "A resposta é B"
- "the correct answer is [A-D]" → "The correct answer is C"
- "opção [A-D]" → "A opção D"
- "letra [A-D]" → "A letra A"
- "alternativa [A-D]" → "A alternativa B"

**STRUCTURAL PATTERNS (clear confidence):**
- "**[A-D]**" → "**C**" (Markdown bold)
- "[A-D]:" at line start → "D: Explicação..."
- "[A-D])" at line start → "A) Resposta..."
- "([A-D])" at line start → "(B) Alternativa..."
- "[A-D]:" anywhere → "concluo que: A"

**FALLBACK (low_confidence → manual review):**
- Any isolated A-D letter → "Eu acho que é B"

CONFIDENCE LEVELS:
==================

- **clear**: Single match from explicit/context/structural patterns.
  Safe to use automatically without human review.

- **ambiguous**: Multiple different letters found (e.g., "A e B estão corretas").
  Requires manual review to determine correct answer.

- **no_answer**: No letter patterns found in response.
  Requires manual review (LLM may have provided explanation only).

- **low_confidence**: Only fallback pattern matched.
  Requires manual review (answer may be accidental mention).

EDGE CASES HANDLED:
===================

1. **Portuguese/Spanish articles**: "A resposta" → filters out article "A"
2. **Repeated same letter**: "A resposta é A. Definitivamente A." → clear (same letter)
3. **Multiple different letters**: "A ou B" → ambiguous
4. **Letter in explanation**: "Estudo ABC (2020)" → may be low_confidence or no_answer
5. **Markdown variations**: "**A)**", "__A__", "**a)**" → all recognized
6. **Case insensitivity**: "resposta: b" → B (uppercase)
7. **Reasoning models**: Separates reasoning text from answer when possible

Example:
    >>> parser = AnswerParser()
    >>> result = parser.parse("A resposta correta é B)")
    >>> print(result.answer)
    B
    >>> print(result.confidence)
    clear
"""

import logging
import re
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class ParsedAnswer:
    """Result of parsing an LLM response.

    Attributes:
        answer: The extracted answer letter (A, B, C, or D), or None if not found.
        confidence: Confidence level indicating if manual review is needed.
            - "clear": Single high/medium confidence match, safe to use automatically.
            - "ambiguous": Multiple different letters found, requires manual review.
            - "no_answer": No letter patterns found, requires manual review.
            - "low_confidence": Only fallback pattern matched, requires manual review.
        raw_matches: List of all letter matches found in the response text.
        reasoning_text: Extracted reasoning text if present (optional).

    Example:
        >>> result = ParsedAnswer(
        ...     answer="B",
        ...     confidence="clear",
        ...     raw_matches=["B"],
        ...     reasoning_text="A alternativa B está correta porque..."
        ... )
    """

    answer: Optional[str] = None
    confidence: str = "no_answer"
    raw_matches: list[str] = field(default_factory=list)
    reasoning_text: Optional[str] = None

    def __post_init__(self) -> None:
        """Validate confidence level."""
        valid_confidence = {"clear", "ambiguous", "no_answer", "low_confidence"}
        if self.confidence not in valid_confidence:
            raise ValueError(f"Invalid confidence level: {self.confidence}")
        if self.confidence == "clear" and self.answer is None:
            raise ValueError("Clear confidence requires a valid answer")


class AnswerParser:
    """Parser for extracting answer letters from LLM responses.

    This class implements a hierarchical pattern matching strategy
    to extract answer letters (A, B, C, D) from LLM response text.

    Pattern Hierarchy:
        1. **Explicit Patterns** (high confidence):
           - "resposta: [A-D]"
           - "answer is: [A-D]"
           - "alternativa correta: [A-D]"

        2. **Context Patterns** (medium confidence):
           - "a resposta correta é [A-D]"
           - "the correct answer is [A-D]"
           - "opção [A-D]"
           - "letra [A-D]"

        3. **Structural Patterns** (medium-low confidence):
           - "[A-D]:" at line start
           - "[A-D])" at line start
           - "**[A-D]**" (markdown bold)

        4. **Fallback** (low confidence → manual review):
           - First occurrence of [A-D] as isolated word

    Confidence Classification:
        - **clear**: Single match from explicit/context/structural patterns
        - **ambiguous**: Multiple different letters found
        - **no_answer**: No patterns matched
        - **low_confidence**: Only fallback pattern matched

    Example:
        >>> parser = AnswerParser()
        >>> result = parser.parse("A resposta correta é B)")
        >>> assert result.answer == "B"
        >>> assert result.confidence == "clear"
    """

    # Pattern definitions with confidence levels
    # Each tuple: (pattern, has_group, confidence_if_matched)
    EXPLICIT_PATTERNS = [
        (r"(?:resposta|answer)\s*:\s*([A-D])", True, "clear"),
        (r"(?:alternativa\s+)?correta\s*(?:é|is)\s*([A-D])", True, "clear"),
    ]

    CONTEXT_PATTERNS = [
        (r"a\s+resposta\s+(?:correta\s+)?(?:é|is)\s*([A-D])", True, "clear"),
        (r"the\s+correct\s+answer\s+(?:is)?\s*([A-D])", True, "clear"),
        (r"(?:opção|option)\s*([A-D])", True, "clear"),
        (r"(?:letra|letter)\s*([A-D])", True, "clear"),
        (r"alternativa\s+([A-D])\b", True, "clear"),  # "alternativa A", "alternativa B", etc. (requires space/boundary)
    ]

    STRUCTURAL_PATTERNS = [
        (r"^\s*\*\*([A-D])\*\*", True, "clear"),  # **A**, **B**, etc.
        (r"^\s*([A-D])\s*:", True, "clear"),  # A:, B:, etc. at line start
        (r"^\s*([A-D])\s*\)", True, "clear"),  # A), B), etc. at line start
        (r"^\s*\(\s*([A-D])\s*\)", True, "clear"),  # (A), (B), etc. at line start
        (r"\b([A-D])\b\s*:", True, "clear"),  # A:, B:, etc. anywhere
        (r"\b([A-D])\b\s*\)", True, "clear"),  # A), B), etc. anywhere
    ]

    FALLBACK_PATTERN = r"\b([A-D])\b"  # Any isolated A-D letter

    def __init__(self) -> None:
        """Initialize the AnswerParser."""
        self._compile_patterns()

    def _compile_patterns(self) -> None:
        """Compile all regex patterns for efficiency."""
        self._explicit_regex = [
            (re.compile(pattern, re.IGNORECASE | re.MULTILINE), has_group, conf)
            for pattern, has_group, conf in self.EXPLICIT_PATTERNS
        ]
        self._context_regex = [
            (re.compile(pattern, re.IGNORECASE | re.MULTILINE), has_group, conf)
            for pattern, has_group, conf in self.CONTEXT_PATTERNS
        ]
        self._structural_regex = [
            (re.compile(pattern, re.IGNORECASE | re.MULTILINE), has_group, conf)
            for pattern, has_group, conf in self.STRUCTURAL_PATTERNS
        ]
        self._fallback_regex = re.compile(self.FALLBACK_PATTERN, re.IGNORECASE)

    def parse(self, response_text: str) -> ParsedAnswer:
        """Parse an LLM response and extract the answer letter.

        This method applies the hierarchical pattern matching strategy
        to extract the answer letter and classify confidence.

        Args:
            response_text: Full text response from the LLM.

        Returns:
            ParsedAnswer object containing:
            - answer: Extracted letter (A, B, C, D) or None
            - confidence: "clear", "ambiguous", "no_answer", or "low_confidence"
            - raw_matches: All letter matches found
            - reasoning_text: Extracted reasoning if present

        Example:
            >>> parser = AnswerParser()
            >>> result = parser.parse("A resposta correta é B)")
            >>> print(result.answer)
            B
            >>> print(result.confidence)
            clear
        """
        if not response_text or not response_text.strip():
            logger.debug("Empty response text")
            return ParsedAnswer(confidence="no_answer")

        response_text = response_text.strip()

        # Step 1: Find all letter matches for ambiguity detection
        all_matches = self._find_all_matches(response_text)
        
        # Filter out false positive articles (e.g., "A resposta")
        filtered_matches = self._filter_ambiguous_articles(response_text, all_matches)
        logger.debug(f"All letter matches: {all_matches}, filtered: {filtered_matches}")

        # Step 2: Check for ambiguity (multiple different letters)
        unique_letters = set(m for m in filtered_matches if m in ("A", "B", "C", "D"))
        if len(unique_letters) > 1:
            logger.debug(f"Ambiguous response: multiple letters {unique_letters}")
            return ParsedAnswer(
                answer=None,
                confidence="ambiguous",
                raw_matches=filtered_matches,
            )

        # Step 3: Try patterns by priority
        # Try explicit patterns
        for pattern, has_group, confidence in self._explicit_regex:
            match = pattern.search(response_text)
            if match:
                letter = self._extract_match(match, has_group)
                if letter and letter in ("A", "B", "C", "D"):
                    logger.debug(f"Matched explicit pattern: {pattern.pattern}")
                    return ParsedAnswer(
                        answer=letter,
                        confidence=confidence,
                        raw_matches=filtered_matches,
                    )

        # Try context patterns
        for pattern, has_group, confidence in self._context_regex:
            match = pattern.search(response_text)
            if match:
                letter = self._extract_match(match, has_group)
                if letter and letter in ("A", "B", "C", "D"):
                    logger.debug(f"Matched context pattern: {pattern.pattern}")
                    return ParsedAnswer(
                        answer=letter,
                        confidence=confidence,
                        raw_matches=filtered_matches,
                    )

        # Try structural patterns
        for pattern, has_group, confidence in self._structural_regex:
            match = pattern.search(response_text)
            if match:
                letter = self._extract_match(match, has_group)
                if letter and letter in ("A", "B", "C", "D"):
                    logger.debug(f"Matched structural pattern: {pattern.pattern}")
                    return ParsedAnswer(
                        answer=letter,
                        confidence=confidence,
                        raw_matches=filtered_matches,
                    )

        # Step 4: Fallback - use first filtered match if available
        if filtered_matches:
            letter = filtered_matches[0]
            if letter in ("A", "B", "C", "D"):
                logger.debug(f"Matched fallback pattern with filtered matches")
                return ParsedAnswer(
                    answer=letter,
                    confidence="low_confidence",
                    raw_matches=filtered_matches,
                )

        # Step 5: No match found
        logger.debug(f"No answer pattern found in: {response_text[:100]}")
        return ParsedAnswer(
            answer=None,
            confidence="no_answer",
            raw_matches=filtered_matches,
        )

    def _find_all_matches(self, text: str) -> list[str]:
        """Find all letter matches in the text.

        Args:
            text: Response text to search.

        Returns:
            List of all matched letters.
        """
        matches = self._fallback_regex.findall(text)
        return [m.upper() for m in matches if m.upper() in ("A", "B", "C", "D")]

    def _filter_ambiguous_articles(self, text: str, matches: list[str]) -> list[str]:
        """Filter out false positive matches from Portuguese/Spanish articles and common words.

        The letter 'A' or 'a' as a standalone word is often a Portuguese/Spanish article
        (e.g., "A resposta", "a capital", "A alternativa"). This method filters out these
        false positives by checking context.

        Args:
            text: Original response text.
            matches: List of matched letters.

        Returns:
            Filtered list of matches excluding likely articles.
        """
        if not matches:
            return []

        # Pattern to detect 'A' or 'a' as article (followed by noun indicators)
        # Matches: "A ", "a ", "A alternativa", "a capital", "A opção", "A resposta", etc.
        article_pattern = re.compile(
            r'\b[Aa]\s+(?:alternativa|opção|opcoes|resposta|letra|questão|questao|correct|correcta|correta|melhor|mais|única|unica|primeira|segunda|terceira|última|ultima|explicação|explicacao|capital|cidade|pais|país|regiao|região|parte|maioria|unica|primeira)\b',
            re.IGNORECASE
        )

        # Find all 'A'/'a' matches that are likely articles
        article_matches = list(article_pattern.finditer(text))
        article_positions = set()
        for match in article_matches:
            # The 'A' or 'a' is at the start of the match
            article_positions.add(match.start())

        # Filter matches
        filtered = []
        for match in self._fallback_regex.finditer(text):
            letter = match.group(1).upper()
            # Only filter 'A', and only if it's at an article position
            if letter == "A" and match.start() in article_positions:
                # Skip this 'A' - it's likely an article
                logger.debug(f"Filtering out article 'A' at position {match.start()}")
                continue
            filtered.append(letter)

        return filtered

    def _extract_match(self, match: re.Match, has_group: bool) -> Optional[str]:
        """Extract the letter from a regex match.

        Args:
            match: Regex match object.
            has_group: Whether the pattern has a capture group.

        Returns:
            Extracted letter or None.
        """
        if has_group:
            return match.group(1).upper()
        return match.group(0).upper()

    def extract_reasoning_text(self, response_text: str) -> Optional[str]:
        """Extract reasoning/explanation text from the response.

        This method attempts to separate the answer from the reasoning
        by looking for common explanation markers.

        Args:
            response_text: Full response text.

        Returns:
            Reasoning text if found, None otherwise.
        """
        if not response_text:
            return None

        # Common reasoning markers
        reasoning_markers = [
            r"(?:porque|por que|pois|justificativa|explicação|razão|reason|because|why|justification|explanation):?\s*",
            r"(?:\n\n|\n)\s*(?:justificativa|explicação|razão|reasoning|explanation):?\s*",
        ]

        for marker_pattern in reasoning_markers:
            marker_match = re.search(marker_pattern, response_text, re.IGNORECASE)
            if marker_match:
                # Return text after the marker
                reasoning_start = marker_match.end()
                reasoning_text = response_text[reasoning_start:].strip()
                if reasoning_text:
                    return reasoning_text

        return None


# Convenience function for simple usage
def parse_answer(response_text: str) -> ParsedAnswer:
    """Parse an LLM response and extract the answer letter.

    Convenience function for simple usage without creating a parser instance.

    Args:
        response_text: Full text response from the LLM.

    Returns:
        ParsedAnswer object with extracted answer and confidence.

    Example:
        >>> result = parse_answer("A resposta correta é B)")
        >>> print(result.answer)
        B
        >>> print(result.confidence)
        clear
    """
    parser = AnswerParser()
    return parser.parse(response_text)
