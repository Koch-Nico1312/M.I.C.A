# Changelog

All notable changes to the M.I.C.A AI Assistant project will be documented in this file.

## [Unreleased] - 2026-06-01

### Assistant Runtime Hardening

- Added first-run API key and model setup support with a safe `config/api_keys.example.json`.
- Wired routed model preferences and Gemini/Ollama fallback behavior into the runtime model path.
- Added Memory management to the React dashboard for viewing, editing, exporting, and forgetting entries.
- Added central tool approval checks and action-history recording in `core/tool_executor.py`.
- Expanded dashboard telemetry with device status, sessions, file-transfer history, tool history, approvals, and permissions.
- Added a local contact manager integration backed by `data/contacts.json`.
- Added a local release archive script and release documentation.

### Performance Optimizations - Phase 3 (Complex Architectural Changes)

This release implements 6 complex architectural performance optimizations as part of the performance improvement initiative. All optimizations are behind feature flags for safe gradual rollout.

#### Phase 3 Optimizations

1. **Reduce Memory Footprint** (`core/memory_manager.py`, `main.py`)
   - Created memory manager with weak references and LRU cache
   - Implemented periodic garbage collection with configurable interval
   - Added memory limit enforcement with automatic cache clearing
   - **Feature Flag**: `performance.flags.reduce_memory_footprint`
   - **Metrics**: Memory usage, GC frequency, object count, cache evictions
   - **Expected Impact**: Reduced memory footprint, automatic memory management

2. **Parallel Tool Execution** (`core/tool_executor.py`)
   - Implemented parallel tool execution with asyncio.gather
   - Execute independent tools concurrently (max 4 parallel)
   - Dependency-aware task scheduling
   - **Feature Flag**: `performance.flags.parallel_tool_execution`
   - **Metrics**: Tool execution time, CPU usage, throughput, parallel task count
   - **Expected Impact**: 30-50% faster multi-tool workflows

3. **Optimise Workflow Engine (async task queue)** (`core/workflow_engine.py`)
   - Implemented async task queue for workflow steps
   - Execute independent workflow steps in parallel (max 4 concurrent)
   - Added async event loop per workflow for parallel execution
   - **Feature Flag**: `performance.flags.async_workflow_engine`
   - **Metrics**: Workflow execution time, CPU usage, throughput, parallel step count
   - **Expected Impact**: 40-60% faster workflow execution for multi-step workflows

4. **Precompute Common Queries** (`core/semantic_search.py`)
   - Implemented precomputed query cache for common queries
   - Precompute 5 common queries on startup
   - Fuzzy matching for partial query matches
   - **Feature Flag**: `performance.flags.precompute_queries`
   - **Metrics**: Query latency, cache hit rate, memory
   - **Expected Impact**: Instant response for common queries

5. **Implement Response Streaming** (`core/response_streamer.py`)
   - Created response streamer for token-by-token streaming
   - Stream text in configurable chunks (default 10 tokens)
   - Optional callback for each chunk
   - **Feature Flag**: `performance.flags.response_streaming`
   - **Metrics**: Time to first token, tokens per second, memory
   - **Expected Impact**: Reduced perceived latency, better user experience

6. **Async/IO in ui_bridge.py (migrate to aiohttp)** (`ui_bridge.py`)
   - Added async support to HTTP request handlers
   - Run handlers in event loop when feature flag enabled
   - Fallback to synchronous execution on error
   - **Feature Flag**: `performance.flags.async_ui_server`
   - **Metrics**: Request latency, throughput, memory
   - **Expected Impact**: Reduced blocking I/O, improved concurrency

### Configuration Changes

To enable Phase 3 optimizations, set the corresponding flags in `config.yaml`:

```yaml
performance:
  flags:
    reduce_memory_footprint: true
    parallel_tool_execution: true
    async_workflow_engine: true
    precompute_queries: true
    response_streaming: true
    async_ui_server: true
```

### Testing

All optimizations include:
- Performance metrics collection before/after changes
- Feature flag checks for gradual rollout
- Thread-safe implementations where applicable
- Error handling and fallback mechanisms
- Async/await pattern for I/O operations

### Migration Notes

- No breaking changes
- All optimizations are opt-in via feature flags
- Existing functionality preserved when flags are disabled
- New dependencies: None (uses existing asyncio)
- Memory manager requires psutil for memory tracking (optional)

### Next Steps

Phase 3 complete. Total progress: 20/20 optimizations implemented across all phases.

---

## [Unreleased] - 2026-06-01

### Performance Optimizations - Phase 2 (Medium Impact)

This release implements 7 medium-impact performance optimizations as part of the performance improvement initiative. All optimizations are behind feature flags for safe gradual rollout.

