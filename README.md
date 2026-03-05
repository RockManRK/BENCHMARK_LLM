# Benchmark LLM

A Python-based benchmark tool for evaluating LLM (Large Language Model) performance by administering a 100-question medical questionnaire through the OpenRouter API.

## Overview

This tool enables researchers and developers to:
- Test multiple LLM models against a standardized questionnaire
- Configure test iterations for consistency analysis
- Filter questions by ID or metadata attributes
- Collect comprehensive metrics (response time, token usage, accuracy)
- Store all experimental data in SQLite for analysis
- Handle both text-only and image-based questions

## Requirements

- Python 3.10+
- OpenRouter API key

## Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd benchmark_llm
```

2. Create a virtual environment (recommended):
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

## Configuration

### Environment Variables

Copy the example environment file and configure it:

```bash
copy .env.example .env    # Windows
cp .env.example .env      # Linux/macOS
```

Edit `.env` with your settings:

```env
# OpenRouter API Configuration (required)
OPENROUTER_API_KEY=your_api_key_here
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
| `OPENROUTER_API_KEY` | Your OpenRouter API key | - | Yes |
| `OPENROUTER_BASE_URL` | OpenRouter API base URL | `https://openrouter.ai/api/v1` | No |
| `DATABASE_PATH` | Path to SQLite database | `./data/benchmark.db` | No |
| `LOG_LEVEL` | Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL) | `INFO` | No |
| `LOG_FILE_PATH` | Path to log file | `./logs/benchmark.log` | No |
| `DEFAULT_ITERATIONS` | Number of test iterations per model | `1` | No |
| `RANDOM_SEED` | Seed for reproducible randomization | `None` | No |

## Basic Usage

### Running a Benchmark Test

```bash
python -m src.main --models openai/gpt-4 --iterations 3
```

### Command-Line Options

| Option | Description |
|--------|-------------|
| `--models` | Comma-separated list of model IDs to test |
| `--iterations` | Number of iterations per model |
| `--questions` | Filter questions by ID (e.g., `1,2,3` or `1-10`) |
| `--config` | Path to configuration file |

### Example: Test Multiple Models

```bash
python -m src.main --models openai/gpt-4,anthropic/claude-3,google/gemini-pro --iterations 5
```

### Example: Test Specific Questions

```bash
python -m src.main --models openai/gpt-4 --questions 1-10
```

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
- **Token Usage**: Input tokens, output tokens, total tokens
- **Error Tracking**: All errors, failures, and edge cases
- **Consistency Data**: Multiple run comparisons when configured
- **Metadata**: Timestamp, model version, configuration used

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
