"""Question loader module for TO-BE architecture.

This module provides functionality to load, validate, and manage
question datasets from JSON files.

The QuestionLoader handles:
- Loading question datasets from JSON files
- Validating question payloads (required fields, uniqueness)
- ID mapping between source IDs (Q001) and internal numeric IDs (1..N)
- Parsing question specifications (single, range, comma-separated)

Internal numeric IDs (1..N) are the system's source of truth.
Source IDs (e.g., Q001) are preserved only as reference metadata.
"""

import json
import os
from pathlib import Path
from typing import Any


class QuestionLoader:
    """Dataset loader and validator.
    
    Loads question datasets from JSON files, validates payloads,
    and provides ID mapping between internal numeric IDs and source IDs.
    
    Internal numeric IDs (1..N) are the system's source of truth.
    Dataset-provided IDs (e.g., Q001) are preserved only as reference metadata.
    
    Example:
        >>> loader = QuestionLoader()
        >>> questions = loader.load_dataset("data/questions.json")
        >>> questions_with_ids = loader.assign_internal_ids(questions)
        >>> spec_questions = loader.parse_question_spec("Q001-Q010", questions_with_ids)
    """
    
    REQUIRED_FIELDS = ("stem", "options", "answer_key")
    
    def __init__(self) -> None:
        """Initialize the QuestionLoader."""
        pass
    
    def load_dataset(self, dataset_path: str | None = None) -> list[dict]:
        """Load question dataset from JSON file.
        
        Args:
            dataset_path: Path to JSON dataset file. If None, load from 
                          QUESTIONS_DATASET_PATH env var or default.
        
        Returns:
            List of question dictionaries from the dataset.
        
        Raises:
            FileNotFoundError: If dataset file does not exist.
            json.JSONDecodeError: If dataset is not valid JSON.
            ValueError: If dataset is not a list or is empty.
        
        Note:
            This method fails loudly — no silent fallbacks or placeholders.
        
        Example:
            >>> loader = QuestionLoader()
            >>> questions = loader.load_dataset("data/questions.json")
            >>> len(questions)
            100
        """
        resolved_path = self._resolve_dataset_path(dataset_path)
        
        path = Path(resolved_path)
        if not path.is_absolute():
            path = Path.cwd() / path
        
        if not path.exists():
            raise FileNotFoundError(f"Question dataset not found: {path}")
        
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        questions = self._extract_questions(data)
        
        if not isinstance(questions, list):
            raise ValueError("Dataset must contain a list of questions")
        
        if len(questions) == 0:
            raise ValueError("Question dataset is empty")
        
        return questions
    
    def _resolve_dataset_path(self, dataset_path: str | None) -> str:
        """Resolve dataset path from parameter or environment.
        
        Args:
            dataset_path: Explicit path, or None to use env/default.
        
        Returns:
            Resolved path string.
        """
        if dataset_path is not None:
            return dataset_path
        
        env_path = os.environ.get('QUESTIONS_DATASET_PATH')
        if env_path:
            return env_path
        
        return "data/enamed_questions.json"
    
    def _extract_questions(self, data: Any) -> list[dict]:
        """Extract questions list from dataset structure.
        
        Supports multiple dataset formats:
        - Flat list: [question1, question2, ...]
        - Wrapped: {"questions": [...]}
        - Metadata + questions: {"dataset": {...}, "questions": [...]}
        
        Args:
            data: Parsed JSON data.
        
        Returns:
            List of question dictionaries.
        
        Raises:
            ValueError: If questions cannot be extracted.
        """
        if isinstance(data, list):
            return data
        
        if isinstance(data, dict):
            if "questions" in data:
                return data["questions"]
        
        raise ValueError("Dataset format not recognized: expected list or dict with 'questions' key")
    
    def validate_payload(self, question: dict) -> bool:
        """Validate a single question payload.
        
        Args:
            question: Question dictionary to validate.
        
        Returns:
            True if question has required fields.
        
        Required Fields:
            - stem: Non-empty string (the question text)
            - options: Non-empty list (answer options)
            - answer_key: Non-empty string (correct answer)
        
        Note:
            Different questions must have different answer_key values.
            Constant answer_key across all questions indicates placeholder data.
        
        Example:
            >>> loader = QuestionLoader()
            >>> valid_question = {"stem": "What is X?", "options": ["A", "B", "C", "D"], "answer_key": "A"}
            >>> loader.validate_payload(valid_question)
            True
            >>> invalid_question = {"stem": "What is X?"}
            >>> loader.validate_payload(invalid_question)
            False
        """
        for field in self.REQUIRED_FIELDS:
            if field not in question:
                return False
            
            value = question[field]
            
            if field == "stem":
                if not isinstance(value, str) or not value.strip():
                    return False
            
            elif field == "options":
                if not isinstance(value, list) or len(value) == 0:
                    return False
            
            elif field == "answer_key":
                if not isinstance(value, str) or not value.strip():
                    return False
        
        return True
    
    def validate_answer_key_uniqueness(self, questions: list[dict]) -> bool:
        """Validate that answer keys are not all identical.
        
        Args:
            questions: List of question dictionaries.
        
        Returns:
            True if answer keys vary (not all the same).
            False if all questions have the same answer_key (placeholder data).
        
        Note:
            Constant answer_key across all questions indicates placeholder data.
        
        Example:
            >>> loader = QuestionLoader()
            >>> real_questions = [
            ...     {"stem": "Q1", "options": ["A", "B"], "answer_key": "A"},
            ...     {"stem": "Q2", "options": ["A", "B"], "answer_key": "B"},
            ... ]
            >>> loader.validate_answer_key_uniqueness(real_questions)
            True
            >>> placeholder_questions = [
            ...     {"stem": "Q1", "options": ["A", "B"], "answer_key": "B"},
            ...     {"stem": "Q2", "options": ["A", "B"], "answer_key": "B"},
            ... ]
            >>> loader.validate_answer_key_uniqueness(placeholder_questions)
            False
        """
        if len(questions) == 0:
            return True
        
        answer_keys = set()
        for q in questions:
            if "answer_key" in q:
                answer_keys.add(q["answer_key"].strip().upper())
        
        if len(answer_keys) == 0:
            return True
        
        if len(answer_keys) == 1 and len(questions) > 1:
            return False
        
        return True
    
    def get_all_question_ids(self, questions: list[dict]) -> list[str]:
        """Extract all question IDs from dataset.
        
        Args:
            questions: List of question dictionaries.
        
        Returns:
            List of source question IDs (e.g., ["Q001", "Q002", ...]).
            If questions don't have IDs, generate numeric IDs ["1", "2", ...].
        
        Example:
            >>> loader = QuestionLoader()
            >>> questions = [
            ...     {"id": "Q001", "stem": "Question 1"},
            ...     {"id": "Q002", "stem": "Question 2"},
            ... ]
            >>> loader.get_all_question_ids(questions)
            ['Q001', 'Q002']
        """
        ids = []
        for i, q in enumerate(questions, start=1):
            if "id" in q:
                ids.append(str(q["id"]))
            elif "question_id" in q:
                ids.append(str(q["question_id"]))
            else:
                ids.append(str(i))
        return ids
    
    def parse_question_spec(self, spec: str, questions: list[dict]) -> list[dict]:
        """Parse question specification string and return matching questions.

        Args:
            spec: Specification string in one of these formats:
                  - Single ID: "Q001" or "1"
                  - Comma-separated: "Q001,Q005,Q010" or "1,5,10" (spaces allowed: "1, 3, 5")
                  - Range: "Q001-Q010" or "1-10"
                  - Mixed: "Q001,Q005-Q010,15"
            questions: Full list of questions to select from.

        Returns:
            List of matching question dictionaries.

        Raises:
            ValueError: If spec format is invalid or IDs not found.

        Note:
            Supports both source IDs (Q001) and internal numeric IDs (1-50).
            Internal numeric IDs are 1-based (1..N).
            Input is normalized: whitespace is stripped, spaces after commas are handled.

        Example:
            >>> loader = QuestionLoader()
            >>> questions = [
            ...     {"internal_id": 1, "source_id": "Q001"},
            ...     {"internal_id": 2, "source_id": "Q002"},
            ...     {"internal_id": 3, "source_id": "Q003"},
            ... ]
            >>> loader.parse_question_spec("Q001,Q003", questions)
            [{'internal_id': 1, 'source_id': 'Q001'}, {'internal_id': 3, 'source_id': 'Q003'}]
        """
        import re

        question_ids = []

        normalized_spec = spec.strip()

        for part in normalized_spec.split(','):
            part = part.strip()
            if not part:
                continue

            range_match = re.match(r'^(q?)(\d+)-(q?)(\d+)$', part, re.IGNORECASE)
            if range_match:
                prefix1, start, prefix2, end = range_match.groups()
                prefix = prefix1 or prefix2
                start_num = int(start)
                end_num = int(end)

                if start_num > end_num:
                    raise ValueError(f"Invalid range: {start_num}-{end_num} (start > end)")

                for i in range(start_num, end_num + 1):
                    if prefix:
                        question_ids.append(f"Q{i:03d}")
                    else:
                        question_ids.append(str(i))
                continue

            single_match = re.match(r'^(q?)(\d+)$', part, re.IGNORECASE)
            if single_match:
                prefix, num = single_match.groups()
                if prefix:
                    question_ids.append(f"Q{int(num):03d}")
                else:
                    question_ids.append(str(int(num)))
                continue

            raise ValueError(f"Invalid question spec format: {part}")

        if not question_ids:
            raise ValueError("No valid question IDs found in spec")

        return self._select_questions_by_ids(question_ids, questions)
    
    def _select_questions_by_ids(
        self, 
        question_ids: list[str], 
        questions: list[dict]
    ) -> list[dict]:
        """Select questions by ID list.
        
        Supports both source_id (Q001) and internal_id (1, 2, 3) matching.
        
        Args:
            question_ids: List of question IDs to select.
            questions: Full list of questions to select from.
        
        Returns:
            List of matching questions.
        
        Raises:
            ValueError: If any ID is not found.
        """
        id_to_question = {}
        
        for q in questions:
            if "source_id" in q:
                id_to_question[q["source_id"]] = q
            if "id" in q:
                id_to_question[q["id"]] = q
            if "internal_id" in q:
                id_to_question[str(q["internal_id"])] = q
        
        selected = []
        missing_ids = []
        
        for qid in question_ids:
            normalized_qid = qid.upper() if qid.upper().startswith('Q') else qid
            
            if normalized_qid in id_to_question:
                selected.append(id_to_question[normalized_qid])
            elif qid in id_to_question:
                selected.append(id_to_question[qid])
            else:
                missing_ids.append(qid)
        
        if missing_ids:
            raise ValueError(f"Question IDs not found: {', '.join(missing_ids)}")
        
        return selected
    
    def assign_internal_ids(self, questions: list[dict]) -> list[dict]:
        """Assign internal numeric IDs to questions.
        
        Args:
            questions: List of question dictionaries from dataset.
        
        Returns:
            List of questions with added 'internal_id' field (1..N).
            Original 'id' or 'question_id' field preserved as 'source_id'.
        
        Example:
            >>> loader = QuestionLoader()
            >>> questions = [
            ...     {"id": "Q001", "stem": "Question 1"},
            ...     {"id": "Q002", "stem": "Question 2"},
            ... ]
            >>> result = loader.assign_internal_ids(questions)
            >>> result[0]["internal_id"]
            1
            >>> result[0]["source_id"]
            'Q001'
        """
        result = []
        
        for i, q in enumerate(questions, start=1):
            question_copy = dict(q)
            
            source_id = None
            if "id" in question_copy:
                source_id = question_copy["id"]
            elif "question_id" in question_copy:
                source_id = question_copy["question_id"]
            
            question_copy["internal_id"] = i
            
            if source_id is not None:
                question_copy["source_id"] = str(source_id)
            
            result.append(question_copy)
        
        return result
