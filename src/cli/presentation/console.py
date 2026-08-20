"""Central Rich Console instances for the bcllm CLI.

Two singletons, matching the stream discipline in
docs/contracts/interaction-contracts.md Section 2:

- `console` — stdout, results only.
- `error_console` — stderr, diagnostics only.

Both respect `NO_COLOR` and non-TTY output automatically (Rich's own
`Console` already checks `NO_COLOR` and `sys.stdout.isatty()`/
`sys.stderr.isatty()` — this module does not reimplement that detection,
only makes the two streams explicit and centralized so no command module
constructs its own `Console()` ad hoc).

Constructing a `Console` performs no I/O by itself — nothing is printed,
no file is opened, no environment variable is mutated. Only calling
`.print(...)` (or similar) produces output. Importing this module is
therefore side-effect-free.
"""

from __future__ import annotations

from rich.console import Console

from src.cli.presentation.theme import SEMANTIC_THEME

console = Console(theme=SEMANTIC_THEME)
"""Stdout console — results only. Never print diagnostics here."""

error_console = Console(theme=SEMANTIC_THEME, stderr=True)
"""Stderr console — diagnostics only. Never print a requested result here."""
