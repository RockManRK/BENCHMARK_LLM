# Benchmark LLM

A Python-based benchmark tool for evaluating LLM (Large Language Model) performance by administering a 100-question medical questionnaire through the OpenRouter API.

## Overview

This tool enables researchers and developers to:
- Test multiple LLM models against a standardized questionnaire
- Configure test iterations for consistency analysis
- Filter questions by ID or metadata attributes (e.g., `--where status=valid`, `--exclude status=annulled`)
- Collect comprehensive metrics (response time, token usage, accuracy, **cost**)
- Store all experimental data in SQLite for analysis
- Handle both text-only and image-based questions
- **NEW:** Automatic model detection with metadata
- **NEW:** Structured outputs (JSON schema) support
- **NEW:** Simplified CLI with `bcllm` command
- **NEW:** Cost tracking per request (via OpenRouter `usage.cost`)

## Requirements

- Python 3.10+
- OpenRouter API key

## Installation

### Option 1: Direct Usage (Recommended for Testing)

1. Clone the repository:
```bash
git clone <repository-url>
cd benchmark_llm
```

2. Create a virtual environment:
```bash
python -m venv .venv
```

3. Activate the virtual environment:

**Windows:**
```bash
.venv\Scripts\activate
```

**Linux/macOS:**
```bash
source .venv/bin/activate
```

4. Install dependencies:
```bash
pip install -r requirements.txt
```

5. Run with:
```bash
python bcllm.py --help
```

### Option 2: Install as Package (Recommended for Production)

After steps 1-4 above, install as package:

```bash
pip install -e .
```

Then use the `bcllm` command directly:
```bash
bcllm --help
```

## Configuration

### Environment Variables

#### Step 1: Configure OPENROUTER_API_KEY (Required)

**IMPORTANT:** For security reasons, the API key must be set via system environment variable, NOT in the `.env` file.

**Windows (PowerShell or CMD):**
```bash
setx OPENROUTER_API_KEY "your-api-key-here"
```

**Linux/macOS:**
```bash
export OPENROUTER_API_KEY=your-api-key-here
```

Add to your shell profile (`~/.bashrc`, `~/.zshrc`, or PowerShell profile) for persistence.

#### Step 2: Configure Non-Sensitive Settings

Copy the example environment file:

```bash
copy .env.example .env    # Windows
cp .env.example .env      # Linux/macOS
```

Edit `.env` with your settings (DO NOT include OPENROUTER_API_KEY here):

```env
# OpenRouter API Configuration
# NOTE: OPENROUTER_API_KEY must be set via system environment variable, not in this file!
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1

# Database Configuration
DATABASE_PATH=./data/benchmark.db

# Logging Configuration
LOG_LEVEL=INFO
LOG_FILE_PATH=./logs/benchmark.log

# Test Configuration
DEFAULT_ITERATIONS=1
DEFAULT_MODELS=

# Randomization Seed (optional, for reproducibility)
RANDOM_SEED=
```

### Configuration Options

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `OPENROUTER_API_KEY` | Your OpenRouter API key (**must be set via system env**) | - | Yes |
| `OPENROUTER_BASE_URL` | OpenRouter API base URL | `https://openrouter.ai/api/v1` | No |
| `DATABASE_PATH` | Path to SQLite database | `./data/benchmark.db` | No |
| `LOG_LEVEL` | Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL) | `INFO` | No |
| `LOG_FILE_PATH` | Path to log file | `./logs/benchmark.log` | No |
| `DEFAULT_ITERATIONS` | Number of test iterations per model | `1` | No |
| `RANDOM_SEED` | Seed for randomization (see Random Seed Modes below) | `None` | No |
| `USE_STRUCTURED_OUTPUTS` | Enable JSON schema structured outputs | `false` | No |

**Security Note:** The `OPENROUTER_API_KEY` must be configured via system environment variable, not in the `.env` file. This prevents accidental exposure in version control.

### Random Seed Modes

The `RANDOM_SEED` configuration supports three distinct modes for controlling answer randomization:

| Mode | Configuration | Behavior | Use Case |
|------|---------------|----------|----------|
| **No Randomization** | `RANDOM_SEED=` (empty) or not set | Answers stay in original A,B,C,D order | Default behavior, no shuffling |
| **AUTO** | `RANDOM_SEED=AUTO` | Automatic seed generation using hash of run_id (unique per run) | When you want randomization but don't need reproducibility |
| **Fixed Seed** | `RANDOM_SEED=42` (any integer) | Fixed seed for reproducible randomization | Reproducible experiments, debugging |

