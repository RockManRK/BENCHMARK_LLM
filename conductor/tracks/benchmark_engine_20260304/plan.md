# Implementation Plan: benchmark_engine_20260304

## Phase 1: Project Scaffolding [checkpoint: d1c06e5]

Setup project structure, dependencies, and configuration.

- [x] Task: Create project directory structure `4d3e5a7`
    - [x] Create `src/` directory with subdirectories
    - [x] Create `tests/` directory
    - [x] Create `logs/` directory
    - [x] Create `.env.example` file

- [x] Task: Create requirements.txt with all dependencies `e5f9745`
    - [x] httpx (async HTTP client)
    - [x] pydantic (data validation)
    - [x] pydantic-settings (settings management)
    - [x] Pillow (image processing)
    - [x] python-dotenv (environment management)
    - [x] rich (terminal output)
    - [x] pytest (testing framework)
    - [x] pytest-asyncio (async test support)
    - [x] pytest-mock (mocking utilities)

- [x] Task: Create configuration module `07f072c`
    - [x] Settings class using pydantic-settings
    - [x] Environment variable validation
    - [x] Default values for all config options

- [x] Task: Create .gitignore file `07f072c`
    - [x] Ignore .env, .log files, __pycache__, .pytest_cache, etc.

- [x] Task: Create initial README.md `a68bdff`
    - [x] Project description
    - [x] Installation instructions
    - [x] Configuration guide
    - [x] Basic usage example

- [x] Task: Conductor - User Manual Verification 'Project Scaffolding' (Protocol in workflow.md)

---

## Phase 2: Database Layer [checkpoint: 7432a5c]

Implement SQLite database schema and data access layer.

- [x] Task: Create database schema module `3494f8f`
    - [x] Define CREATE TABLE statements for all tables
    - [x] Implement database initialization function
    - [x] Create database connection manager

- [x] Task: Create models module (data classes) `3494f8f`
    - [x] Run model dataclass
    - [x] Question model dataclass
    - [x] Response model dataclass
    - [x] Error model dataclass
    - [x] Iteration model dataclass

- [x] Task: Create repository module (data access) `273c35f`
    - [x] RunRepository - CRUD operations for runs
    - [x] ModelRepository - CRUD operations for models
    - [x] ResponseRepository - CRUD operations for responses
    - [x] ErrorRepository - CRUD operations for errors
    - [x] IterationRepository - CRUD operations for iterations

- [x] Task: Create database tests `7432a5c`
    - [x] Test database initialization
    - [x] Test CRUD operations for each repository
    - [x] Test transaction handling

- [ ] Task: Conductor - User Manual Verification 'Database Layer' (Protocol in workflow.md)

---

## Phase 3: Data Loading Layer [checkpoint: ]

Implement questionnaire loading and parsing.

- [ ] Task: Create question loader module
    - [ ] Load JSON questionnaire from file
    - [ ] Validate JSON structure with pydantic
    - [ ] Parse question metadata (has_image, has_table, status)

- [ ] Task: Create question filter module
    - [ ] Filter by question ID(s)
    - [ ] Filter by metadata attributes
    - [ ] Filter by status (valid, annulled)

- [ ] Task: Create answer randomizer module
    - [ ] Implement Fisher-Yates shuffle for options
    - [ ] Track original letter mapping
    - [ ] Apply global seed from run_id for reproducibility
    - [ ] Remap answer keys after randomization

- [ ] Task: Create image handler module
    - [ ] Load image from file path
    - [ ] Encode image to base64
    - [ ] Validate image format and size
    - [ ] Handle missing image files gracefully

- [ ] Task: Create data loading tests
    - [ ] Test JSON loading with valid file
    - [ ] Test JSON loading with invalid file
    - [ ] Test question filtering
    - [ ] Test answer randomization (with seed verification)
    - [ ] Test image encoding

- [ ] Task: Conductor - User Manual Verification 'Data Loading Layer' (Protocol in workflow.md)

---

## Phase 4: OpenRouter API Client [checkpoint: f6c254b]

Implement API integration with retry logic.

- [x] Task: Create API client module `f6c254b`
    - [x] Initialize httpx AsyncClient
    - [x] Implement authentication with API key
    - [x] Create chat completion request builder
    - [x] Handle text-only messages
    - [x] Handle multimodal messages (text + image)

- [x] Task: Implement retry logic `f6c254b`
    - [x] Exponential backoff strategy
    - [x] Handle rate limiting (429)
    - [x] Handle timeouts
    - [x] Maximum retry count configuration
    - [x] Log retry attempts

- [x] Task: Implement response parser `f6c254b`
    - [x] Parse successful responses
    - [x] Extract selected answer from response text
    - [x] Extract token usage (input/output)
    - [x] Extract latency
    - [x] Handle malformed responses

- [x] Task: Implement model capability checker `f6c254b`
    - [x] Check if model supports vision/images
    - [x] Mark questions as "unsupported" for incompatible models
    - [x] Cache model capabilities

