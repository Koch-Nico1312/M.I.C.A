# M.I.C.A Enhancements Documentation

This document describes all the new enhancements added to M.I.C.A (M.I.C.A).

## 📋 Overview

The following enhancements have been implemented across 4 categories:

### 1. Intelligence & Context Awareness
- **Passive Vision System**: Background OCR/Vision stream for short-term visual memory
- **Semantic File Search (RAG)**: Vector database for semantic search across documents
- **Vision-Verify Self-Correction**: Automatic screenshot verification after actions

### 2. UI/UX (Iron Man Experience)
- **Screen Overlay HUD**: Transparent overlay with glowing highlights
- **Proactive Suggestions**: AI-powered help before being asked
- **Voice Emotional Analysis**: Detect frustration/urgency to adjust tone

### 3. Architecture & Extensibility
- **Dynamic Plugin System**: Load tools from plugins/ directory
- **Local LLM Fallback**: Ollama integration for offline capability
- **Unified Configuration**: .env and config.yaml for easy setup

### 4. Productivity Force Multipliers
- **VS Code Extension Bridge**: Real-time code editing integration
- **Cross-Device Handover**: Telegram/Discord bot for mobile notifications

---

## 🚀 Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

New dependencies added:
- python-dotenv (for .env support)
- pyyaml (for config.yaml)
- chromadb (for semantic search)
- sentence-transformers (for embeddings)
- ollama (for local LLM)
- librosa (for audio emotion analysis)
- soundfile (for audio processing)
- aiohttp (for async HTTP)
- websockets (for real-time communication)

### 2. Configure Settings

Copy the example configuration file:
```bash
cp .env.example .env
```

Edit `.env` or `config.yaml` to enable features:
```yaml
# Enable features you want
passive_vision:
  enabled: true
  interval_seconds: 30

rag:
  enabled: true
  vector_db: "chromadb"

hud:
  enabled: true
  transparency: 0.7

ollama:
  enabled: true
  base_url: "http://localhost:11434"
```

### 3. Start M.I.C.A

```bash
.\venv\Scripts\python.exe .\main.py
```

---

## 📚 Feature Details

### 1. Unified Configuration System

**Files Created:**
- `.env.example` - Environment variables template
- `config.yaml` - YAML configuration file
- `config/config_loader.py` - Configuration loader module

**Usage:**
```python
from config.config_loader import get_config

config = get_config()
api_key = config.get_api_key('gemini')
model = config.get('models.live')
```

**Benefits:**
- Centralized configuration management
- Environment-specific settings
- Easy deployment and "stealth" mode
- No hardcoded paths in code

---

### 2. Dynamic Plugin System

**Files Created:**
- `core/plugin_system.py` - Plugin manager
- `plugins/` - Directory for custom tools
- `plugins/__init__.py` - Plugin package init

**Usage:**
```python
from core.plugin_system import get_plugin_manager

plugin_manager = get_plugin_manager()
plugin_manager.load_all_plugins()
tools = plugin_manager.get_tool_declarations()
```

**Creating a Custom Plugin:**
```python
# plugins/my_tool.py
TOOL_DECLARATION = {
    "name": "my_tool",
    "description": "Does something cool",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "input": {"type": "STRING"}
        }
    }
}

def my_tool(parameters: dict, player=None, speak=None, **kwargs):
    input_val = parameters.get('input', '')
    # Your implementation here
    return "Done."
```

**Benefits:**
- Drop-in tool creation
- No need to modify main.py
- Automatic tool registration
- Easy to share plugins

---

### 3. Local LLM Fallback (Ollama)

**Files Created:**
- `core/llm_fallback.py` - Ollama integration

**Usage:**
```python
from core.llm_fallback import get_hybrid_llm

hybrid = get_hybrid_llm()
hybrid.set_fallback_mode(True)
result = hybrid.generate_text("Hello", system_prompt="...")
```