**Example usage:**

```bash
# No randomization (default)
RANDOM_SEED=  # in .env
bcllm --models Qwen --questions Q001

# AUTO mode - unique seed per run
RANDOM_SEED=AUTO  # in .env
bcllm --models Qwen --questions Q001

# Fixed seed - reproducible
RANDOM_SEED=42  # in .env
# OR via CLI
bcllm --models Qwen --questions Q001 --seed 42
```

**Note:** The `--seed` CLI argument takes precedence over `RANDOM_SEED` in `.env`.

### Model Generation Parameters (Optional)

These parameters control how the model generates responses. **If left blank, the system will not send them, allowing the model/server to use its own defaults.**

| Variable | Description | Recommended | Notes |
|----------|-------------|-------------|-------|
| `MODEL_MAX_TOKENS` | Maximum tokens for generation | `16384` for reasoning models | **Important:** llama.cpp defaults to 100 tokens, which is insufficient for reasoning models (Qwen, o1, etc.). Set to `16384` or higher for models with chain-of-thought. |
| `MODEL_TEMPERATURE` | Sampling temperature | `0.0` for deterministic | Lower = more deterministic, higher = more creative |
| `MODEL_TOP_P` | Nucleus sampling parameter | Leave blank | Alternative to temperature |
| `MODEL_TOP_K` | Top-k sampling parameter | Leave blank | Limits token selection |
| `MODEL_REPEAT_PENALTY` | Penalty for repetition | Leave blank | Reduces repetitive output |

**Example Configuration for Reasoning Models:**
```env
MODEL_MAX_TOKENS=16384
MODEL_TEMPERATURE=0.0
MODEL_TOP_P=
MODEL_TOP_K=
MODEL_REPEAT_PENALTY=
```

**Example Configuration for Standard Models (using defaults):**
```env
MODEL_MAX_TOKENS=
MODEL_TEMPERATURE=
MODEL_TOP_P=
MODEL_TOP_K=
MODEL_REPEAT_PENALTY=
```

## Basic Usage

### Running a Benchmark Test

```bash
python -m src.main --models openai/gpt-4 --iterations 3
```

### Incremental Flow (Add Models to Existing Run)

You can add models to an existing run without re-executing already answered questions:

```bash
# Day 1: Create run with 3 models
bcllm --models gpt-4 claude-3 gemini --iterations 3
# → run-20260314-abc123 created

# Day 2: Add 2 more models
bcllm --add-to-run run-20260314-abc123 --add-models qwen-2.5 llama-3
# → Models added to run with status 'pending'

# Day 3: Re-execute run (only pending models executed)
bcllm --run-id run-20260314-abc123 --iterations 3
# → gpt-4, claude-3, gemini: SKIPPED (completed)
# → qwen-2.5, llama-3: EXECUTED (pending)

# When finished, complete the run
bcllm --complete-run run-20260314-abc123
# → No more models can be added
```

**How it works:**
- The system tracks which questions each model has answered using `(question_id, iteration)` as the key
- When re-executing, only unanswered questions are processed
- Clear logs show which models are skipped: `⏭️  Skipping model variant {id}: status=completed`

**Benefits:**
- No wasted API calls on already completed models
- Flexible workflow: add models as needed
- Automatic detection of pending questions

### Command-Line Options

| Option | Description |
|--------|-------------|
| `--models` | Comma-separated list of model IDs to test |
| `--iterations` | Number of iterations per model |
| `--questions` | Filter questions by ID or range (e.g., `Q001` or `Q001-Q010`) |
| `--where` | Filter questions by metadata (e.g., `--where status=valid`) |
| `--exclude` | Exclude questions by metadata (e.g., `--exclude status=annulled`) |
| `--experiment` | Create a frozen experiment with config hash (immutable config) |
| `--config` | Path to configuration file |
| `--output` | Output format: `console`, `json`, `csv`, `markdown` |
| `--output-file` | Path to output file for results |
| `--seed` | Random seed for reproducible answer randomization (integer or use RANDOM_SEED in .env) |
| `--vary-seed` | Use different seed for each iteration |
| `--test-mode` | Run without persisting data (in-memory database) |
| `--mode` | Execution mode: `test`, `dev`, `experiment` |
| `--dry-run` | Validate configuration without executing |
| `--verbose` | Enable verbose logging |
| `--temperature` | Temperature for model generation |
| `--max-tokens` | Maximum tokens for model generation |
| `--top-p` | Top-p sampling parameter |
| `--top-k` | Top-k sampling parameter |
| `--repeat-penalty` | Repeat penalty parameter |
| `--reasoning-effort` | Reasoning effort level: `xhigh`, `high`, `medium`, `low`, `minimal`, `none` |
| `--reasoning-tokens` | Maximum tokens for reasoning |
| `--reasoning-exclude` | Exclude reasoning from response (use internally) |

