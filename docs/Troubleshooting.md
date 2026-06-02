# JARVIS AI Assistant - Troubleshooting Guide

This guide helps you diagnose and resolve common issues with JARVIS.

## Table of Contents

- [Installation Issues](#installation-issues)
- [Configuration Issues](#configuration-issues)
- [Runtime Issues](#runtime-issues)
- [Performance Issues](#performance-issues)
- [Integration Issues](#integration-issues)
- [Testing Issues](#testing-issues)
- [Getting Help](#getting-help)

## Installation Issues

### Python Version Incompatible

**Problem**: JARVIS requires Python 3.11 or higher.

**Solution**:
```bash
python --version  # Check your Python version
# If version < 3.11, install Python 3.11 or higher
```

### Dependencies Fail to Install

**Problem**: `pip install -r requirements.txt` fails.

**Solutions**:

1. Update pip:
```bash
pip install --upgrade pip
```

2. Use a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

3. Install packages individually to identify the issue:
```bash
pip install package-name
```

### Qt/PyQt6 Installation Fails

**Problem**: PyQt6 fails to install on some systems.

**Solutions**:

1. Install system dependencies (Linux):
```bash
sudo apt-get install python3-pyqt6
```

2. Use CLI mode without GUI:
```bash
python main.py  # Runs in CLI mode without --gui flag
```

## Configuration Issues

### API Key Not Found

**Problem**: JARVIS reports missing API key.

**Solutions**:

1. Check `.env` file:
```bash
cat .env
```

2. Add API key to `.env`:
```
GEMINI_API_KEY=your_api_key_here
```

3. Check `config/api_keys.json`:
```json
{
  "gemini_api_key": "your_api_key_here"
}
```

### Configuration File Not Found

**Problem**: `config.yaml` not found or invalid.

**Solutions**:

1. Verify file exists:
```bash
ls -la config.yaml
```

2. Copy from example if missing:
```bash
cp config.yaml.example config.yaml
```

3. Validate YAML syntax:
```bash
python -c "import yaml; yaml.safe_load(open('config.yaml'))"
```

### Permission Profile Invalid

**Problem**: Invalid permission profile in configuration.

**Solution**:

Check `config.yaml`:
```yaml
security:
  permission_profile: "safe"  # Valid: safe, normal, strict
```

## Runtime Issues

### Application Won't Start

**Problem**: JARVIS fails to start with error.

**Solutions**:

1. Check logs:
```bash
tail -f logs/jarvis.log
```

2. Run with verbose output:
```bash
python main.py --verbose
```

3. Check dependencies:
```bash
pip list
```

### Voice Input Not Working

**Problem**: Microphone not detected or voice input fails.

**Solutions**:

1. Check audio backend:
```bash
python -c "import sounddevice as sd; print(sd.query_devices())"
```

2. Install sounddevice:
```bash
pip install sounddevice
```

3. Check system microphone permissions

### AI Model Not Responding

**Problem**: AI model doesn't respond to queries.

**Solutions**:

1. Verify API key is valid:
```bash
python -c "from config.startup_config import get_api_key; print(get_api_key())"
```

2. Check internet connection

3. Verify model name in `config.yaml`:
```yaml
models:
  live: "models/gemini-2.5-flash-native-audio-preview-12-2025"
```

4. Check API quota limits

### Actions Not Executing

**Problem**: Actions fail to execute or return errors.

**Solutions**:

1. Check action is enabled in `config.yaml`:
```yaml
security:
  disabled_actions: []
```

2. Check approval flow settings:
```yaml
security:
  confirmation_medium_risk: true
  confirmation_high_risk: true
```

3. Check action logs for specific errors

### Memory Issues

**Problem**: JARVIS runs out of memory or becomes slow.

**Solutions**:

1. Enable memory compression:
```yaml
performance:
  flags:
    reduce_memory_footprint: true
```

2. Clear conversation history periodically

3. Adjust memory limits in configuration

## Performance Issues

### Slow Response Times

**Problem**: JARVIS responds slowly to queries.

**Solutions**:

1. Enable performance flags:
```yaml
performance:
  flags:
    lazy_tool_declarations: true
    cache_system_prompt: true
    lazy_load_actions: true
```

2. Check system resources:
```bash
top  # Linux/Mac
taskmgr  # Windows
```

3. Enable performance tracking to identify bottlenecks:
```yaml
performance:
  enabled: true
```

### High CPU Usage

**Problem**: JARVIS uses excessive CPU.

**Solutions**:

1. Disable resource-intensive features:
```yaml
passive_vision:
  enabled: false
```

2. Adjust background task workers:
```yaml
performance:
  background_workers: 2  # Reduce from default
```

3. Check for runaway processes

### High Memory Usage

**Problem**: JARVIS uses excessive memory.

**Solutions**:

1. Enable memory management:
```yaml
performance:
  flags:
    reduce_memory_footprint: true
```

2. Reduce conversation history size:
```yaml
security:
  action_history_max_size: 500  # Reduce from default 1000
```

3. Enable periodic memory compression

## Integration Issues

### Gmail Integration Not Working

**Problem**: Gmail features fail.

**Solutions**:

1. Check Gmail API credentials in `.env`:
```
GMAIL_CLIENT_ID=your_client_id
GMAIL_CLIENT_SECRET=your_client_secret
```

2. Verify OAuth consent screen is configured

3. Check Gmail API is enabled in Google Cloud Console

### Calendar Integration Not Working

**Problem**: Calendar features fail.

**Solutions**:

1. Check Calendar API credentials in `.env`:
```
CALENDAR_CLIENT_ID=your_client_id
CALENDAR_CLIENT_SECRET=your_client_secret
```

2. Verify Calendar API is enabled

3. Check calendar permissions

### Spotify Integration Not Working

**Problem**: Spotify features fail.

**Solutions**:

1. Check Spotify credentials in `.env`:
```
SPOTIFY_CLIENT_ID=your_client_id
SPOTIFY_CLIENT_SECRET=your_client_secret
SPOTIFY_REDIRECT_URI=http://localhost:8888/callback
```

2. Verify Spotify Developer account

3. Check Spotify Premium subscription (required for some features)

### Obsidian Integration Not Working

**Problem**: Obsidian vault integration fails.

**Solutions**:

1. Check vault path in `config.yaml`:
```yaml
obsidian:
  vault_path: "/path/to/your/vault"
```

2. Verify vault path exists and is accessible

3. Check Obsidian is not running (conflict possible)

## Testing Issues

### Tests Fail to Run

**Problem**: `pytest` fails with errors.

**Solutions**:

1. Install test dependencies:
```bash
pip install pytest pytest-cov pytest-asyncio pytest-mock
```

2. Check pytest configuration in `pytest.ini`

3. Run specific test to isolate issue:
```bash
pytest tests/test_specific_file.py -v
```

### Coverage Below Threshold

**Problem**: Coverage report shows below 70% threshold.

**Solutions**:

1. Identify uncovered modules:
```bash
pytest --cov-report=html
open htmlcov/index.html
```

2. Add tests for uncovered code

3. Adjust threshold in `pytest.ini` if necessary

### Mocking Issues

**Problem**: Tests fail due to mocking problems.

**Solutions**:

1. Use provided mocking utilities from `tests/mocking_utils.py`
2. Check mock configuration
3. Verify mock returns expected values

## Debug Mode

### Enable Debug Logging

Enable debug logging for detailed information:

```yaml
logging:
  level: "DEBUG"
```

### Run Diagnostics

Run system diagnostics:

```python
from core.diagnostics import run_diagnostics
report = run_diagnostics(verbose=True)
print(report)
```

### Check Feature Flags

Check which features are enabled:

```python
from core.performance_flags import get_performance_flags
flags = get_performance_flags()
print(flags.get_all_flags())
```

## Common Error Messages

### "API key not valid"

**Cause**: Invalid or missing API key

**Solution**: Verify API key in `.env` or `config/api_keys.json`

### "Action not found"

**Cause**: Action not registered or disabled

**Solution**: Check action is enabled and properly registered

### "Permission denied"

**Cause**: Action requires higher permission level

**Solution**: Adjust permission profile or approve action manually

### "Out of memory"

**Cause**: System memory exhausted

**Solution**: Enable memory compression, reduce history size

### "Connection timeout"

**Cause**: Network issue or API unreachable

**Solution**: Check internet connection, verify API status

## Log Files

### Log Locations

- Main log: `logs/jarvis.log`
- Error log: `logs/error.log`
- Performance log: `logs/performance.log`

### Viewing Logs

```bash
# View main log
tail -f logs/jarvis.log

# View error log
tail -f logs/error.log

# Search for errors
grep "ERROR" logs/jarvis.log
```

## System Diagnostics

### Run Full Diagnostics

```python
from core.diagnostics import SystemDiagnostics

diagnostics = SystemDiagnostics()
report = diagnostics.run_full_check()
print(report.format_report(verbose=True))
```

### Check Dependencies

```bash
pip check
```

### Check Python Environment

```bash
python --version
pip list
python -c "import sys; print(sys.path)"
```

## Getting Help

### Documentation

- [Architecture.md](Architecture.md) - System architecture
- [API.md](API.md) - API documentation
- [Contributing.md](Contributing.md) - Contributing guidelines
- [Performance Guide.md](Performance-Guide.md) - Performance optimization

### Community

- GitHub Issues: Report bugs and request features
- GitHub Discussions: Ask questions and share ideas
- Check existing issues before creating new ones

### When Reporting Issues

Include:

1. JARVIS version
2. Python version
3. OS version
4. Error message
5. Steps to reproduce
6. Relevant logs
7. Configuration (sanitized)

## Recovery Procedures

### Reset Configuration

If configuration is corrupted:

```bash
# Backup current config
cp config.yaml config.yaml.backup

# Reset to defaults (if available)
cp config.yaml.example config.yaml

# Reconfigure as needed
```

### Clear Memory

If memory is corrupted:

```python
from core.memory_manager import get_memory_manager

memory = get_memory_manager()
memory.clear_conversation()
memory.clear_long_term_memory()
```

### Reset Action History

```python
from core.action_history import get_action_history

history = get_action_history()
history.clear()
```

## Preventive Measures

### Regular Backups

Enable automatic memory backups:

```yaml
memory:
  backup:
    enabled: true
    interval_hours: 24
    max_backups: 7
```

### Monitor Resources

Enable resource monitoring:

```yaml
performance:
  resource_monitoring: true
  resource_interval_seconds: 60
```

### Keep Updated

Regularly update dependencies:

```bash
pip install --upgrade -r requirements.txt
```

### Check Logs Regularly

Review logs periodically for issues:

```bash
tail -n 100 logs/jarvis.log
```
