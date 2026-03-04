# Product Guidelines

## 1. Code Style & Documentation

### Standards
- **PEP 8 Compliance** - All code must follow PEP 8 style guidelines
- **Type Hints** - Full type annotations for all function parameters and return values
- **Google Style Docstrings** - Comprehensive docstrings with Args, Returns, Raises, and Examples

### Documentation Requirements
- Every module must have a module-level docstring describing its purpose
- Every public function/class must have a docstring
- Docstrings must include:
  - Brief description of purpose
  - Args section with parameter descriptions and types
  - Returns section with return value description and type
  - Raises section listing exceptions that may be raised
  - Examples section with usage examples (where applicable)

### Code Organization
- Clean, readable function names that describe intent
- Logical grouping of related functions into modules
- Maximum function length: 50 lines (extract helper functions when longer)
- Single Responsibility Principle for all functions and classes

---

## 2. Error Handling Philosophy

### Hybrid Approach

**Critical Paths (Strict Mode)**
- API authentication failures → Raise exception immediately
- Database connection failures → Raise exception, halt execution
- Data corruption detected → Raise exception, prevent invalid operations
- Missing required configuration → Raise exception with clear message

**Non-Critical Paths (Graceful Degradation)**
- Individual API request failures → Retry with exponential backoff
- Single question failures → Log error, continue with next question
- Non-fatal warnings → Log warning, continue execution
- Rate limiting → Implement retry-after handling

### Error Logging
- All errors must be logged with full context
- Error entries in database must include:
  - Timestamp
  - Error type and message
  - Stack trace (for critical errors)
  - Related entity (model, question, iteration)
  - Recovery action taken (if any)

---

## 3. Testing Philosophy

### Integration-Focused Testing

**Priority: End-to-End Flow Tests**
- Dataset loading and parsing
- Question selection and filtering
- API request/response cycle (with mocked responses)
- Answer validation and comparison
- Database persistence and retrieval
- Report generation

**Test Coverage Areas**
1. **Data Flow Tests**
   - Load JSON questionnaire
   - Parse question metadata
   - Handle image-based questions
   - Handle text-only questions

2. **API Integration Tests**
   - Mock OpenRouter API responses
   - Test retry logic
   - Test rate limiting handling
   - Test error responses

3. **Database Tests**
   - Schema creation
   - Data insertion
   - Query operations
   - Data integrity

### Minimal Unit Tests

**Core Utilities**
- JSON parser validation
- Answer normalization functions
- Accuracy calculation logic
- Randomization with letter remapping

**Test Guidelines**
- Tests must be deterministic (except where testing randomness)
- Mock external dependencies (APIs, network)
- Use fixtures for common test data
- Aim for >80% coverage on critical paths

---

## 4. Data & Privacy

### Secrets Management
- **Environment Variables** for all sensitive data:
  - `OPENROUTER_API_KEY`
  - Database paths (if sensitive)
  - Any third-party credentials
- `.env` file support via `python-dotenv`
- `.env` must be in `.gitignore`

### Logging Strategy

**Audit Trail Requirements**
- Log all API requests (endpoint, model, timestamp)
- Log all responses (status, tokens, latency)
- Log all errors with full context
- Log test execution progress

**Privacy Considerations**
- Do NOT log API keys or secrets
- Do NOT log full question/response content in production logs
- Use reference IDs in logs (link to database for full content)
- Sensitive data only in SQLite database

### Database Security
- SQLite file should be stored in secure location
- Consider encryption for production deployments
- Regular backups recommended for long-running tests

---

## 5. Performance Guidelines

### Efficiency Requirements
- Stream responses when possible (reduce memory usage)
- Batch database writes (don't write every single record immediately)
- Implement connection pooling for database
- Use async/await for API calls where beneficial

### Resource Management
- Close database connections properly
- Handle large datasets with generators/iterators
- Implement progress tracking for long-running operations
- Memory-efficient image encoding for multimodal questions

---

## 6. Maintainability

### Code Review Checklist
- [ ] Type hints present and correct
- [ ] Docstrings follow Google style
- [ ] Error handling appropriate for context
- [ ] Logging sufficient for debugging
- [ ] Tests cover critical paths
- [ ] No hardcoded values (use config/env)
- [ ] Function names are descriptive
- [ ] No unnecessary complexity

### Version Control
- Descriptive commit messages
- Feature branches for new functionality
- Code review before merging
- Changelog for significant changes
