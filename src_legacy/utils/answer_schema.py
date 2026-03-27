"""JSON Schema for structured outputs in medical benchmarks.

This module defines the JSON schema used for structured outputs
when querying medical benchmark questions. The schema ensures
that model responses are properly formatted and easy to parse.
"""

ANSWER_SCHEMA = {
    "type": "json_schema",
    "json_schema": {
        "name": "resposta_médica",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "answer": {
                    "type": "string",
                    "enum": ["A", "B", "C", "D"],
                    "description": "A letra da resposta"
                }
            },
            "required": ["answer"],
            "additionalProperties": False
        }
    }
}
