from setuptools import setup, find_packages

setup(
    name="benchmark_llm",
    version="2.0.0",
    packages=find_packages(),
    # bcllm.py (the real CLI entry point — see QWEN.md/CLAUDE.md) lives at
    # the repo root, not inside a package `find_packages()` would pick up
    # on its own.
    py_modules=["bcllm"],
    entry_points={
        "console_scripts": [
            # Was "src.cli.bcllm_main:main" until 2026-08-18 — that
            # main() requires a `mode: Mode` positional argument
            # (src/cli/bcllm_main.py) that a console_script wrapper never
            # supplies, so the installed `bcllm` command raised
            # TypeError on every invocation. Was "bcllm:main" until the
            # Unit-of-Work checkpoint moved .env loading out of module
            # import time and into bcllm.py::cli_main() (called only from
            # a real entry point, never from a bare import) — pointing
            # here at plain `main()` would have silently skipped .env
            # loading entirely for the installed console script.
            # bcllm.py::cli_main() is the one place both real entry
            # points (this, and `python bcllm.py`'s own
            # `if __name__ == "__main__"` block) share. See
            # docs/status/composite-flow-unit-of-work-design.md and
            # docs/status/known-issues.md.
            "bcllm=bcllm:cli_main",
        ],
    },
    install_requires=[
        "httpx>=0.25.0",
        "pydantic>=2.0.0",
        "pydantic-settings>=2.0.0",
        "Pillow>=10.0.0",
        "python-dotenv>=1.0.0",
        "rich>=13.0.0",
        "typer>=0.27.1",
    ],
    python_requires=">=3.10",
)
