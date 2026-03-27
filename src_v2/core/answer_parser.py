"""Answer parser module for TO-BE architecture.

This module provides functionality to parse LLM responses and extract
the selected answer letter with confidence classification.

The parser uses a hierarchical pattern matching approach:
1. Explicit patterns (high confidence)
2. Context patterns (medium confidence)
3. Structural patterns (medium-low confidence)
4. Fallback (low confidence → requires manual review)
"""

import re
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ParsedAnswer:
    """Result of parsing an LLM response.

    Attributes:
        answer: The extracted answer letter (A, B, C, or D), or None if not found.
        confidence: Confidence level indicating if manual review is needed.
        raw_matches: List of all letter matches found in the response text.
        reasoning_text: Extracted reasoning text if present.

    Example:
        >>> result = ParsedAnswer(
        ...     answer="B",
        ...     confidence="clear",
        ...     raw_matches=["B"],
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


class AnswerParser:
    """Parser for extracting answer letters from LLM responses.

    This class implements a hierarchical pattern matching strategy
    to extract answer letters (A, B, C, D) from LLM response text.

    Example:
        >>> parser = AnswerParser()
        >>> result = parser.parse("A resposta correta é B)")
        >>> assert result.answer == "B"
        >>> assert result.confidence == "clear"
    """

    # Pattern definitions with confidence levels
    EXPLICIT_PATTERNS = [
        (r"(?:resposta|answer)\s*:\s*([A-D])", True, "clear"),
        (r"(?:alternativa\s+)?correta\s*(?:é|is)\s*([A-D])", True, "clear"),
    ]

    CONTEXT_PATTERNS = [
        (r"a\s+resposta\s+(?:correta\s+)?(?:é|is)\s*([A-D])", True, "clear"),
        (r"the\s+correct\s+answer\s+(?:is)?\s*([A-D])", True, "clear"),
        (r"(?:opção|option)\s*([A-D])", True, "clear"),
        (r"(?:letra|letter)\s*([A-D])", True, "clear"),
        (r"alternativa\s+([A-D])\b", True, "clear"),
    ]

    STRUCTURAL_PATTERNS = [
        (r"^\s*\*\*([A-D])\*\*", True, "clear"),
        (r"^\s*([A-D])\s*:", True, "clear"),
        (r"^\s*([A-D])\s*\)", True, "clear"),
        (r"^\s*\(\s*([A-D])\s*\)", True, "clear"),
        (r"\b([A-D])\b\s*:", True, "clear"),
        (r"\b([A-D])\b\s*\)", True, "clear"),
    ]

    FALLBACK_PATTERN = r"\b([A-D])\b"

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

        Args:
            response_text: Full text response from the LLM.

        Returns:
            ParsedAnswer object containing answer, confidence, and raw matches.

        Example:
            >>> parser = AnswerParser()
            >>> result = parser.parse("A resposta correta é B)")
            >>> print(result.answer)
            B
        """
        if not response_text or not response_text.strip():
            return ParsedAnswer(confidence="no_answer")

        response_text = response_text.strip()

        # Find all letter matches
        all_matches = self._find_all_matches(response_text)
        filtered_matches = self._filter_ambiguous_articles(response_text, all_matches)

        # Check for ambiguity
        unique_letters = set(m for m in filtered_matches if m in ("A", "B", "C", "D"))
        if len(unique_letters) > 1:
            return ParsedAnswer(
                answer=None,
                confidence="ambiguous",
                raw_matches=filtered_matches,
            )

        # Try patterns by priority
        for pattern, has_group, confidence in self._explicit_regex:
            match = pattern.search(response_text)
            if match:
                letter = self._extract_match(match, has_group)
                if letter and letter in ("A", "B", "C", "D"):
                    return ParsedAnswer(
                        answer=letter,
                        confidence=confidence,
                        raw_matches=filtered_matches,
                    )

        for pattern, has_group, confidence in self._context_regex:
            match = pattern.search(response_text)
            if match:
                letter = self._extract_match(match, has_group)
                if letter and letter in ("A", "B", "C", "D"):
                    return ParsedAnswer(
                        answer=letter,
                        confidence=confidence,
                        raw_matches=filtered_matches,
                    )

        for pattern, has_group, confidence in self._structural_regex:
            match = pattern.search(response_text)
            if match:
                letter = self._extract_match(match, has_group)
                if letter and letter in ("A", "B", "C", "D"):
                    return ParsedAnswer(
                        answer=letter,
                        confidence=confidence,
                        raw_matches=filtered_matches,
                    )

        # Fallback
        if filtered_matches:
            letter = filtered_matches[0]
            if letter in ("A", "B", "C", "D"):
                return ParsedAnswer(
                    answer=letter,
                    confidence="low_confidence",
                    raw_matches=filtered_matches,
                )

        return ParsedAnswer(
            answer=None,
            confidence="no_answer",
            raw_matches=filtered_matches,
        )

    def _find_all_matches(self, text: str) -> list[str]:
        """Find all letter matches in the text."""
        matches = self._fallback_regex.findall(text)
        return [m.upper() for m in matches if m.upper() in ("A", "B", "C", "D")]

    def _filter_ambiguous_articles(self, text: str, matches: list[str]) -> list[str]:
        """Filter out false positive matches from articles."""
        if not matches:
            return []

        article_pattern = re.compile(
            r'\b[Aa]\s+(?:alternativa|opção|opcoes|resposta|letra|questão|questao|correct|correcta|correta|melhor|mais|única|unica|primeira|segunda|terceira|última|ultima|explicação|explicacao|capital|cidade|pais|país|regiao|região|parte|maioria)\b',
            re.IGNORECASE
        )

        article_matches = list(article_pattern.finditer(text))
        article_positions = set(match.start() for match in article_matches)

        filtered = []
        for match in self._fallback_regex.finditer(text):
            letter = match.group(1).upper()
            if letter == "A" and match.start() in article_positions:
                continue
            filtered.append(letter)

        return filtered

    def _extract_match(self, match: re.Match, has_group: bool) -> Optional[str]:
        """Extract the letter from a regex match."""
        if has_group:
            return match.group(1).upper()
        return match.group(0).upper()
