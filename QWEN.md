# Benchmark LLM - Project Context

## Project Overview

**Benchmark LLM** is a Python-based benchmark tool for evaluating Large Language Model (LLM) performance by administering a 100-question medical questionnaire through the OpenRouter API. The tool enables researchers and developers to test multiple LLM models against a standardized questionnaire, configure test iterations for consistency analysis, and collect comprehensive metrics stored in SQLite for analysis.

### Core Purpose
- Evaluate and compare LLM models via OpenRouter's unified API
- Support both text-only and image-based questions (3 image questions in the questionnaire)
- Collect comprehensive metrics: response time, token usage, accuracy, error tracking
- Enable reproducibility through random seed configuration
- Store all experimental data in SQLite with operational logs in `.log` files

### Target Users
- **Researchers**: AI/ML researchers evaluating different LLM models
- **Developers**: Developers comparing LLMs for integration into applications

## Project Structure

```
benchmark_llm/
├── src/
│   ├── __init__.py
│   ├── main.py                 # Main entry point, BenchmarkRunner orchestrator
│   ├── api/                    # OpenRouter API integration
│   │   ├── __init__.py
│   │   └── client.py           # HTTP client for API calls
│   ├── cli/                    # Command-line interface
│   │   ├── __init__.py
│   │   ├── cli.py              # Argument parsing (CLIParser)
│   │   ├── output_formatter.py # Console/JSON/CSV/Markdown formatters
│   │   └── statistics.py       # Statistics calculation
│   ├── core/                   # Core business logic
│   │   ├── __init__.py
│   │   ├── error_collector.py  # Error tracking
│   │   ├── filter.py           # Question filtering
│   │   ├── iteration_executor.py
│   │   ├── loader.py           # Data/question loading
│   │   ├── question_executor.py
│   │   ├── randomizer.py       # Answer randomization
│   │   └── run_manager.py      # Benchmark lifecycle management
│   ├── db/                     # Database layer
│   │   ├── __init__.py
│   │   └── schema.py           # SQLite schema, DatabaseManager
│   └── utils/                  # Utilities
│       ├── __init__.py
│       ├── config.py           # Pydantic settings management
│       └── logging_config.py   # Logging configuration
├── tests/                      # Unit and integration tests
│   ├── conftest.py             # Pytest configuration
│   ├── test_api_client.py
│   ├── test_cli.py
│   ├── test_config.py
│   ├── test_data_loading.py
│   ├── test_database.py
│   ├── test_error_collector.py
│   ├── test_execution.py
│   ├── test_integration.py
│   ├── test_logging_config.py
│   ├── test_model_capabilities.py
│   ├── test_parser.py
│   ├── test_retry.py
│   └── ...
├── conductor/                  # Project management (Conductor extension)
│   ├── index.md                # Project index
│   ├── product.md              # Product definition
│   ├── product-guidelines.md   # Product guidelines
│   ├── tech-stack.md           # Technology stack documentation
│   ├── workflow.md             # Development workflow
│   ├── tracks.md               # Track registry
│   └── tracks/                 # Individual track plans
├── data/                       # Database and data files
├── docs/                       # Documentation
├── logs/                       # Operational logs (git-ignored)
├── .env.example                # Environment template
├── .gitignore
├── requirements.txt            # Python dependencies
├── README.md                   # User-facing documentation
└── QWEN.md                     # This file - AI assistant context
```

## Technology Stack

| Category | Technology | Purpose |
|----------|-----------|---------|
| **Language** | Python 3.10+ | Modern Python with async support and type hints |
| **HTTP Client** | `httpx` | Async HTTP client for OpenRouter API calls |
| **Data Validation** | `pydantic` + `pydantic-settings` | Settings management and validation |
| **Image Processing** | `Pillow` | Image processing for multimodal questions |
| **Database** | `sqlite3` (native) | Local data persistence |
| **Environment** | `python-dotenv` | Environment variable management |
| **Terminal Output** | `rich` | Progress bars, tables, formatted output |
| **Testing** | `pytest`, `pytest-asyncio`, `pytest-mock` | Test framework and utilities |

## Building and Running

### Prerequisites
- Python 3.10+
- OpenRouter API key

### Installation

