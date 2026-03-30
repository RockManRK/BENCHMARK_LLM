"""Mode enum for CLI mode resolution."""
from enum import Enum


class Mode(Enum):
    """CLI execution mode.

    Modes are mutually exclusive and determine what operation is being performed:
    - CREATE: Creating new entities (experiments)
    - MODIFY: Modifying existing entities (adding models, questions, runs)
    - EXECUTE: Running benchmarks
    - EXPORT: Exporting benchmark results (read-only)
    - INVALID: No valid mode flags detected (invalid/empty input)
    """
    CREATE = "create"
    MODIFY = "modify"
    EXECUTE = "execute"
    EXPORT = "export"
    INVALID = "invalid"