**Configuration:**
```yaml
ollama:
  enabled: true
  base_url: "http://localhost:11434"
  model: "llama3"
  fallback_only: false  # Use as primary or fallback only
```

**Benefits:**
- Offline capability
- No API limits
- Privacy (local processing)
- Automatic fallback when Gemini fails

---

### 4. Passive Vision System

**Files Created:**
- `core/passive_vision.py` - Background vision monitoring

**Usage:**
```python
from core.passive_vision import get_passive_vision

vision = get_passive_vision()
vision.start()

# Query visual memory
result = vision.query_memory("What was that error message?")
```

**Configuration:**
```yaml
passive_vision:
  enabled: true
  interval_seconds: 30  # Capture every 30 seconds
  memory_minutes: 10    # Keep 10 minutes of history
```

**Benefits:**
- Short-term visual memory
- Answer questions about past screen content
- "What was that error 2 minutes ago?"
- Automatic background monitoring

---

### 5. Semantic File Search (RAG)

**Files Created:**
- `core/semantic_search.py` - Vector-based search

**Usage:**
```python
from core.semantic_search import get_semantic_search

search = get_semantic_search()
search.index_directory(Path("./documents"))
results = search.search("marketing campaign next steps")
answer = search.ask("What are the project goals?")
```

**Configuration:**
```yaml
rag:
  enabled: true
  vector_db: "chromadb"
  index_path: "./data/vector_db"
  chunk_size: 500
  embedding_model: "all-MiniLM-L6-v2"
```

**Benefits:**
- Search across entire document folder
- Semantic understanding (not just keyword)
- Answer questions based on documents
- Fast retrieval with vector embeddings

---

### 6. Vision-Verify Self-Correction

**Files Modified:**
- `agent/executor.py` - Added vision verification

**How It Works:**
After clicking or screen-interaction actions:
1. Takes a screenshot
2. Verifies the action worked
3. Retries if verification fails
4. Proceeds only when successful

**Configuration:**
```yaml
system:
  vision_verify: true  # Enable/disable verification
```

**Benefits:**
- Autonomous action verification
- Self-correction on failures
- More reliable automation
- Reduced need for manual intervention

---

### 7. Screen Overlay HUD

**Files Created:**
- `core/hud_overlay.py` - Transparent overlay system

**Usage:**
```python
from core.hud_overlay import get_hud_manager

hud = get_hud_manager()
hud.initialize()
hud.highlight_click(500, 300)  # Highlight click position
hud.set_status("Processing...")
hud.set_action("Opening Chrome")
```

**Configuration:**
```yaml
hud:
  enabled: true
  transparency: 0.7
  highlight_color: "#00ff00"
  show_click_targets: true
```

**Benefits:**
- Visual feedback for autonomous actions
- Glowing highlights on clicks
- "Iron Man" experience
- See what M.I.C.A is doing

---

### 8. Proactive Suggestions

**Files Created:**
- `core/proactive_suggestions.py` - AI-powered suggestions

**Usage:**
```python
from core.proactive_suggestions import get_proactive_suggestions

proactive = get_proactive_suggestions()
proactive.set_speak_callback(speak_function)
proactive.track_action("open_chrome", success=True)
proactive.start()
```

**Configuration:**
```yaml
proactive:
  enabled: true
  interval_seconds: 60
  max_suggestions: 3
```

**Benefits:**
- Help before being asked
- Detect repetitive actions
- Suggest automation opportunities
- Error pattern detection

---

### 9. Voice Emotional Analysis

**Files Created:**
- `core/voice_emotion.py` - Emotion detection from voice

**Usage:**
```python
from core.voice_emotion import get_emotion_analyzer

emotion = get_emotion_analyzer()
result = emotion.analyze_audio(audio_data, sample_rate=16000)
print(f"Detected: {result.emotion}")

# Adjust response based on emotion
adjusted = emotion.format_response_for_emotion(response, result.emotion)
```

**Configuration:**
```yaml
emotion:
  enabled: true
  sensitivity: 0.5
  adjust_tone: true
```

