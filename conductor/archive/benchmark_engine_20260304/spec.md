# Track Specification: benchmark_engine_20260304

## Overview

Build a Python-based benchmark tool that evaluates LLM performance by administering a 100-question medical questionnaire (including 3 image-based questions) through the OpenRouter API.

## Objectives

1. **Core Architecture**: Modular Python codebase with clean separation of concerns
2. **API Integration**: OpenRouter API client with support for multiple LLM providers
3. **Data Persistence**: SQLite3 database for comprehensive metrics storage
4. **Test Execution**: Configurable test runs with iteration support
5. **Reliability**: Retry logic, error handling, and operational logging

## Scope

### In Scope
- Load and parse JSON questionnaire (100 questions, 3 with images)
- Configure test parameters (models, iterations, question filters)
- Execute tests via OpenRouter API
- Collect comprehensive metrics (response, latency, tokens, errors)
- Store all data in SQLite database
- Implement retry logic with exponential backoff
- Handle multimodal questions (text + image)
- Randomize answer order with proper letter remapping
- Basic statistical output

### Out of Scope (Future Tracks)
- Advanced analytics dashboard
- HTML/visual reports
- Multi-user support
- Real-time monitoring interface

## Technical Requirements

### Language & Runtime
- Python 3.10+
- Type hints on all functions
- Google-style docstrings

### Dependencies
- `httpx` - Async HTTP client
- `pydantic` - Data validation
- `Pillow` - Image processing
- `python-dotenv` - Environment management
- `rich` - Progress bars and terminal output
- `pytest` + `pytest-asyncio` - Testing

### Database Schema

**runs**
- `run_id` (TEXT PRIMARY KEY)
- `created_at` (TIMESTAMP)
- `config` (TEXT - JSON)
- `status` (TEXT)

**models**
- `model_id` (TEXT PRIMARY KEY)
- `model_name` (TEXT)
- `provider` (TEXT)

**iterations**
- `iteration_id` (INTEGER PRIMARY KEY AUTOINCREMENT)
- `run_id` (TEXT)
- `model_id` (TEXT)
- `iteration_number` (INTEGER)
- `started_at` (TIMESTAMP)
- `completed_at` (TIMESTAMP)
- `status` (TEXT)

**responses**
- `response_id` (INTEGER PRIMARY KEY AUTOINCREMENT)
- `iteration_id` (INTEGER)
- `question_id` (TEXT)
- `model_id` (TEXT)
- `run_id` (TEXT)
- `question_text` (TEXT)
- `options_json` (TEXT)
- `options_randomized` (BOOLEAN)
- `selected_answer` (TEXT)
- `correct_answer` (TEXT)
- `is_correct` (BOOLEAN)
- `response_text` (TEXT)
- `input_tokens` (INTEGER)
- `output_tokens` (INTEGER)
- `latency_ms` (INTEGER)
- `timestamp` (TIMESTAMP)
- `status` (TEXT: success/error/unsupported)

**errors**
- `error_id` (INTEGER PRIMARY KEY AUTOINCREMENT)
- `response_id` (INTEGER)
- `error_type` (TEXT)
- `error_message` (TEXT)
- `stack_trace` (TEXT)
- `timestamp` (TIMESTAMP)

**operational_logs**
- `log_id` (INTEGER PRIMARY KEY AUTOINCREMENT)
- `run_id` (TEXT)
- `level` (TEXT)
- `message` (TEXT)
- `timestamp` (TIMESTAMP)

## API Integration

### OpenRouter Endpoints
- Base URL: `https://openrouter.ai/api/v1`
- Chat Completions: `POST /chat/completions`
- Models List: `GET /models`

### Request Format
```json
{
  "model": "provider/model-name",
  "messages": [
    {
      "role": "user",
      "content": [
        {"type": "text", "text": "..."},
        {"type": "image_url", "image_url": {"url": "data:image/..."}}
      ]
    }
  ],
  "max_tokens": 100
}
```

## Error Handling

### Critical Errors (Halt Execution)
- API authentication failure
- Database connection failure
- Configuration file missing

### Recoverable Errors (Retry)
- API rate limiting (429)
- Network timeouts
- Temporary service unavailability

### Per-Question Errors (Continue)
- Model doesn't support images
- Invalid response format
- Individual question failures

## Logging Strategy

### Operational Logs → `.log` files
- Progress updates
- Error summaries
- Status changes
- Configuration info

### Experimental Data → SQLite
- Full request/response data
- All metrics
- Error details
- Timing information

## Success Criteria

1. All 100 questions can be loaded and parsed
2. API integration works with at least 2 different LLM providers
3. All metrics are captured and stored in SQLite
4. Retry logic handles transient failures
5. Image-based questions are properly handled
6. Answer randomization works with correct letter remapping
7. Basic statistics can be generated from stored data

## Constraints

- Must use native SQLite3 (no ORM)
- All secrets via environment variables
- Operational logs to files, experimental data to database
- Images referenced by path only (no binary storage)
- Global random seed for reproducibility
