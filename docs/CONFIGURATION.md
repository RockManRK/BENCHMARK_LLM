# Benchmark LLM - Configuration Guide

This guide provides comprehensive documentation for all configuration options available in the Benchmark LLM tool.

## Table of Contents

- [Overview](#overview)
- [Environment Variables](#environment-variables)
- [Configuration Files](#configuration-files)
- [Command-Line Arguments](#command-line-arguments)
- [Configuration Precedence](#configuration-precedence)
- [Detailed Option Reference](#detailed-option-reference)
- [Example Configurations](#example-configurations)
- [Troubleshooting Configuration](#troubleshooting-configuration)

---

## Overview

Benchmark LLM supports multiple configuration methods:

1. **Environment Variables** - Set via `.env` file or system environment
2. **Command-Line Arguments** - Passed directly when running the tool
3. **Configuration Files** - Optional YAML/JSON config files

The system uses a layered approach where command-line arguments override environment variables, which override defaults.

---

## Environment Variables

### Required Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `OPENROUTER_API_KEY` | Your OpenRouter API key | `sk-or-v1-abc123...` |

### Optional Variables

| Variable | Description | Default | Example |
|----------|-------------|---------|---------|
| `OPENROUTER_BASE_URL` | OpenRouter API base URL | `https://openrouter.ai/api/v1` | `https://custom.api.com/v1` |
| `DATABASE_PATH` | SQLite database file path | `./data/benchmark.db` | `/var/data/benchmark.db` |
| `LOG_LEVEL` | Logging verbosity | `INFO` | `DEBUG`, `WARNING`, `ERROR` |
| `LOG_FILE_PATH` | Log file location | `./logs/benchmark.log` | `/var/log/benchmark.log` |
| `DEFAULT_ITERATIONS` | Default iterations per model | `1` | `3` |
| `DEFAULT_MODELS` | Default models to test | (empty) | `openai/gpt-4,anthropic/claude-3` |
| `RANDOM_SEED` | Seed for reproducibility | (none) | `42` |

---

## Configuration Files

### .env File Format

Create a `.env` file in the project root:

```env
# OpenRouter API Configuration
OPENROUTER_API_KEY=sk-or-v1-your-api-key-here
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1

# Database Configuration
DATABASE_PATH=./data/benchmark.db

# Logging Configuration
LOG_LEVEL=INFO
LOG_FILE_PATH=./logs/benchmark.log

# Test Configuration
DEFAULT_ITERATIONS=1
DEFAULT_MODELS=

# Randomization
RANDOM_SEED=42
```

### Custom Configuration File

You can also use a custom configuration file with the `--config` option:

```bash
python -m src.main --config /path/to/config.yaml --models openai/gpt-4
```

---

## Command-Line Arguments

### Basic Arguments

| Argument | Short | Description | Required |
|----------|-------|-------------|----------|
| `--models` | `-m` | Comma-separated list of model IDs | Yes |
| `--iterations` | `-i` | Number of iterations per model | No (default: 1) |
| `--questions` | `-q` | Filter questions by ID or range | No (default: all) |
| `--seed` | `-s` | Random seed for reproducibility | No |
| `--dry-run` | `-d` | Validate config without API calls | No |

### Output Arguments

| Argument | Short | Description | Default |
|----------|-------|-------------|---------|
| `--output-format` | `-f` | Output format (console/json/csv/markdown) | `console` |
| `--output-file` | `-o` | File to write output | stdout |

### Configuration Arguments

| Argument | Short | Description | Default |
|----------|-------|-------------|---------|
| `--config` | `-c` | Path to configuration file | `.env` |

---

## Configuration Precedence

Values are resolved in this order (highest priority first):

```
1. Command-line arguments
       ↓
2. Environment variables (system)
       ↓
3. .env file variables
       ↓
4. Default values
```

### Example

```bash
# .env file has: DEFAULT_ITERATIONS=1
# Command line has: --iterations 5
# Result: 5 iterations (command line wins)
```

---

## Detailed Option Reference

### API Configuration

#### OPENROUTER_API_KEY

**Type:** String  
**Required:** Yes  
**Default:** None

Your OpenRouter API key for authentication.

```env
OPENROUTER_API_KEY=sk-or-v1-abc123def456...
```

**Getting your API key:**
1. Visit [openrouter.ai](https://openrouter.ai)
2. Sign in or create an account
3. Navigate to API Keys section
4. Generate a new key

#### OPENROUTER_BASE_URL

**Type:** String (URL)  
**Required:** No  
**Default:** `https://openrouter.ai/api/v1`

Custom API endpoint for OpenRouter-compatible services.

```env
OPENROUTER_BASE_URL=https://custom-endpoint.example.com/v1
```

---

### Database Configuration

#### DATABASE_PATH

**Type:** String (file path)  
**Required:** No  
**Default:** `./data/benchmark.db`

Location of the SQLite database file.

```env
DATABASE_PATH=/var/data/benchmark_llm/results.db
```

**Notes:**
- Parent directories are created automatically
- Use absolute paths for production deployments
- Database is created on first run

---

### Logging Configuration

#### LOG_LEVEL

**Type:** String (enum)  
**Required:** No  
**Default:** `INFO`  
**Valid values:** `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`

Controls the verbosity of log output.

```env
# Verbose logging for debugging
LOG_LEVEL=DEBUG

# Production logging
LOG_LEVEL=WARNING
```

**Level descriptions:**
- `DEBUG`: Detailed diagnostic information
- `INFO`: General operational messages
- `WARNING`: Warning messages (potential issues)
- `ERROR`: Error messages (failures)
- `CRITICAL`: Critical errors (system instability)

#### LOG_FILE_PATH

**Type:** String (file path)  
**Required:** No  
**Default:** `./logs/benchmark.log`

Location of the log file.

```env
LOG_FILE_PATH=/var/log/benchmark_llm/app.log
```

**Notes:**
- Parent directories are created automatically
- Logs are appended (not overwritten)
- Consider log rotation for long-running deployments

---

### Test Configuration

#### DEFAULT_ITERATIONS

**Type:** Integer  
**Required:** No  
**Default:** `1`  
**Minimum:** `1`

Number of test iterations per model when not specified via command line.

```env
DEFAULT_ITERATIONS=3
```

**Recommendations:**
- `1`: Quick validation
- `3-5`: Standard benchmarking
- `10+`: Statistical analysis

#### DEFAULT_MODELS

**Type:** String (comma-separated)  
**Required:** No  
**Default:** (empty)

Default models to test when not specified via command line.

```env
DEFAULT_MODELS=openai/gpt-4,anthropic/claude-3,google/gemini-pro
```

**Notes:**
- Must still specify `--models` on command line if not set
- Useful for standard test suites

#### RANDOM_SEED

**Type:** Integer  
**Required:** No  
**Default:** (none - uses system random)

Seed for the random number generator used in answer randomization.

```env
RANDOM_SEED=42
```

**Use cases:**
- Reproducible experiments
- Debugging specific randomization scenarios
- Scientific comparisons

---

## Example Configurations

### Development Setup

```env
# Development configuration
OPENROUTER_API_KEY=sk-or-v1-dev-key

# Use local database
DATABASE_PATH=./data/dev.db

# Verbose logging
LOG_LEVEL=DEBUG
LOG_FILE_PATH=./logs/dev.log

# Quick tests
DEFAULT_ITERATIONS=1
```

### Production Setup

```env
# Production configuration
OPENROUTER_API_KEY=sk-or-v1-prod-key

# Centralized database
DATABASE_PATH=/var/data/benchmark_llm/prod.db

# Minimal logging
LOG_LEVEL=WARNING
LOG_FILE_PATH=/var/log/benchmark_llm/app.log

# Thorough testing
DEFAULT_ITERATIONS=5
RANDOM_SEED=42
```

### CI/CD Setup

```env
# CI/CD configuration
OPENROUTER_API_KEY=${CI_API_KEY}

# Temporary database
DATABASE_PATH=/tmp/benchmark_${CI_JOB_ID}.db

# Info logging for debugging
LOG_LEVEL=INFO
LOG_FILE_PATH=/tmp/benchmark_${CI_JOB_ID}.log

# Single iteration for speed
DEFAULT_ITERATIONS=1

# Fixed seed for reproducibility
RANDOM_SEED=12345
```

### Multi-Model Comparison

```env
# Standard model set
OPENROUTER_API_KEY=sk-or-v1-key

# Test common models
DEFAULT_MODELS=openai/gpt-4,openai/gpt-3.5-turbo,anthropic/claude-3-opus,anthropic/claude-3-sonnet,google/gemini-pro

# Multiple iterations for statistical significance
DEFAULT_ITERATIONS=5

# Reproducible randomization
RANDOM_SEED=42
```

---

## Troubleshooting Configuration

### Common Issues

#### API Key Not Found

**Error:** `Error: OpenRouter API key not configured`

**Solutions:**
1. Verify `.env` file exists in project root
2. Check `OPENROUTER_API_KEY` is set correctly
3. Ensure no trailing spaces in the value
4. Try setting via environment:
   ```bash
   export OPENROUTER_API_KEY=your-key
   ```

#### Database Permission Error

**Error:** `sqlite3.OperationalError: unable to open database file`

**Solutions:**
1. Check directory permissions:
   ```bash
   ls -la data/
   ```
2. Use absolute path:
   ```env
   DATABASE_PATH=/full/path/to/database.db
   ```
3. Ensure parent directory exists and is writable

#### Log File Not Created

**Issue:** Log file not appearing in expected location

**Solutions:**
1. Check `LOG_FILE_PATH` is absolute or relative to working directory
2. Verify parent directory exists:
   ```bash
   mkdir -p $(dirname ./logs/benchmark.log)
   ```
3. Check write permissions

#### Configuration Not Applied

**Issue:** Settings from `.env` not taking effect

**Solutions:**
1. Verify `.env` file is in project root
2. Check for typos in variable names
3. Ensure no BOM or encoding issues in `.env` file
4. Try explicit config file:
   ```bash
   python -m src.main --config .env --models openai/gpt-4
   ```

### Validation Commands

```bash
# Check environment variables
echo $OPENROUTER_API_KEY

# Verify .env file exists
ls -la .env

# Test database connectivity
sqlite3 data/benchmark.db "SELECT 1;"

# Check log file
tail -f logs/benchmark.log

# Run dry-run to validate configuration
python -m src.main --models openai/gpt-4 --dry-run
```

### Debug Mode

Enable maximum verbosity for troubleshooting:

```env
LOG_LEVEL=DEBUG
```

Then run with:

```bash
python -m src.main --models openai/gpt-4 --dry-run
```

Review `logs/benchmark.log` for detailed diagnostic information.

---

## Support

For additional configuration help:

1. Check [USAGE.md](./USAGE.md) for usage examples
2. Review [README.md](../README.md) for general information
3. Run `python -m src.main --help` for CLI reference
4. Open an issue on the GitHub repository