**Benefits:**
- Detect frustration/urgency
- Adjust tone automatically
- Better user experience
- Context-aware responses

---

### 10. VS Code Extension Bridge

**Files Created:**
- `core/vscode_bridge.py` - VS Code communication

**Usage:**
```python
from core.vscode_bridge import get_vscode_bridge

vscode = get_vscode_bridge()
await vscode.connect()
await vscode.edit_file("main.py", [
    {"old_text": "old", "new_text": "new"}
])
await vscode.refactor_code("file.py", "pattern", "replacement")
```

**Configuration:**
```yaml
vscode:
  bridge_enabled: true
  port: 8080
  auto_connect: false
```

**Benefits:**
- Real-time code editing
- Watch code change in editor
- Refactoring assistance
- Seamless IDE integration

---

### 11. Cross-Device Handover

**Files Created:**
- `core/cross_device.py` - Telegram/Discord integration

**Usage:**
```python
from core.cross_device import get_cross_device

handover = get_cross_device()
handover.sync_send_summary("Task completed successfully")
handover.sync_send_reminder("Meeting at 3 PM")
handover.sync_send_task_completion("Backup", "Done")
```

**Configuration:**
```yaml
cross_device:
  telegram:
    enabled: true
    bot_token: "your_bot_token"
    chat_id: "your_chat_id"
  discord:
    enabled: true
    bot_token: "your_bot_token"
    channel_id: "your_channel_id"
```

**Benefits:**
- Send summaries to phone
- Mobile reminders
- Task completion notifications
- Stay connected anywhere

---

## 🔧 Integration with main.py

To integrate these enhancements into the existing main.py, add the following imports and initialization:

```python
# Add imports
from config.config_loader import get_config
from core.plugin_system import get_plugin_manager
from core.passive_vision import get_passive_vision
from core.semantic_search import get_semantic_search
from core.hud_overlay import get_hud_manager
from core.proactive_suggestions import get_proactive_suggestions
from core.voice_emotion import get_emotion_analyzer
from core.vscode_bridge import get_vscode_bridge
from core.cross_device import get_cross_device

# Initialize in M.I.C.ALive.__init__
config = get_config()

# Initialize enabled features
if config.get('passive_vision.enabled'):
    passive_vision = get_passive_vision()
    passive_vision.start()

if config.get('rag.enabled'):
    semantic_search = get_semantic_search()
    semantic_search.index_directory(Path("./documents"))

if config.get('hud.enabled'):
    hud = get_hud_manager()
    hud.initialize()

if config.get('proactive.enabled'):
    proactive = get_proactive_suggestions()
    proactive.set_speak_callback(self.speak)
    proactive.start()
```

---

## 📝 Notes

### Optional Dependencies
Some features have optional dependencies. If a library is not installed, the feature will be disabled automatically with a warning message.

### Performance Considerations
- **Passive Vision**: Captures screen every 30 seconds by default (configurable)
- **RAG**: Initial indexing may take time for large document sets
- **HUD**: Uses PyQt6 overlay, minimal performance impact
- **Emotion Analysis**: Processes audio in real-time

### Privacy
- **Ollama**: Runs locally, no data leaves your machine
- **RAG**: Vector database stored locally
- **Passive Vision**: Visual memory stored locally, configurable retention

### Security
- API keys should be stored in `.env` (not committed to git)
- Telegram/Discord tokens should be kept secure
- VS Code bridge runs on localhost by default

---

## 🎯 Future Enhancements

Potential future additions:
- Hume AI integration for advanced emotion detection
- More sophisticated OCR (Tesseract integration)
- Multi-language support for semantic search
- Additional cross-device platforms (Slack, etc.)
- Advanced HUD features (graphs, charts)
- Plugin marketplace/sharing system

---

## 📞 Support

For issues or questions:
- Check configuration files
- Ensure all dependencies are installed
- Verify API keys are correct
- Check logs in the console output

---

**Enjoy your enhanced M.I.C.A experience! 🤖**
