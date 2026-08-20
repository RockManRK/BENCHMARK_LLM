"""Central console presentation layer for the bcllm CLI.

Foundation only (CLI Typer migration Fase 2 — see
docs/architecture/adr/adr-002-cli-presentation.md). No command is wired
to this layer yet; importing this package must have zero side effects
(no output, no DB connection, no logging reconfiguration) — see
docs/contracts/interaction-contracts.md Section 2.
"""
