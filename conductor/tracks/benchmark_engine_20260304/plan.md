# Implementation Plan: benchmark_engine_20260304

## Phase 1: Project Scaffolding [checkpoint: ]

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

## Phase 2: Database Layer [checkpoint: ]

Implement SQLite database schema and data access layer.

- [ ] Task: Create database schema module
    - [ ] Define CREATE TABLE statements for all tables
    - [ ] Implement database initialization function
    - [ ] Create database connection manager

- [ ] Task: Create models module (data classes)
    - [ ] Run model dataclass
    - [ ] Question model dataclass
    - [ ] Response model dataclass
    - [ ] Error model dataclass
    - [ ] Iteration model dataclass

- [ ] Task: Create repository module (data access)
    - [ ] RunRepository - CRUD operations for runs
    - [ ] ModelRepository - CRUD operations for models
    - [ ] ResponseRepository - CRUD operations for responses
    - [ ] ErrorRepository - CRUD operations for errors
    - [ ] IterationRepository - CRUD operations for iterations

- [ ] Task: Create database tests
    - [ ] Test database initialization
    - [ ] Test CRUD operations for each repository
    - [ ] Test transaction handling

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

## Phase 4: OpenRouter API Client [checkpoint: ]

Implement API integration with retry logic.

- [ ] Task: Create API client module
    - [ ] Initialize httpx AsyncClient
    - [ ] Implement authentication with API key
    - [ ] Create chat completion request builder
    - [ ] Handle text-only messages
    - [ ] Handle multimodal messages (text + image)

- [ ] Task: Implement retry logic
    - [ ] Exponential backoff strategy
    - [ ] Handle rate limiting (429)
    - [ ] Handle timeouts
    - [ ] Maximum retry count configuration
    - [ ] Log retry attempts

- [ ] Task: Implement response parser
    - [ ] Parse successful responses
    - [ ] Extract selected answer from response text
    - [ ] Extract token usage (input/output)
    - [ ] Extract latency
    - [ ] Handle malformed responses

- [ ] Task: Implement model capability checker
    - [ ] Check if model supports vision/images
    - [ ] Mark questions as "unsupported" for incompatible models
    - [ ] Cache model capabilities

- [ ] Task: Create API client tests
    - [ ] Test successful API call (mocked)
    - [ ] Test retry logic (mocked failures)
    - [ ] Test rate limit handling
    - [ ] Test response parsing
    - [ ] Test image message formatting

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

## Phase 7: CLI & Basic Statistics [checkpoint: ]

Implement command-line interface and basic output.

- [ ] Task: Create CLI module
    - [ ] Parse command-line arguments
    - [ ] Support model selection (--models)
    - [ ] Support iteration count (--iterations)
    - [ ] Support question filtering (--questions)
    - [ ] Support config file (--config)

- [ ] Task: Create statistics module
    - [ ] Calculate accuracy per model
    - [ ] Calculate average latency per model
    - [ ] Calculate token usage statistics
    - [ ] Calculate consistency across iterations
    - [ ] Generate error summary

- [ ] Task: Create output formatter
    - [ ] Console output with rich tables
    - [ ] JSON export option
    - [ ] CSV export option
    - [ ] Markdown summary export

- [ ] Task: Create main entry point
    - [ ] Wire up CLI to execution engine
    - [ ] Handle graceful shutdown
    - [ ] Display final statistics
    - [ ] Log completion summary

- [ ] Task: Create CLI tests
    - [ ] Test argument parsing
    - [ ] Test statistics calculations
    - [ ] Test output formatting
    - [ ] Test end-to-end execution (mocked)

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
