# Async Refactoring: Lifecycle + Incremental Persistence

**Document Type:** Design Document  
**Project:** Benchmark LLM V2  
**Version:** 1.0  
**Date:** 2026-04-04  
**Status:** Approved  

---

## Summary

Refactor the async execution model to fix the `Event loop is closed` bug, introduce incremental result persistence, and prepare the architecture for future parallelism — all while keeping the ExecutionEngine pure and decoupled from the database.

---

## Root Cause

`asyncio.run()` is called once per item, creating and closing an event loop per item. The shared `httpx.AsyncClient` becomes associated with the first loop, which is then closed. Subsequent items find the client in an inconsistent state.

---

## Architecture: After

```
bcllm_execute.py (sync)
  └─ AsyncOrchestrator.execute(plan)
       └─ asyncio.run(_execute_async())    ← SINGLE EVENT LOOP
            ├─ httpx.AsyncClient()         ← created INSIDE the loop
            ├─ asyncio.Queue()             ← shared result queue
            ├─ AsyncWriter()               ← consumes queue → DB
            └─ ExecutionEngine.execute_async()
                 └─ for each item:
                      └─ await queue.put(result)  ← incremental
```

---

## Key Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Entry point owner | AsyncOrchestrator | CLI stays sync; clean bridge |
| httpx lifecycle | Created inside asyncio.run(), closed after all items | Never crosses loop boundaries |
| Engine API | async def execute_async() | Clean async surface |
| Persistence | asyncio.Queue → AsyncWriter | Engine stays DB-free |
| Parallelism path | concurrency param + asyncio.Semaphore | Natural progression to TaskGroup |

## Shutdown Order Guarantee

1. Engine completes → all results on queue
2. Sentinel (None) put on queue
3. Writer drains queue → completes
4. httpx.AsyncClient closed
5. asyncio.run() returns → loop closes

---

## Out of Scope

- Actual parallelism (concurrency stays at 1)
- Database schema changes
- Prompt/message building changes
- Answer parsing changes
