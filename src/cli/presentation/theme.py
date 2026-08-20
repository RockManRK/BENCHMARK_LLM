"""Minimal semantic theme for the bcllm CLI.

Fase 2 scope only: the four semantic styles that map directly to the
stdout/stderr split already normative in
docs/contracts/interaction-contracts.md Section 2 (`success`/`info` are
stdout-appropriate; `warning`/`error` are stderr-appropriate). This is
deliberately not the full visual palette (run-status colors, inherited/
system-default markers, table borders) described in the CLI migration
plan's Fase 6 — those are presentation-detail decisions with no concrete
consumer yet, and are added only once a command actually renders them.
"""

from __future__ import annotations

from rich.theme import Theme

SEMANTIC_THEME = Theme(
    {
        "success": "bold green",
        "warning": "yellow",
        "error": "bold red",
        "info": "cyan",
    }
)