### Example: Filter Questions by Metadata

```bash
# Exclude annulled questions
python bcllm.py --models gpt-4 --questions Q001-Q100 --exclude status=annulled

# Only valid questions without images
python bcllm.py --models gpt-4 --questions Q001-Q100 --where status=valid has_image=false

# Combine filters
python bcllm.py --models gpt-4 --questions Q001-Q100 --where status=valid --exclude has_image=true
```

### Example: Test Multiple Models

```bash
python -m src.main --models openai/gpt-4,anthropic/claude-3,google/gemini-pro --iterations 5
```

### Example: Test Specific Questions

```bash
python -m src.main --models openai/gpt-4 --questions 1-10
```

### Experiment Mode

Create frozen experiments with immutable configuration:

```bash
# Create a named experiment
bcllm --experiment my-experiment --models Qwen --questions Q001

# Experiment configuration is hashed and immutable
# Any change to config creates a new experiment
```

**Features:**
- Configuration is hashed and stored with results
- Ensures reproducibility - same config = same experiment
- Supports shadow experiments in dev mode for testing
- All runs linked to experiment ID for easy analysis

**Use cases:**
- Formal benchmark runs that need to be exactly reproducible
- Comparing model performance across different configurations
- Academic/research experiments requiring strict configuration control

## Project Structure

```
benchmark_llm/
├── src/
│   ├── core/          # Core business logic
│   ├── api/           # OpenRouter API integration
│   ├── db/            # Database layer
│   ├── cli/           # Command-line interface
│   └── utils/         # Utilities and configuration
├── tests/             # Unit and integration tests
├── docs/              # Documentation
│   ├── USAGE.md       # Detailed usage guide
│   └── CONFIGURATION.md # Configuration reference
├── logs/              # Operational logs
├── data/              # Database and data files
├── .env.example       # Environment template
├── requirements.txt   # Python dependencies
└── README.md          # This file
```

## Documentation

- **[Usage Guide](docs/USAGE.md)** - Comprehensive usage instructions and examples
- **[Configuration Guide](docs/CONFIGURATION.md)** - Complete configuration reference

## Development

### Running Tests

```bash
pytest tests/ -v
```

### Running Tests with Coverage

```bash
pytest tests/ --cov=src --cov-report=term-missing
```

### Code Style

This project follows:
- PEP 8 style guide
- Type hints on all functions
- Google-style docstrings

## Supported Models

The tool supports all models available through OpenRouter, including:
- **OpenAI**: GPT-4, GPT-4 Turbo, GPT-3.5 Turbo
- **Anthropic**: Claude 3 (Opus, Sonnet, Haiku), Claude 2
- **Google**: Gemini Pro, Gemini Ultra, Gemini 1.5
- **Meta**: Llama 2, Llama 3, Llama 3.1
- **Mistral**: Mistral Large, Mistral Medium, Mixtral
- **And many more** via OpenRouter's unified API