#### Phase 2 Optimizations

1. **Lazy Load Actions** (`core/action_loader.py`, `main.py`)
   - Created dynamic action loader with module-level caching
   - Actions imported only when needed
   - Preload critical actions on startup
   - **Feature Flag**: `performance.flags.lazy_load_actions`
   - **Metrics**: Startup time, memory usage, cache hit rate
   - **Expected Impact**: Reduced startup time, lower memory footprint

2. **Connection Pooling for External APIs** (`core/http_pool.py`)
   - Created HTTP connection pool with aiohttp ClientSession
   - Max 10 connections per pool, 5 per host
   - Shared session across API clients
   - **Feature Flag**: `performance.flags.connection_pooling`
   - **Metrics**: Connection count, request latency, memory
   - **Expected Impact**: Reduced connection overhead, faster API calls

3. **Memory Compression (aggressive)** (`memory/conversation_compression.py`)
   - Implemented Zstandard compression for old conversations (> 24h)
   - Added token limit enforcement (1000 tokens per message)
   - Updated database schema to store compression method
   - **Feature Flag**: `performance.flags.aggressive_compression`
   - **Metrics**: Storage size, compression ratio, decompression time
   - **Expected Impact**: 70-80% additional storage savings for old conversations

4. **Database Connection Pooling** (`memory/conversation_compression.py`, `core/semantic_search.py`)
   - Implemented SQLite connection pool with max 10 connections
   - ChromaDB client reuse for vector DB
   - Thread-safe connection management
   - **Feature Flag**: `performance.flags.db_connection_pooling`
   - **Metrics**: Connection count, query latency, memory
   - **Expected Impact**: Reduced connection overhead, faster queries

5. **Vector DB Caching** (`core/vector_cache.py`, `core/semantic_search.py`)
   - Created Redis-based cache for ChromaDB query results
   - 1-hour TTL for cached results
   - Hash-based cache keys for query matching
   - In-memory fallback if Redis unavailable
   - **Feature Flag**: `performance.flags.vector_db_cache`
   - **Metrics**: Cache hit rate, query latency, memory
   - **Expected Impact**: Reduced redundant vector searches, faster response times

6. **Batch Processing for Screen Captures** (`core/passive_vision.py`)
   - Implemented parallel OCR and hash computation
   - Used ThreadPoolExecutor for concurrent processing
   - Reduced screen capture processing time
   - **Feature Flag**: `performance.flags.batch_screen_processing`
   - **Metrics**: Processing time, CPU usage, throughput
   - **Expected Impact**: 30-40% faster screen capture processing

7. **Optimise File Watching (event-based)** (`memory/obsidian_vault.py`)
   - Implemented watchdog-based event-driven file watching
   - Replaced polling with inotify-based events
   - Added VaultFileHandler for file change events
   - **Feature Flag**: `performance.flags.event_file_watching`
   - **Metrics**: File watch events, CPU usage, latency
   - **Expected Impact**: Reduced CPU usage, instant file change detection

### Configuration Changes

To enable Phase 2 optimizations, set the corresponding flags in `config.yaml`:

```yaml
performance:
  flags:
    lazy_load_actions: true
    connection_pooling: true
    aggressive_compression: true
    db_connection_pooling: true
    vector_db_cache: true
    batch_screen_processing: true
    event_file_watching: true
```

### Testing

All optimizations include:
- Performance metrics collection before/after changes
- Feature flag checks for gradual rollout
- Thread-safe implementations where applicable
- Error handling and fallback mechanisms

### Migration Notes

- No breaking changes
- All optimizations are opt-in via feature flags
- Existing functionality preserved when flags are disabled
- New dependencies added to requirements.txt (watchdog, zstandard)
- Database schema updated with compression_method column

### Next Steps

Phase 3 will implement complex architectural changes:
- Reduce Memory Footprint
- Parallel Tool Execution
- Optimise Workflow Engine (async task queue)
- Precompute Common Queries
- Implement Response Streaming
- Async/IO in ui_bridge.py (migrate to aiohttp)

---

## [Unreleased] - 2026-06-01

### Performance Optimizations - Phase 1 (Quick Wins)

This release implements 7 high-impact, low-effort performance optimizations as part of the performance improvement initiative. All optimizations are behind feature flags for safe gradual rollout.

#### Infrastructure

- **Added Performance Flags System** (`core/performance_flags.py`)
  - Centralized feature flag management for performance optimizations
  - All flags configurable via `config.yaml` under `performance.flags` section
  - Default: All flags disabled for safe rollout

- **Added Metrics Collector** (`core/metrics_collector.py`)
  - Performance metrics collection before/after each optimization
  - Tracks latency, memory usage, CPU usage, and custom metrics
  - Baseline comparison and statistics generation