- [x] Task: Create API client tests `f6c254b`
    - [x] Test successful API call (mocked)
    - [x] Test retry logic (mocked failures)
    - [x] Test rate limit handling
    - [x] Test response parsing
    - [x] Test image message formatting

- [ ] Task: Conductor - User Manual Verification 'OpenRouter API Client' (Protocol in workflow.md)

---

## Phase 5: Test Execution Engine [checkpoint: ]

Implement core test orchestration.

- [ ] Task: Create run manager module
    - [ ] Initialize new run with unique run_id
    - [ ] Store run configuration
    - [ ] Track run status

- [ ] Task: Create iteration executor module
    - [ ] Execute single iteration for a model
    - [ ] Track iteration progress
    - [ ] Handle iteration-level errors

- [ ] Task: Create question executor module
    - [ ] Execute single question
    - [ ] Apply answer randomization
    - [ ] Build API request
    - [ ] Send request and capture response
    - [ ] Store response in database
    - [ ] Handle and log errors

- [ ] Task: Create progress tracker module
    - [ ] Display progress bar with rich
    - [ ] Show current question/model/iteration
    - [ ] Estimate time remaining
    - [ ] Log progress to operational log

- [ ] Task: Create execution tests
    - [ ] Test full execution flow (mocked API)
    - [ ] Test error handling during execution
    - [ ] Test progress tracking
    - [ ] Test database writes during execution

- [ ] Task: Conductor - User Manual Verification 'Test Execution Engine' (Protocol in workflow.md)

---

## Phase 6: Logging & Error Handling [checkpoint: ]

Implement comprehensive logging and error management.

- [ ] Task: Create logging configuration module
    - [ ] Configure operational log file handler
    - [ ] Set log levels (DEBUG, INFO, WARNING, ERROR)
    - [ ] Create structured log format
    - [ ] Implement log rotation

- [ ] Task: Create error collector module
    - [ ] Capture error details
    - [ ] Classify error types
    - [ ] Store errors in database
    - [ ] Generate error summaries

- [ ] Task: Implement structured logging
    - [ ] Log all API requests (endpoint, model, timestamp)
    - [ ] Log all responses (status, tokens, latency)
    - [ ] Log execution progress
    - [ ] Log configuration at startup

- [ ] Task: Create logging tests
    - [ ] Test log file creation
    - [ ] Test log rotation
    - [ ] Test error capture and storage
    - [ ] Test log format and content

- [ ] Task: Conductor - User Manual Verification 'Logging & Error Handling' (Protocol in workflow.md)

---

## Phase 7: CLI & Basic Statistics [checkpoint: 9b8294e]

Implement command-line interface and basic output.

- [x] Task: Create CLI module `9b8294e`
    - [x] Parse command-line arguments
    - [x] Support model selection (--models)
    - [x] Support iteration count (--iterations)
    - [x] Support question filtering (--questions)
    - [x] Support config file (--config)

- [x] Task: Create statistics module `9b8294e`
    - [x] Calculate accuracy per model
    - [x] Calculate average latency per model
    - [x] Calculate token usage statistics
    - [x] Calculate consistency across iterations
    - [x] Generate error summary

- [x] Task: Create output formatter `9b8294e`
    - [x] Console output with rich tables
    - [x] JSON export option
    - [x] CSV export option
    - [x] Markdown summary export

- [x] Task: Create main entry point `9b8294e`
    - [x] Wire up CLI to execution engine
    - [x] Handle graceful shutdown
    - [x] Display final statistics
    - [x] Log completion summary

- [x] Task: Create CLI tests `9b8294e`
    - [x] Test argument parsing
    - [x] Test statistics calculations
    - [x] Test output formatting
    - [x] Test end-to-end execution (mocked)

- [ ] Task: Conductor - User Manual Verification 'CLI & Basic Statistics' (Protocol in workflow.md)

---

## Phase 8: Integration & Documentation [checkpoint: ]

Final integration testing and documentation.

- [ ] Task: Create integration tests
    - [ ] Test full workflow with mocked API
    - [ ] Test with real API (optional, requires key)
    - [ ] Test database integrity after full run
    - [ ] Test error recovery scenarios

- [ ] Task: Create usage documentation
    - [ ] Write detailed README usage section
    - [ ] Create example configuration files
    - [ ] Document all CLI options
    - [ ] Add troubleshooting guide

- [ ] Task: Create API documentation
    - [ ] Document all public functions
    - [ ] Add usage examples to docstrings
    - [ ] Generate API docs (optional: pdoc)

- [ ] Task: Final code review
    - [ ] Verify type hints on all functions
    - [ ] Verify docstrings follow Google style
    - [ ] Check code coverage (>80%)
    - [ ] Run linter (flake8/ruff)
    - [ ] Fix all warnings

- [ ] Task: Conductor - User Manual Verification 'Integration & Documentation' (Protocol in workflow.md)