```bash
# Clone and navigate to project
cd benchmark_llm

# Create virtual environment
python -m venv .venv

# Activate virtual environment (Windows)
.venv\Scripts\activate

# Activate virtual environment (Linux/macOS)
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### Configuration

```bash
# Copy environment template
copy .env.example .env    # Windows
cp .env.example .env      # Linux/macOS
```

Edit `.env` with your settings:
```env
OPENROUTER_API_KEY=your_api_key_here
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
DATABASE_PATH=./data/benchmark.db
LOG_LEVEL=INFO
LOG_FILE_PATH=./logs/benchmark.log
DEFAULT_ITERATIONS=1
DEFAULT_MODELS=
RANDOM_SEED=

# Model Generation Parameters (optional, leave blank for model defaults)
MODEL_MAX_TOKENS=16384    # Recommended for reasoning models (Qwen, o1)
MODEL_TEMPERATURE=0.0     # 0 = deterministic
MODEL_TOP_P=              # Leave blank for default
MODEL_TOP_K=              # Leave blank for default
MODEL_REPEAT_PENALTY=     # Leave blank for default
```

### Running the Benchmark

```bash
# Basic usage
python -m src.main --models openai/gpt-4 --iterations 3

# Test multiple models
python -m src.main --models openai/gpt-4,anthropic/claude-3,google/gemini-pro --iterations 5

# Test specific questions
python -m src.main --models openai/gpt-4 --questions 1-10

# Dry run (validate configuration only)
python -m src.main --models openai/gpt-4 --dry-run

# With custom output format
python -m src.main --models openai/gpt-4 --output json
```

### Command-Line Options

| Option | Description | Default |
|--------|-------------|---------|
| `--models`, `-m` | List of model IDs to benchmark | Required |
| `--iterations`, `-i` | Number of test iterations per model | `1` |
| `--questions`, `-q` | Filter questions by ID or range | All questions |
| `--output`, `-o` | Output format: `console`, `json`, `csv`, `markdown` | `console` |
| `--output-file`, `-f` | Path to output file | None |
| `--seed`, `-s` | Random seed for reproducibility | None |
| `--verbose`, `-v` | Enable verbose output | False |
| `--dry-run` | Validate configuration only | False |

### Running Tests

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=src --cov-report=term-missing

# Run specific test file
pytest tests/test_cli.py -v

# Run with markers
pytest tests/ -v -m "not slow"  # Skip slow tests
pytest tests/ -v -m integration  # Run integration tests only
```

## Development Conventions

### Code Style
- **PEP 8** style guide compliance
- **Type hints** on all functions (Python 3.10+ syntax)
- **Google-style docstrings** with Args, Returns, Raises, and Examples
- **Module docstrings** at the top of each file

### Testing Practices
- **Test-Driven Development (TDD)**: Write failing tests before implementation
- **Code coverage target**: >80% for all modules
- **Test markers**: `@pytest.mark.slow` for slow tests, `@pytest.mark.integration` for integration tests
- **Fixtures**: Use `conftest.py` for shared test fixtures
- **Mocking**: Use `pytest-mock` for external dependencies

### Project Workflow (Conductor)

This project uses the **Conductor extension** for task management. Key principles:

1. **Plan is Source of Truth**: All work tracked in `conductor/tracks/<track_id>/plan.md`
2. **Test-Driven Development**: Write unit tests before implementation
3. **High Code Coverage**: Target >80% coverage for all modules
4. **Non-Interactive Commands**: Prefer non-interactive commands; use `CI=true` for watch-mode tools

### Task Workflow Summary

```
1. Select task from plan.md
2. Mark task as in-progress [~]
3. Write failing tests (Red phase)
4. Implement to pass tests (Green phase)
5. Refactor (optional)
6. Verify coverage
7. Commit code with proper message
8. Attach task summary with git notes
9. Update plan.md with commit SHA
10. Mark task complete [x]
```

### Commit Message Format

```
<type>(<scope>): <description>

[optional body]

[optional footer]
```

