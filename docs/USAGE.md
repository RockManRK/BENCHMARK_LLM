# Benchmark LLM - Usage Guide

This guide provides detailed instructions for using the Benchmark LLM tool, from basic usage to advanced configurations.

## Table of Contents

- [Quick Start](#quick-start)
- [Installation](#installation)
- [Configuration](#configuration)
- [Basic Usage](#basic-usage)
- [Advanced Usage](#advanced-usage)
- [Output Formats](#output-formats)
- [Understanding Results](#understanding-results)
- [Best Practices](#best-practices)

---

## Quick Start

Get up and running in 3 steps:

```bash
# 1. Set your API key
export OPENROUTER_API_KEY=your_api_key_here

# 2. Run a simple benchmark
python -m src.main --models openai/gpt-4 --iterations 3

# 3. View results
# Results are displayed in the console and stored in the database
```

---

## Installation

### Prerequisites

- Python 3.10 or higher
- pip (Python package manager)
- OpenRouter API key

### Step-by-Step Installation

1. **Clone the repository** (if not already done):
   ```bash
   git clone <repository-url>
   cd benchmark_llm
   ```

2. **Create a virtual environment** (recommended):
   ```bash
   # Windows
   python -m venv .venv
   .venv\Scripts\activate

   # Linux/macOS
   python3 -m venv .venv
   source .venv/bin/activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment**:
   ```bash
   # Copy example environment file
   copy .env.example .env    # Windows
   cp .env.example .env      # Linux/macOS

   # Edit .env and add your API key
   ```

---

## Configuration

### Environment Variables

The tool is configured via environment variables. Create a `.env` file in the project root:

```env
# Required: OpenRouter API key
OPENROUTER_API_KEY=sk-or-...

# Optional: API base URL (default: https://openrouter.ai/api/v1)
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1

# Optional: Database location (default: ./data/benchmark.db)
DATABASE_PATH=./data/benchmark.db

# Optional: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
LOG_LEVEL=INFO

# Optional: Log file location (default: ./logs/benchmark.log)
LOG_FILE_PATH=./logs/benchmark.log

# Optional: Default iterations per model
DEFAULT_ITERATIONS=1

# Optional: Default models to test (comma-separated)
DEFAULT_MODELS=

# Optional: Random seed for reproducibility
RANDOM_SEED=42
```

### Configuration Precedence

Configuration values are loaded in this order (highest priority first):

1. Command-line arguments
2. Environment variables
3. `.env` file
4. Default values

---

## Basic Usage

### Running Your First Benchmark

Test a single model with default settings:

```bash
python -m src.main --models openai/gpt-4
```

### Testing Multiple Models

Compare multiple models in a single run:

```bash
python -m src.main --models openai/gpt-4,anthropic/claude-3,google/gemini-pro
```

### Running Multiple Iterations

Test consistency by running multiple iterations:

```bash
python -m src.main --models openai/gpt-4 --iterations 5
```

### Testing Specific Questions

Run only specific questions by ID:

```bash
# Single question
python -m src.main --models openai/gpt-4 --questions 1

# Range of questions
python -m src.main --models openai/gpt-4 --questions 1-10

# Multiple specific questions
python -m src.main --models openai/gpt-4 --questions 1,5,10,15

# Mixed format
python -m src.main --models openai/gpt-4 --questions 1-5,10,15-20
```

### Dry Run Mode

Validate configuration without making API calls:

```bash
python -m src.main --models openai/gpt-4 --dry-run
```

---

## Advanced Usage

### Setting Random Seed for Reproducibility

Ensure reproducible answer randomization:

```bash
python -m src.main --models openai/gpt-4 --seed 42
```

### Custom Database Location

Store results in a custom location:

```bash
# Via environment variable
export DATABASE_PATH=/path/to/custom.db
python -m src.main --models openai/gpt-4

# Or modify .env file
```

### Custom Output File

Export results to a file:

```bash
# JSON format
python -m src.main --models openai/gpt-4 --output-format json --output-file results.json

# CSV format
python -m src.main --models openai/gpt-4 --output-format csv --output-file results.csv

# Markdown format
python -m src.main --models openai/gpt-4 --output-format markdown --output-file results.md
```

### Verbose Logging

Enable debug-level logging for troubleshooting:

```bash
# Via environment variable
export LOG_LEVEL=DEBUG
python -m src.main --models openai/gpt-4

# Or modify .env file
LOG_LEVEL=DEBUG
```

---

## Output Formats

### Console Output (Default)

Human-readable table format displayed in the terminal:

```
Benchmark Results
=================

Model: openai/gpt-4
  Total Questions: 100
  Correct Answers: 85
  Accuracy: 85.00%
  Avg Latency: 1250ms
  Total Input Tokens: 50000
  Total Output Tokens: 10000
  Errors: 2
```

### JSON Output

Machine-readable format for programmatic processing:

```bash
python -m src.main --models openai/gpt-4 --output-format json
```

Example output:
```json
{
  "models": [
    {
      "model_id": "openai/gpt-4",
      "total_questions": 100,
      "correct_answers": 85,
      "accuracy": 0.85,
      "avg_latency_ms": 1250,
      "total_input_tokens": 50000,
      "total_output_tokens": 10000,
      "error_count": 2
    }
  ]
}
```

### CSV Output

Spreadsheet-compatible format:

```bash
python -m src.main --models openai/gpt-4 --output-format csv
```

### Markdown Output

Formatted for documentation:

```bash
python -m src.main --models openai/gpt-4 --output-format markdown
```

---

## Understanding Results

### Metrics Explained

| Metric | Description |
|--------|-------------|
| **Total Questions** | Number of questions attempted |
| **Correct Answers** | Number of correctly answered questions |
| **Accuracy** | Percentage of correct answers (Correct/Total × 100) |
| **Avg Latency** | Average response time in milliseconds |
| **Total Input Tokens** | Total tokens sent to the model |
| **Total Output Tokens** | Total tokens generated by the model |
| **Error Count** | Number of failed requests |

### Interpreting Accuracy

- **90-100%**: Excellent performance
- **80-89%**: Good performance
- **70-79%**: Average performance
- **Below 70%**: May indicate model limitations or configuration issues

### Understanding Errors

Common error types:

| Error Type | Description | Solution |
|------------|-------------|----------|
| `HTTPError_401` | Invalid API key | Check OPENROUTER_API_KEY |
| `HTTPError_429` | Rate limit exceeded | Wait and retry, or reduce iterations |
| `TimeoutError` | Request timed out | Increase timeout or check network |
| `RequestError` | Network error | Check internet connection |

---

## Best Practices

### 1. Start Small

Begin with a few questions to validate setup:

```bash
python -m src.main --models openai/gpt-4 --questions 1-5 --iterations 1
```

### 2. Use Reproducible Seeds

For scientific comparisons, always use a seed:

```bash
python -m src.main --models openai/gpt-4 --seed 42
```

### 3. Run Multiple Iterations

For reliable results, run at least 3 iterations:

```bash
python -m src.main --models openai/gpt-4 --iterations 3
```

### 4. Monitor Token Usage

Track token consumption to manage costs:

```bash
python -m src.main --models openai/gpt-4 --output-format json | jq '.[].total_tokens'
```

### 5. Export Results

Always export results for later analysis:

```bash
python -m src.main --models openai/gpt-4 --output-format json --output-file results.json
```

### 6. Use Dry Run for Validation

Before running expensive benchmarks:

```bash
python -m src.main --models openai/gpt-4 --dry-run
```

### 7. Check Logs for Issues

Review logs for detailed error information:

```bash
# View recent logs
tail -f logs/benchmark.log

# Search for errors
grep ERROR logs/benchmark.log
```

---

## Command-Line Reference

### Complete Option List

| Option | Short | Description | Default |
|--------|-------|-------------|---------|
| `--models` | `-m` | Comma-separated model IDs | Required |
| `--iterations` | `-i` | Iterations per model | 1 |
| `--questions` | `-q` | Question filter (e.g., `1-10`) | All |
| `--seed` | `-s` | Random seed | None |
| `--output-format` | `-f` | Output format (console/json/csv/markdown) | console |
| `--output-file` | `-o` | Output file path | stdout |
| `--config` | `-c` | Config file path | .env |
| `--dry-run` | `-d` | Validate without API calls | False |
| `--help` | `-h` | Show help message | - |

### Examples

```bash
# Full benchmark with all options
python -m src.main \
  --models openai/gpt-4,anthropic/claude-3 \
  --iterations 5 \
  --questions 1-50 \
  --seed 42 \
  --output-format json \
  --output-file benchmark_results.json

# Quick validation
python -m src.main -m gpt-4 -q 1-3 -d
```

---

## Database Access

Results are stored in SQLite database. Query directly for custom analysis:

```bash
# Using sqlite3 CLI
sqlite3 data/benchmark.db

# Example queries
SELECT model_id, COUNT(*) as total, AVG(is_correct) as accuracy
FROM responses
GROUP BY model_id;

SELECT * FROM responses WHERE status = 'error';
```

---

## Support

For issues and questions:

1. Check the [README.md](../README.md) for general information
2. Review [CONFIGURATION.md](./CONFIGURATION.md) for configuration options
3. Check logs in `logs/benchmark.log`
4. Open an issue on the GitHub repository
