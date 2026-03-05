# Technology Stack

## Core Language
- **Python 3.10+** - Modern Python with full async support and type hints

## HTTP Client & API
- **httpx** - Async HTTP client for OpenRouter API calls
- **OpenRouter API** - Unified API for accessing multiple LLM providers

## Data & Validation
- **pydantic** - Data validation and settings management
- **pydantic-settings** - Settings management from environment variables
- **Pillow (PIL)** - Image processing for multimodal questions

## Database
- **SQLite3** - Native Python database for storing experimental data

## Configuration & Environment
- **python-dotenv** - Environment variable management from `.env` files

## Logging
- **logging** (native) - Operational logs to `.log` files with RotatingFileHandler
- Custom loggers for separating operational vs. experimental data

## Testing
- **pytest** - Test framework
- **pytest-asyncio** - Async test support
- **pytest-mock** - Mocking utilities

## Utilities
- **rich** - Terminal output, progress bars, and tables
- **PyYAML** - Configuration file parsing (optional)

## Project Structure

```
src/
├── api/           # OpenRouter API client, retry logic, parsers
├── cli/           # CLI parser, statistics calculator, output formatter
├── core/          # Business logic (loader, filter, randomizer, executors)
├── db/            # Database schema, models, repositories
└── utils/         # Configuration, logging, image handler, progress
```