For a complete list of available models, visit [OpenRouter Models](https://openrouter.ai/models).

## Data Collection

The benchmark collects comprehensive metrics:
- **Response Data**: Selected answer, full response text
- **Performance Metrics**: Response time/latency
- **Token Usage**: Input tokens, response tokens, total tokens, reasoning tokens
- **Cost**: Final cost per request (from OpenRouter `usage.cost`)
- **Error Tracking**: All errors, failures, and edge cases
- **Consistency Data**: Multiple run comparisons when configured
- **Metadata**: Timestamp, model version, configuration used

**Token Calculation Formulas:**
- `total_tokens = input_tokens + response_tokens` (excludes reasoning_tokens)
- `effective_tokens = input_tokens + response_tokens + reasoning_tokens`
- `reasoning_tokens` are a subtype of `response_tokens`, not additional

**Database Schema:**
```sql
CREATE TABLE responses (
    -- ... other fields ...
    input_tokens INTEGER,       -- prompt_tokens
    response_tokens INTEGER,    -- completion_tokens (response output)
    total_tokens INTEGER,       -- input_tokens + response_tokens (excludes reasoning)
    reasoning_tokens INTEGER,   -- reasoning tokens (optional, from completion_tokens_details)
    effective_tokens INTEGER,   -- input + response + reasoning (total computational cost)
    cost REAL,                  -- cost in credits (from usage.cost)
    -- ... other fields ...
);
```

**Important:**
- `usage.cost` is the official cost value (the "receipt")
- `usage.cost_details` is NOT used (informational only)
- Empty configuration values are NOT sent to the API (model uses its own defaults)
- `response_tokens` was previously named `output_tokens` (consolidated in v1.1.0)

## Logging

- **Operational Logs**: Written to `.log` files (progress, errors, status)
- **Experimental Data**: Stored in SQLite database (input, output, complete metrics)

## Troubleshooting

### Common Issues

#### API Key Not Configured

**Error:** `Error: OpenRouter API key not configured`

**Solution:**
```bash
# Set via environment
export OPENROUTER_API_KEY=your-api-key

# Or add to .env file
OPENROUTER_API_KEY=your-api-key
```

#### Rate Limit Exceeded

**Error:** `HTTPError_429: Rate limit exceeded`

**Solutions:**
- Wait a few minutes and retry
- Reduce the number of iterations
- Check your OpenRouter account limits

#### Database Permission Error

**Error:** `sqlite3.OperationalError: unable to open database file`

**Solution:**
```bash
# Ensure data directory exists and is writable
mkdir -p data
chmod 755 data

# Or use a different location
export DATABASE_PATH=/tmp/benchmark.db
```

#### Timeout Errors

**Error:** `TimeoutError: Request timed out`

**Solutions:**
- Check your internet connection
- The model may be experiencing high load - retry later
- Consider using a model with faster response times
- **Note:** Default timeout is now 180s (3 minutes) to accommodate models that generate thousands of tokens

**Why 180s?** Models can generate large responses:
- Example: 6344 tokens × ~0.02s/token = ~127s
- Reasoning models (Qwen, o1) often generate 5000+ tokens
- Previous 30s timeout was insufficient for complex responses

#### Enhanced Logging and Debugging

The system now provides comprehensive logging for debugging:

**Request Logging:**
- Model ID and version
- `max_tokens`, `temperature` settings
- Whether structured outputs are enabled

**Response Logging:**
- Token usage (input, output, total)
- `finish_reason` (why model stopped: `stop`, `length`, `eos`, `error`)
- HTTP status code

**Error Logging:**
- Full error response body captured in `error_details` database field
- Complete raw API response stored in `raw_response_json` field
- Detailed error messages in log files

**To debug issues:**
```bash
# Enable verbose logging
bcllm --models Qwen --verbose

# Check logs
cat logs/benchmark.log

# Query database for error details
sqlite3 data/benchmark.db "SELECT model_id, finish_reason, error_details FROM responses WHERE finish_reason='error'"
```

#### Response Cut Off / Incomplete

**Error:** Model response is cut off mid-sentence, or `finish_reason: "length"` in logs

**Cause:** The model was limited by `max_tokens`. This is common with:
- **llama.cpp local servers** (default: 100 tokens)
- **Reasoning models** (Qwen, o1, etc.) that need more tokens for chain-of-thought

**Solution:**
```env
# In .env file, set a higher max_tokens value
MODEL_MAX_TOKENS=16384
```

**Note:** If `MODEL_MAX_TOKENS` is left blank, the system uses the model/server default. For llama.cpp, this is typically 100 tokens, which is insufficient for reasoning models.

#### Empty Response from Reasoning Models

**Error:** Model returns `reasoning_content` but `content` is empty

**Cause:** Some models (Qwen, o1) separate reasoning from final answer. If `max_tokens` is too low, the model never reaches the final answer.

**Solution:**
1. Increase `MODEL_MAX_TOKENS` to `16384` or higher
2. The system automatically handles `reasoning_content` fallback

### Getting Help

1. **Check logs**: Review `logs/benchmark.log` for detailed error information
2. **Dry run**: Validate configuration with `--dry-run` flag
3. **Debug mode**: Set `LOG_LEVEL=DEBUG` for verbose output
4. **Documentation**: See [docs/USAGE.md](docs/USAGE.md) and [docs/CONFIGURATION.md](docs/CONFIGURATION.md)

## License

MIT License

## Contributing

1. Fork the repository
2. Create a feature branch
3. Write tests for new functionality
4. Ensure all tests pass with >80% coverage
5. Submit a pull request

## Support

For issues and questions, please open an issue on the GitHub repository.