- **Updated Configuration** (`config.yaml`)
  - Added `performance.flags` section with 20 feature flags
  - All flags default to `false` for safe gradual rollout

- **Updated Dependencies** (`requirements.txt`)
  - Added `aiohttp>=3.9.0` for async HTTP operations
  - Added `watchdog>=3.0.0` for event-based file watching
  - Added `zstandard>=0.22.0` for improved compression
  - Added `redis>=5.0.0` (optional) for vector DB caching

#### Phase 1 Optimizations

1. **Caching for System Prompt** (`main.py`, `core/jarvis_live.py`)
   - Implemented LRU cache with 5-minute TTL for system prompt
   - Cache invalidated on file modification
   - Thread-safe implementation with lock
   - **Feature Flag**: `performance.flags.cache_system_prompt`
   - **Metrics**: File I/O operations, prompt load time, cache hit rate
   - **Expected Impact**: Reduced file I/O, faster startup

2. **Lazy Loading for Tool Declarations** (`main.py`)
   - Implemented lazy loading for TOOL_DECLARATIONS
   - Declarations cached after first load
   - Thread-safe implementation with lock
   - **Feature Flag**: `performance.flags.lazy_tool_declarations`
   - **Metrics**: Import time, memory usage at startup
   - **Expected Impact**: Reduced startup time, lower memory footprint

3. **Optimise Audio Chunk Processing** (`core/audio_handler.py`)
   - Increased chunk size from 1024 to 4096 bytes
   - Implemented double buffering with two queues
   - Reduced context switches in audio processing
   - **Feature Flag**: `performance.flags.optimized_audio_chunks`
   - **Metrics**: Audio latency, CPU usage, context switches
   - **Expected Impact**: Lower audio latency, reduced CPU overhead

4. **Cache API Responses** (`core/api_cache.py`, `core/jarvis_live.py`)
   - Created API response cache with LRU eviction
   - 10-minute TTL for cached responses
   - Hash-based cache keys for prompt matching
   - **Feature Flag**: `performance.flags.cache_api_responses`
   - **Metrics**: API call count, response time, cache hit rate
   - **Expected Impact**: Reduced API calls, faster response times for repeated queries

5. **Preload Embedding Model** (`core/semantic_search.py`)
   - Implemented singleton pattern for embedding model
   - Model preloaded at startup when flag enabled
   - Warmup call to initialize model
   - **Feature Flag**: `performance.flags.preload_embedding_model`
   - **Metrics**: First search latency, memory usage
   - **Expected Impact**: Eliminated first-search latency

6. **Optimise UI State Updates** (`ui_bridge.py`)
   - Implemented debouncing with 1-second interval
   - State updates only when state actually changes
   - Hash-based state comparison
   - Dirty flag for state tracking
   - **Feature Flag**: `performance.flags.debounce_ui_updates`
   - **Metrics**: Network traffic, CPU usage, update frequency
   - **Expected Impact**: Reduced network traffic, lower CPU usage

7. **Reduce Logging Overhead** (`core/logger.py`)
   - Implemented async logging with QueueHandler
   - Background writer thread for log processing
   - Non-blocking log operations
   - **Feature Flag**: `performance.flags.async_logging`
   - **Metrics**: Logging latency, blocking time
   - **Expected Impact**: Reduced blocking time, improved responsiveness

### Configuration Changes

To enable individual optimizations, set the corresponding flag in `config.yaml`:

```yaml
performance:
  flags:
    cache_system_prompt: true
    lazy_tool_declarations: true
    optimized_audio_chunks: true
    cache_api_responses: true
    preload_embedding_model: true
    debounce_ui_updates: true
    async_logging: true
```

### Testing

All optimizations include:
- Performance metrics collection before/after changes
- Feature flag checks for gradual rollout
- Thread-safe implementations where applicable
- Error handling and fallback mechanisms

### Migration Notes

- No breaking changes
- All optimizations are opt-in via feature flags
- Existing functionality preserved when flags are disabled
- New dependencies added to requirements.txt

### Next Steps

Phase 2 will implement medium-impact optimizations:
- Lazy Load Actions
- Connection Pooling for External APIs
- Memory Compression (aggressive)
- Database Connection Pooling
- Vector DB Caching
- Batch Processing for Screen Captures
- Optimise File Watching (event-based)

Phase 3 will implement complex architectural changes:
- Reduce Memory Footprint
- Parallel Tool Execution
- Optimise Workflow Engine (async task queue)
- Precompute Common Queries
- Implement Response Streaming
- Async/IO in ui_bridge.py (migrate to aiohttp)