**Types**: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`

**Examples**:
```bash
git commit -m "feat(api): Add retry logic for API calls"
git commit -m "fix(db): Correct foreign key constraint in responses table"
git commit -m "test(cli): Add tests for argument parsing"
```

### Quality Gates (Before Marking Task Complete)

- [ ] All tests pass
- [ ] Code coverage meets requirements (>80%)
- [ ] Code follows style guidelines
- [ ] All public functions/methods documented
- [ ] Type safety enforced
- [ ] No linting errors
- [ ] Documentation updated if needed

## Key Components

### BenchmarkRunner (`src/main.py`)
Main orchestrator that coordinates:
- CLI argument parsing
- Configuration loading
- Database initialization
- Test execution
- Statistics calculation
- Output formatting

### Settings (`src/utils/config.py`)
Pydantic-based settings management with environment variable validation:
- `Settings` class with all configuration options
- `get_settings()` for global settings instance
- Validation for log levels, random seed, etc.

### DatabaseManager (`src/db/schema.py`)
SQLite database management:
- Schema definition with tables: `runs`, `models`, `iterations`, `responses`, `errors`, `operational_logs`
- Connection management with context manager support
- Foreign key support enabled

### CLIParser (`src/cli/cli.py`)
Command-line argument parsing:
- `CLIParser` class with argparse configuration
- Question range expansion (e.g., `Q001-Q010`)
- Validation for iterations and other arguments

## Data Collection

The benchmark collects comprehensive metrics:

| Category | Data Collected |
|----------|----------------|
| **Response Data** | Selected answer, full response text |
| **Performance** | Response time/latency |
| **Token Usage** | Input tokens, output tokens, total tokens |
| **Error Tracking** | All errors, failures, edge cases |
| **Consistency** | Multiple run comparisons |
| **Metadata** | Timestamp, model version, configuration |

### Logging Separation
- **Operational Logs** → `.log` files (progress, errors, status)
- **Experimental Data** → SQLite database (input, output, complete metrics)

## Supported Models

Via OpenRouter API, the tool supports:
- **OpenAI**: GPT-4, GPT-4 Turbo, GPT-3.5 Turbo
- **Anthropic**: Claude 3 (Opus, Sonnet, Haiku), Claude 2
- **Google**: Gemini Pro, Gemini Ultra, Gemini 1.5
- **Meta**: Llama 2, Llama 3, Llama 3.1
- **Mistral**: Mistral Large, Mistral Medium, Mixtral
- And many more via OpenRouter

## Troubleshooting

### Common Issues

**API Key Not Configured**
```
Error: OpenRouter API key not configured
```
**Solution**: Set `OPENROUTER_API_KEY` in `.env` or environment.

**Rate Limit Exceeded**
```
HTTPError_429: Rate limit exceeded
```
**Solution**: Wait and retry, reduce iterations, or check account limits.

**Database Permission Error**
```
sqlite3.OperationalError: unable to open database file
```
**Solution**: Ensure `data/` directory exists and is writable.

## Documentation References

- **[README.md](README.md)**: User-facing documentation with installation and usage
- **[docs/USAGE.md](docs/USAGE.md)**: Comprehensive usage guide
- **[docs/CONFIGURATION.md](docs/CONFIGURATION.md)**: Configuration reference
- **[conductor/product.md](conductor/product.md)**: Product definition
- **[conductor/tech-stack.md](conductor/tech-stack.md)**: Technology stack
- **[conductor/workflow.md](conductor/workflow.md)**: Development workflow

## Environment Variables

### Core Configuration

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `OPENROUTER_API_KEY` | OpenRouter API key | - | Yes (for execution) |
| `OPENROUTER_BASE_URL` | API base URL | `https://openrouter.ai/api/v1` | No |
| `DATABASE_PATH` | SQLite database path | `./data/benchmark.db` | No |
| `LOG_LEVEL` | Logging level | `INFO` | No |
| `LOG_FILE_PATH` | Log file path | `./logs/benchmark.log` | No |
| `DEFAULT_ITERATIONS` | Default iterations | `1` | No |
| `RANDOM_SEED` | Random seed | `None` | No |

### Model Generation Parameters (Optional)

**Important:** If left blank, these parameters are NOT sent to the API, allowing the model/server to use its own defaults.

| Variable | Description | Default | Notes |
|----------|-------------|---------|-------|
| `MODEL_MAX_TOKENS` | Maximum generation tokens | Model default | **Critical:** llama.cpp defaults to 100 tokens. Set to `16384` for reasoning models (Qwen, o1). |
| `MODEL_TEMPERATURE` | Sampling temperature | Model default | `0.0` = deterministic, higher = more creative |
| `MODEL_TOP_P` | Nucleus sampling | Model default | Alternative to temperature |
| `MODEL_TOP_K` | Top-k sampling | Model default | Limits token selection |
| `MODEL_REPEAT_PENALTY` | Repetition penalty | Model default | Reduces repetitive output |
