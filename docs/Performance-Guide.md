# JARVIS AI Assistant - Performance Guide

This guide provides comprehensive information about optimizing JARVIS performance, monitoring system resources, and troubleshooting performance issues.

## Table of Contents

- [Performance Overview](#performance-overview)
- [Feature Flags](#feature-flags)
- [Caching Strategies](#caching-strategies)
- [Memory Management](#memory-management)
- [Resource Monitoring](#resource-monitoring)
- [Performance Optimization](#performance-optimization)
- [Benchmarking](#benchmarking)
- [Performance Tuning](#performance-tuning)

## Performance Overview

JARVIS uses a multi-layered performance optimization strategy:

1. **Feature Flags**: Enable/disable performance optimizations
2. **Caching**: Reduce redundant computations
3. **Lazy Loading**: Load resources on-demand
4. **Resource Monitoring**: Track system usage
5. **Background Tasks**: Offload work to background threads

## Feature Flags

Feature flags control performance optimizations in `config.yaml`:

```yaml
performance:
  flags:
    lazy_tool_declarations: true
    cache_system_prompt: true
    lazy_load_actions: true
    reduce_memory_footprint: false
```

### Lazy Tool Declarations

**Purpose**: Load tool declarations on first use instead of at startup

**When to Enable**: 
- Slow startup times
- Many tools registered
- Limited memory at startup

**Configuration**:
```yaml
performance:
  flags:
    lazy_tool_declarations: true
```

**Impact**:
- Startup: Faster
- First tool use: Slightly slower
- Memory: Lower initial footprint

### Cache System Prompt

**Purpose**: Cache the system prompt with 5-minute TTL

**When to Enable**:
- Frequent AI interactions
- Stable system prompt
- Reduced file I/O desired

**Configuration**:
```yaml
performance:
  flags:
    cache_system_prompt: true
```

**Impact**:
- AI calls: Faster (no file read)
- Memory: Slightly higher
- Freshness: 5-minute delay for prompt updates

### Lazy Load Actions

**Purpose**: Load action modules on-demand

**When to Enable**:
- Many action modules
- Not all actions used frequently
- Faster startup desired

**Configuration**:
```yaml
performance:
  flags:
    lazy_load_actions: true
```

**Impact**:
- Startup: Faster
- First action use: Slightly slower
- Memory: Lower initial footprint

### Reduce Memory Footprint

**Purpose**: Enable aggressive memory management

**When to Enable**:
- High memory usage
- Memory-constrained environment
- Long-running sessions

**Configuration**:
```yaml
performance:
  flags:
    reduce_memory_footprint: true
```

**Impact**:
- Memory: Significantly lower
- CPU: Slightly higher (GC overhead)
- Latency: Minimal impact

## Caching Strategies

### System Prompt Caching

The system prompt is cached with a 5-minute TTL:

```python
from config.startup_config import load_system_prompt

# First call: loads from file
prompt1 = load_system_prompt()

# Subsequent calls within 5 minutes: uses cache
prompt2 = load_system_prompt()
```

Cache is invalidated if:
- 5 minutes elapsed
- File modified
- Cache cleared

### Tool Declaration Caching

Tool declarations can be cached when lazy loading is enabled:

```python
from main import get_tool_declarations

# First call: loads and caches
tools1 = get_tool_declarations()

# Subsequent calls: uses cache
tools2 = get_tool_declarations()
```

### Custom Caching

Implement custom caching for expensive operations:

```python
from functools import lru_cache
from datetime import datetime, timedelta

@lru_cache(maxsize=128)
def expensive_operation(param):
    # Expensive computation
    return result
```

## Memory Management

### Conversation Memory

Conversation memory grows with each interaction. Manage it by:

1. **Compression**: Periodically compress old messages
2. **Limiting**: Set maximum conversation size
3. **Clearing**: Clear when not needed

```python
from core.memory_manager import get_memory_manager

memory = get_memory_manager()

# Compress memory
memory.compress_memory()

# Clear conversation
memory.clear_conversation()

# Set max size
memory._max_conversation_size = 1000
```

### Long-term Memory

Long-term memory stores persistent facts. Manage by:

1. **Regular cleanup**: Remove outdated information
2. **Categorization**: Organize by category
3. **Backup**: Regular backups

```python
# Add memory
memory.add_long_term_memory("preferences", "color", "blue")

# Search and clean
old_memories = memory.search_memories("old")
for mem in old_memories:
    memory.delete_long_term_memory(mem["key"])
```

### Memory Backup

Enable automatic backups:

```yaml
memory:
  backup:
    enabled: true
    interval_hours: 24
    max_backups: 7
    backup_dir: "data/backups"
```

Manual backup:

```python
from memory.memory_backup import MemoryBackupManager

backup_manager = MemoryBackupManager()
backup_manager.create_backup()
```

## Resource Monitoring

### Enable Monitoring

```yaml
performance:
  enabled: true
  resource_monitoring: true
  resource_interval_seconds: 60
```

### Monitor Resources

```python
from core.performance_monitor import get_performance_monitor

monitor = get_performance_monitor()

# Start monitoring
monitor.start_monitoring()

# Get current metrics
metrics = monitor.get_current_metrics()
print(f"CPU: {metrics['cpu_percent']}%")
print(f"Memory: {metrics['memory_percent']}%")
print(f"Disk: {metrics['disk_percent']}%")
```

### Performance Thresholds

Configure alert thresholds:

```yaml
performance:
  slow_operation_threshold_ms: 2000
  alert_threshold_ms: 5000
```

Track slow operations:

```python
from core.performance_tracker import get_performance_tracker

tracker = get_performance_tracker()
slow_ops = tracker.get_slow_operations(threshold_ms=2000)
for op in slow_ops:
    print(f"{op['name']}: {op['duration']}ms")
```

## Performance Optimization

### Startup Optimization

Reduce startup time:

1. Enable lazy loading
2. Disable unused features
3. Optimize imports

```yaml
performance:
  flags:
    lazy_tool_declarations: true
    lazy_load_actions: true

# Disable unused features
passive_vision:
  enabled: false
semantic_search:
  enabled: false
```

### AI Response Optimization

Optimize AI response times:

1. Use appropriate model
2. Cache system prompt
3. Minimize context

```yaml
models:
  live: "models/gemini-2.5-flash"  # Faster model
  text: "gemini-2.5-flash"

performance:
  flags:
    cache_system_prompt: true
```

### Action Execution Optimization

Optimize action execution:

1. Enable lazy action loading
2. Preload critical actions
3. Use async for I/O operations

```yaml
performance:
  flags:
    lazy_load_actions: true
  background_tasks_enabled: true
  background_workers: 4
```

Preload critical actions:

```python
from core.action_loader import get_action_loader

loader = get_action_loader()
critical_actions = ["web_search", "computer_control"]
loader.preload_actions(critical_actions)
```

## Benchmarking

### Run Benchmarks

```bash
pytest tests/benchmarks/ --benchmark-only
```

### Benchmark Categories

- **Action Performance**: Measure action execution time
- **Memory Operations**: Measure memory operation speed
- **AI Calls**: Measure AI response times
- **I/O Operations**: Measure file/database operations

### Custom Benchmarks

Create benchmarks in `tests/benchmarks/`:

```python
import pytest

@pytest.mark.benchmark
def test_action_performance(benchmark):
    def my_action():
        # Action to benchmark
        return result
    
    result = benchmark(my_action)
    assert result is not None
```

### Benchmark Results

Results saved to `benchmark_results.json`:

```json
{
  "benchmarks": [
    {
      "name": "test_action_performance",
      "stats": {
        "mean": 123.45,
        "stddev": 5.67,
        "min": 110.0,
        "max": 140.0
      }
    }
  ]
}
```

## Performance Tuning

### CPU Optimization

Reduce CPU usage:

1. Disable resource-intensive features
2. Reduce background workers
3. Increase polling intervals

```yaml
performance:
  background_workers: 2  # Reduce from default
  resource_interval_seconds: 120  # Increase from default

passive_vision:
  enabled: false  # Disable if not needed
```

### Memory Optimization

Reduce memory usage:

1. Enable memory footprint reduction
2. Limit history sizes
3. Enable compression

```yaml
performance:
  flags:
    reduce_memory_footprint: true

security:
  action_history_max_size: 500  # Reduce from default 1000

memory:
  compression:
    enabled: true
    threshold: 1000  # Compress after 1000 messages
```

### I/O Optimization

Reduce I/O operations:

1. Enable caching
2. Batch operations
3. Use async I/O

```yaml
performance:
  flags:
    cache_system_prompt: true
    lazy_tool_declarations: true
```

Batch operations:

```python
# Instead of multiple small writes
for item in items:
    write_to_file(item)

# Use single batch write
write_to_file(items)
```

## Performance Profiling

### Profile Code

Use Python's profiler:

```bash
python -m cProfile -o profile.stats main.py
```

Analyze profile:

```python
import pstats

p = pstats.Stats('profile.stats')
p.sort_stats('cumulative')
p.print_stats(20)  # Top 20 functions
```

### Profile Specific Functions

```python
import cProfile
import pstats

def profile_function(func):
    def wrapper(*args, **kwargs):
        profiler = cProfile.Profile()
        profiler.enable()
        result = func(*args, **kwargs)
        profiler.disable()
        stats = pstats.Stats(profiler)
        stats.sort_stats('cumulative')
        stats.print_stats(10)
        return result
    return wrapper

@profile_function
def my_function():
    # Function to profile
    pass
```

## Performance Monitoring Dashboard

### Metrics Collection

Enable metrics collection:

```yaml
performance:
  enabled: true
  metrics:
    enabled: true
    export_interval_seconds: 60
```

### Export Metrics

```python
from core.metrics_collector import get_metrics_collector

metrics = get_metrics_collector()
metrics.export_to_file("metrics.json")
```

### Key Metrics to Monitor

- **Response Time**: Time to process user requests
- **Action Execution Time**: Time to execute actions
- **Memory Usage**: Current memory consumption
- **CPU Usage**: Current CPU utilization
- **Error Rate**: Frequency of errors

## Performance Best Practices

### 1. Use Lazy Loading

Load resources only when needed:

```python
# Bad: Load everything at startup
all_data = load_all_data()

# Good: Load on demand
def get_data(key):
    if key not in cache:
        cache[key] = load_data(key)
    return cache[key]
```

### 2. Cache Expensive Operations

Cache results of expensive computations:

```python
from functools import lru_cache

@lru_cache(maxsize=128)
def expensive_computation(param):
    # Expensive operation
    return result
```

### 3. Use Async for I/O

Use async for I/O-bound operations:

```python
import asyncio

async def fetch_data(url):
    # Async I/O operation
    return await aiohttp.get(url)
```

### 4. Batch Operations

Batch multiple small operations:

```python
# Bad: Multiple small writes
for item in items:
    database.write(item)

# Good: Single batch write
database.write_batch(items)
```

### 5. Monitor Performance

Regularly monitor performance metrics:

```python
from core.performance_tracker import get_performance_tracker

tracker = get_performance_tracker()
metrics = tracker.get_metrics()
# Analyze and optimize based on metrics
```

## Performance Troubleshooting

### Slow Startup

**Symptoms**: Application takes long to start

**Solutions**:
1. Enable lazy loading
2. Disable unused features
3. Check for blocking imports

### High Memory Usage

**Symptoms**: Memory usage grows over time

**Solutions**:
1. Enable memory footprint reduction
2. Limit conversation history
3. Enable memory compression
4. Check for memory leaks

### Slow AI Responses

**Symptoms**: AI takes long to respond

**Solutions**:
1. Cache system prompt
2. Use faster model
3. Reduce context size
4. Check network latency

### High CPU Usage

**Symptoms**: CPU usage consistently high

**Solutions**:
1. Disable resource-intensive features
2. Reduce background workers
3. Check for infinite loops
4. Profile to identify hotspots

## Performance Checklist

Use this checklist to ensure optimal performance:

- [ ] Enable appropriate feature flags
- [ ] Configure caching strategies
- [ ] Set memory limits
- [ ] Enable resource monitoring
- [ ] Run benchmarks
- [ ] Profile slow operations
- [ ] Optimize hotspots
- [ ] Monitor metrics regularly
- [ ] Update configuration based on usage patterns
- [ ] Document performance decisions

## Performance Tools

### Built-in Tools

- **Performance Tracker**: Track operation times
- **Performance Monitor**: Monitor system resources
- **Metrics Collector**: Collect custom metrics

### External Tools

- **py-spy**: Python profiler
- **memory_profiler**: Memory profiling
- **pytest-benchmark**: Benchmarking framework
- **line_profiler**: Line-by-line profiling

### Example: Using py-spy

```bash
# Install
pip install py-spy

# Profile running process
py-spy top --pid <pid>

# Record flame graph
py-spy record --pid <pid> -o profile.svg
```

## Performance Goals

Target performance metrics:

- **Startup Time**: < 5 seconds
- **AI Response Time**: < 3 seconds
- **Action Execution**: < 2 seconds (average)
- **Memory Usage**: < 500 MB (idle)
- **CPU Usage**: < 10% (idle)

Regularly measure against these goals and optimize as needed.
