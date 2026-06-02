import asyncio
import functools
import json
import os
import re
import sys
import threading
import traceback
import warnings
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from core.action_loader import get_action_loader

# Initialize logging first
from core.logger import get_logger, setup_logging
from core.memory_manager import get_memory_manager
from core.metrics_collector import get_metrics_collector
from core.paths import project_path, resolve_project_root, resolve_relative_path
from core.performance_flags import get_performance_flags

os.environ["PYTHONUTF8"] = "1"
for _stream_name in ("stdout", "stderr"):
    try:
        getattr(sys, _stream_name).reconfigure(encoding="utf-8")
    except Exception:
        pass

warnings.filterwarnings(
    "ignore",
    message=r"[\s\S]*google\.generativeai[\s\S]*",
    category=FutureWarning,
)

# Setup logging
setup_logging()
logger = get_logger(__name__)

try:
    import sounddevice as sd
except ImportError:
    sd = None

import google.genai
from google.genai import types

from actions.browser_control import browser_control
from actions.calendar_manager import calendar_manager
from actions.code_helper import code_helper
from actions.computer_control import computer_control
from actions.computer_settings import computer_settings
from actions.desktop import desktop_control
from actions.dev_agent import dev_agent
from actions.file_controller import file_controller
from actions.file_processor import file_processor
from actions.flight_finder import flight_finder
from actions.game_updater import game_updater
from actions.gmail_manager import gmail_manager
from actions.open_app import open_app
from actions.reminder import reminder
from actions.roblox_controller import roblox_controller
from actions.screen_processor import screen_process
from actions.send_message import send_message
from actions.spotify_controller import spotify_controller
from actions.weather_report import weather_action
from actions.web_search import web_search as web_search_action
from actions.youtube_video import youtube_video
from config.config_loader import get_config
from core.action_history import get_action_history
from core.approval_flow import get_approval_flow
from core.background_task_manager import get_background_task_manager
from core.cross_device import get_cross_device
from core.daily_briefing import daily_briefing
from core.healthcheck import build_runtime_report, format_runtime_report
from core.hud_overlay import get_hud_manager
from core.jarvis_live import JarvisLive
from core.llm_fallback import get_hybrid_llm
from core.local_analyzer import get_local_analyzer
from core.morning_routine import RoutineConfig, RoutineMode, get_morning_routine
from core.multimodal_context import get_multimodal_context
from core.passive_vision import get_passive_vision
from core.performance_monitor import get_performance_monitor
from core.performance_tracker import get_performance_tracker
from core.permission_profiles import (
    PermissionLevel,
    disable_action,
    enable_action,
    get_disabled_actions,
    get_tool_metadata,
)
from core.plugin_system import get_plugin_manager
from core.proactive_suggestions import get_proactive_suggestions
from core.semantic_search import get_semantic_search
from core.session_manager import get_session_manager
from core.setup_flow import get_setup_flow, run_setup_check
from core.voice_emotion import get_emotion_analyzer
from core.vscode_bridge import get_vscode_bridge
from core.workflow_engine import get_workflow_engine
from memory.hybrid_retrieval import get_hybrid_retrieval
from memory.memory_backup import get_backup_manager
from memory.memory_manager import (
    MEMORY_PATH,
    format_memory_for_prompt,
    load_memory,
    update_memory,
)
from memory.obsidian_vault import get_obsidian_bridge
from ui_bridge import JarvisUI

# Lazy loading support for tool declarations
_tool_declarations_cache = None
_tool_declarations_lock = threading.Lock()

# Action loader for lazy loading action modules
_action_loader = None


BASE_DIR = resolve_project_root()
API_CONFIG_PATH = project_path("config", "api_keys.json")
PROMPT_PATH = project_path("core", "prompt.txt")
DEFAULT_LIVE_MODEL = "models/gemini-2.5-flash-native-audio-preview-12-2025"
DEFAULT_CHANNELS = 1
DEFAULT_SEND_SAMPLE_RATE = 16000
DEFAULT_RECEIVE_SAMPLE_RATE = 24000
DEFAULT_CHUNK_SIZE = 1024


def _get_api_key() -> str:
    config = get_config()
    api_key = str(config.get_api_key("gemini") or "").strip()
    if api_key:
        return api_key

    with open(API_CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)["gemini_api_key"]


def _load_system_prompt() -> str:
    """
    Load the system prompt from file or return default.
    With caching enabled (via feature flag), uses LRU cache with 5-minute TTL.
    """
    perf_flags = get_performance_flags()
    metrics = get_metrics_collector()

    if perf_flags.is_enabled("cache_system_prompt"):
        return _load_system_prompt_cached()

    # Original implementation without caching
    metrics.start_operation("load_system_prompt_uncached")
    try:
        result = PROMPT_PATH.read_text(encoding="utf-8")
        metrics.end_operation("load_system_prompt_uncached", {"cached": False})
        return result
    except Exception:
        metrics.end_operation("load_system_prompt_uncached", {"cached": False, "error": True})
        return (
            "You are JARVIS, Tony Stark's AI assistant. "
            "Be concise, direct, and always use the provided tools to complete tasks. "
            "Never simulate or guess results — always call the appropriate tool."
        )


# Cached version with timestamp-based invalidation
_system_prompt_cache = {"prompt": None, "timestamp": None, "file_mtime": None}
_system_prompt_cache_ttl = timedelta(minutes=5)
_system_prompt_cache_lock = threading.Lock()


def _load_system_prompt_cached() -> str:
    """
    Load system prompt with LRU cache and 5-minute TTL.
    Cache is invalidated if file is modified.
    """
    metrics = get_metrics_collector()
    metrics.start_operation("load_system_prompt_cached")

    with _system_prompt_cache_lock:
        current_time = datetime.now()

        # Check if we need to refresh cache
        needs_refresh = False

        if _system_prompt_cache["prompt"] is None:
            needs_refresh = True
        elif current_time - _system_prompt_cache["timestamp"] > _system_prompt_cache_ttl:
            needs_refresh = True
        elif PROMPT_PATH.exists():
            current_mtime = PROMPT_PATH.stat().st_mtime
            if _system_prompt_cache["file_mtime"] != current_mtime:
                needs_refresh = True

        if needs_refresh:
            try:
                prompt = PROMPT_PATH.read_text(encoding="utf-8")
                _system_prompt_cache["prompt"] = prompt
                _system_prompt_cache["timestamp"] = current_time
                _system_prompt_cache["file_mtime"] = (
                    PROMPT_PATH.stat().st_mtime if PROMPT_PATH.exists() else None
                )
                metrics.end_operation(
                    "load_system_prompt_cached", {"cached": False, "refreshed": True}
                )
                logger.debug("System prompt cache refreshed")
            except Exception:
                # Return cached version if available, otherwise default
                if _system_prompt_cache["prompt"]:
                    metrics.end_operation(
                        "load_system_prompt_cached", {"cached": True, "error": True}
                    )
                    return _system_prompt_cache["prompt"]
                metrics.end_operation("load_system_prompt_cached", {"cached": False, "error": True})
                return (
                    "You are JARVIS, Tony Stark's AI assistant. "
                    "Be concise, direct, and always use the provided tools to complete tasks. "
                    "Never simulate or guess results — always call the appropriate tool."
                )
        else:
            metrics.end_operation("load_system_prompt_cached", {"cached": True, "refreshed": False})

    return _system_prompt_cache["prompt"]


def get_tool_declarations() -> list:
    """
    Get tool declarations with optional lazy loading.
    When lazy_tool_declarations flag is enabled, declarations are cached after first load.
    """
    perf_flags = get_performance_flags()
    metrics = get_metrics_collector()

    if perf_flags.is_enabled("lazy_tool_declarations"):
        return _get_tool_declarations_lazy()

    # Return static declarations if lazy loading is disabled
    return TOOL_DECLARATIONS


def _get_action_loader():
    """Get the global action loader instance."""
    global _action_loader
    if _action_loader is None:
        _action_loader = get_action_loader()
    return _action_loader


def _get_tool_declarations_lazy() -> list:
    """
    Lazy load tool declarations with caching.
    """
    global _tool_declarations_cache
    metrics = get_metrics_collector()
    metrics.start_operation("get_tool_declarations_lazy")

    with _tool_declarations_lock:
        if _tool_declarations_cache is not None:
            metrics.end_operation("get_tool_declarations_lazy", {"cached": True})
            return _tool_declarations_cache

        # Load declarations on first access
        _tool_declarations_cache = TOOL_DECLARATIONS.copy()
        metrics.end_operation("get_tool_declarations_lazy", {"cached": False, "loaded": True})
        logger.debug("Tool declarations loaded and cached")

    return _tool_declarations_cache


_CTRL_RE = re.compile(r"<ctrl\d+>", re.IGNORECASE)


def _ensure_audio_backend() -> None:
    if sd is None:
        raise RuntimeError(
            "sounddevice is not installed. Install dependencies with "
            "'pip install -r requirements.txt'."
        )


def _is_invalid_api_key_error(exc: Exception) -> bool:
    text = str(exc).lower()
    return "api key not valid" in text or "invalid api key" in text


def _clean_transcript(text: str) -> str:
    text = _CTRL_RE.sub("", text)
    text = re.sub(r"[\x00-\x08\x0b-\x1f]", "", text)
    return text.strip()


TOOL_DECLARATIONS = [
    {
        "name": "open_app",
        "description": (
            "Opens any application on the computer. "
            "Use this whenever the user asks to open, launch, or start any app, "
            "website, or program. Always call this tool — never just say you opened it."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "app_name": {
                    "type": "STRING",
                    "description": "Exact name of the application (e.g. 'WhatsApp', 'Chrome', 'Spotify')",
                }
            },
            "required": ["app_name"],
        },
    },
    {
        "name": "web_search",
        "description": "Searches the web for any information.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "query": {"type": "STRING", "description": "Search query"},
                "mode": {"type": "STRING", "description": "search (default) or compare"},
                "items": {
                    "type": "ARRAY",
                    "items": {"type": "STRING"},
                    "description": "Items to compare",
                },
                "aspect": {"type": "STRING", "description": "price | specs | reviews"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "weather_report",
        "description": "Gives the weather report to user",
        "parameters": {
            "type": "OBJECT",
            "properties": {"city": {"type": "STRING", "description": "City name"}},
            "required": ["city"],
        },
    },
    {
        "name": "send_message",
        "description": "Sends a text message via WhatsApp, Telegram, or other messaging platform.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "receiver": {"type": "STRING", "description": "Recipient contact name"},
                "message_text": {"type": "STRING", "description": "The message to send"},
                "platform": {"type": "STRING", "description": "Platform: WhatsApp, Telegram, etc."},
            },
            "required": ["receiver", "message_text", "platform"],
        },
    },
    {
        "name": "reminder",
        "description": "Sets a timed reminder using Task Scheduler.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "date": {"type": "STRING", "description": "Date in YYYY-MM-DD format"},
                "time": {"type": "STRING", "description": "Time in HH:MM format (24h)"},
                "message": {"type": "STRING", "description": "Reminder message text"},
            },
            "required": ["date", "time", "message"],
        },
    },
    {
        "name": "youtube_video",
        "description": (
            "Controls YouTube. Use for: playing videos, summarizing a video's content, "
            "getting video info, or showing trending videos."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {
                    "type": "STRING",
                    "description": "play | summarize | get_info | trending (default: play)",
                },
                "query": {"type": "STRING", "description": "Search query for play action"},
                "save": {
                    "type": "BOOLEAN",
                    "description": "Save summary to Notepad (summarize only)",
                },
                "region": {
                    "type": "STRING",
                    "description": "Country code for trending e.g. TR, US",
                },
                "url": {"type": "STRING", "description": "Video URL for get_info action"},
            },
            "required": [],
        },
    },
    {
        "name": "screen_process",
        "description": (
            "Captures and analyzes the screen or webcam image. "
            "MUST be called when user asks what is on screen, what you see, "
            "analyze my screen, look at camera, etc. "
            "You have NO visual ability without this tool. "
            "After calling this tool, stay SILENT — the vision module speaks directly."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "angle": {
                    "type": "STRING",
                    "description": "'screen' to capture display, 'camera' for webcam. Default: 'screen'",
                },
                "text": {
                    "type": "STRING",
                    "description": "The question or instruction about the captured image",
                },
            },
            "required": ["text"],
        },
    },
    {
        "name": "computer_settings",
        "description": (
            "Controls the computer: volume, brightness, window management, keyboard shortcuts, "
            "typing text on screen, closing apps, fullscreen, dark mode, WiFi, restart, shutdown, "
            "scrolling, tab management, zoom, screenshots, lock screen, refresh/reload page. "
            "Use for ANY single computer control command. NEVER route to agent_task."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "The action to perform"},
                "description": {
                    "type": "STRING",
                    "description": "Natural language description of what to do",
                },
                "value": {
                    "type": "STRING",
                    "description": "Optional value: volume level, text to type, etc.",
                },
            },
            "required": [],
        },
    },
    {
        "name": "browser_control",
        "description": (
            "Controls any web browser. Use for: opening websites, searching the web, "
            "clicking elements, filling forms, scrolling, screenshots, navigation, any web-based task. "
            "Always pass the 'browser' parameter when the user specifies a browser (e.g. 'open in Edge', "
            "'use Firefox', 'open Chrome'). Multiple browsers can run simultaneously."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {
                    "type": "STRING",
                    "description": "go_to | search | click | type | scroll | fill_form | smart_click | smart_type | get_text | get_url | press | new_tab | close_tab | screenshot | back | forward | reload | switch | list_browsers | close | close_all",
                },
                "browser": {
                    "type": "STRING",
                    "description": "Target browser: chrome | edge | firefox | opera | operagx | brave | vivaldi | safari. Omit to use the currently active browser.",
                },
                "url": {"type": "STRING", "description": "URL for go_to / new_tab action"},
                "query": {"type": "STRING", "description": "Search query for search action"},
                "engine": {
                    "type": "STRING",
                    "description": "Search engine: google | bing | duckduckgo | yandex (default: google)",
                },
                "selector": {"type": "STRING", "description": "CSS selector for click/type"},
                "text": {"type": "STRING", "description": "Text to click or type"},
                "description": {
                    "type": "STRING",
                    "description": "Element description for smart_click/smart_type",
                },
                "direction": {"type": "STRING", "description": "up | down for scroll"},
                "amount": {
                    "type": "INTEGER",
                    "description": "Scroll amount in pixels (default: 500)",
                },
                "key": {
                    "type": "STRING",
                    "description": "Key name for press action (e.g. Enter, Escape, F5)",
                },
                "path": {"type": "STRING", "description": "Save path for screenshot"},
                "incognito": {"type": "BOOLEAN", "description": "Open in private/incognito mode"},
                "clear_first": {
                    "type": "BOOLEAN",
                    "description": "Clear field before typing (default: true)",
                },
            },
            "required": ["action"],
        },
    },
    {
        "name": "file_controller",
        "description": "Manages files and folders: list, create, delete, move, copy, rename, read, write, find, disk usage.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {
                    "type": "STRING",
                    "description": "list | create_file | create_folder | delete | move | copy | rename | read | write | find | largest | disk_usage | organize_desktop | info",
                },
                "path": {
                    "type": "STRING",
                    "description": "File/folder path or shortcut: desktop, downloads, documents, home",
                },
                "destination": {"type": "STRING", "description": "Destination path for move/copy"},
                "new_name": {"type": "STRING", "description": "New name for rename"},
                "content": {"type": "STRING", "description": "Content for create_file/write"},
                "name": {"type": "STRING", "description": "File name to search for"},
                "extension": {
                    "type": "STRING",
                    "description": "File extension to search (e.g. .pdf)",
                },
                "count": {"type": "INTEGER", "description": "Number of results for largest"},
            },
            "required": ["action"],
        },
    },
    {
        "name": "desktop_control",
        "description": "Controls the desktop: wallpaper, organize, clean, list, stats.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {
                    "type": "STRING",
                    "description": "wallpaper | wallpaper_url | organize | clean | list | stats | task",
                },
                "path": {"type": "STRING", "description": "Image path for wallpaper"},
                "url": {"type": "STRING", "description": "Image URL for wallpaper_url"},
                "mode": {"type": "STRING", "description": "by_type or by_date for organize"},
                "task": {"type": "STRING", "description": "Natural language desktop task"},
            },
            "required": ["action"],
        },
    },
    {
        "name": "code_helper",
        "description": "Writes, edits, explains, runs, or builds code files.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {
                    "type": "STRING",
                    "description": "write | edit | explain | run | build | auto (default: auto)",
                },
                "description": {
                    "type": "STRING",
                    "description": "What the code should do or what change to make",
                },
                "language": {
                    "type": "STRING",
                    "description": "Programming language (default: python)",
                },
                "output_path": {"type": "STRING", "description": "Where to save the file"},
                "file_path": {
                    "type": "STRING",
                    "description": "Path to existing file for edit/explain/run/build",
                },
                "code": {"type": "STRING", "description": "Raw code string for explain"},
                "args": {"type": "STRING", "description": "CLI arguments for run/build"},
                "timeout": {
                    "type": "INTEGER",
                    "description": "Execution timeout in seconds (default: 30)",
                },
            },
            "required": ["action"],
        },
    },
    {
        "name": "dev_agent",
        "description": "Builds complete multi-file projects from scratch: plans, writes files, installs deps, opens VSCode, runs and fixes errors.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "description": {"type": "STRING", "description": "What the project should do"},
                "language": {
                    "type": "STRING",
                    "description": "Programming language (default: python)",
                },
                "project_name": {"type": "STRING", "description": "Optional project folder name"},
                "timeout": {
                    "type": "INTEGER",
                    "description": "Run timeout in seconds (default: 30)",
                },
            },
            "required": ["description"],
        },
    },
    {
        "name": "agent_task",
        "description": (
            "Executes complex multi-step tasks requiring multiple different tools. "
            "Examples: 'research X and save to file', 'find and organize files'. "
            "DO NOT use for single commands. NEVER use for Steam/Epic — use game_updater."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "goal": {
                    "type": "STRING",
                    "description": "Complete description of what to accomplish",
                },
                "priority": {
                    "type": "STRING",
                    "description": "low | normal | high (default: normal)",
                },
            },
            "required": ["goal"],
        },
    },
    {
        "name": "computer_control",
        "description": "Direct computer control: type, click, hotkeys, scroll, move mouse, screenshots, find elements on screen.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {
                    "type": "STRING",
                    "description": "type | smart_type | click | double_click | right_click | hotkey | press | scroll | move | copy | paste | screenshot | wait | clear_field | focus_window | screen_find | screen_click | random_data | user_data",
                },
                "text": {"type": "STRING", "description": "Text to type or paste"},
                "x": {"type": "INTEGER", "description": "X coordinate"},
                "y": {"type": "INTEGER", "description": "Y coordinate"},
                "keys": {"type": "STRING", "description": "Key combination e.g. 'ctrl+c'"},
                "key": {"type": "STRING", "description": "Single key e.g. 'enter'"},
                "direction": {"type": "STRING", "description": "up | down | left | right"},
                "amount": {"type": "INTEGER", "description": "Scroll amount (default: 3)"},
                "seconds": {"type": "NUMBER", "description": "Seconds to wait"},
                "title": {"type": "STRING", "description": "Window title for focus_window"},
                "description": {
                    "type": "STRING",
                    "description": "Element description for screen_find/screen_click",
                },
                "type": {"type": "STRING", "description": "Data type for random_data"},
                "field": {"type": "STRING", "description": "Field for user_data: name|email|city"},
                "clear_first": {
                    "type": "BOOLEAN",
                    "description": "Clear field before typing (default: true)",
                },
                "path": {"type": "STRING", "description": "Save path for screenshot"},
            },
            "required": ["action"],
        },
    },
    {
        "name": "game_updater",
        "description": (
            "THE ONLY tool for ANY Steam or Epic Games request. "
            "Use for: installing, downloading, updating games, listing installed games, "
            "checking download status, scheduling updates. "
            "ALWAYS call directly for any Steam/Epic/game request. "
            "NEVER use agent_task, browser_control, or web_search for Steam/Epic."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {
                    "type": "STRING",
                    "description": "update | install | list | download_status | schedule | cancel_schedule | schedule_status (default: update)",
                },
                "platform": {
                    "type": "STRING",
                    "description": "steam | epic | both (default: both)",
                },
                "game_name": {
                    "type": "STRING",
                    "description": "Game name (partial match supported)",
                },
                "app_id": {"type": "STRING", "description": "Steam AppID for install (optional)"},
                "hour": {
                    "type": "INTEGER",
                    "description": "Hour for scheduled update 0-23 (default: 3)",
                },
                "minute": {
                    "type": "INTEGER",
                    "description": "Minute for scheduled update 0-59 (default: 0)",
                },
                "shutdown_when_done": {
                    "type": "BOOLEAN",
                    "description": "Shut down PC when download finishes",
                },
            },
            "required": [],
        },
    },
    {
        "name": "flight_finder",
        "description": "Searches Google Flights and speaks the best options.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "origin": {"type": "STRING", "description": "Departure city or airport code"},
                "destination": {"type": "STRING", "description": "Arrival city or airport code"},
                "date": {"type": "STRING", "description": "Departure date (any format)"},
                "return_date": {"type": "STRING", "description": "Return date for round trips"},
                "passengers": {
                    "type": "INTEGER",
                    "description": "Number of passengers (default: 1)",
                },
                "cabin": {"type": "STRING", "description": "economy | premium | business | first"},
                "save": {"type": "BOOLEAN", "description": "Save results to Notepad"},
            },
            "required": ["origin", "destination", "date"],
        },
    },
    {
        "name": "shutdown_jarvis",
        "description": (
            "Shuts down the assistant completely. "
            "Call this when the user expresses intent to end the conversation, "
            "close the assistant, say goodbye, or stop Jarvis. "
            "The user can say this in ANY language."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {},
        },
    },
    {
        "name": "file_processor",
        "description": (
            "Processes any file that the user has uploaded or dropped onto the interface. "
            "Use this when the user refers to an uploaded file and wants an action on it. "
            "Supports: images (describe/ocr/resize/compress/convert), "
            "PDFs (summarize/extract_text/to_word), "
            "Word docs & text files (summarize/fix/reformat/translate), "
            "CSV/Excel (analyze/stats/filter/sort/convert), "
            "JSON/XML (validate/format/analyze), "
            "code files (explain/review/fix/optimize/run/document/test), "
            "audio (transcribe/trim/convert/info), "
            "video (trim/extract_audio/extract_frame/compress/transcribe/info), "
            "archives (list/extract), "
            "presentations (summarize/extract_text). "
            "ALWAYS call this tool when a file has been uploaded and the user gives a command about it. "
            "If the user's command is ambiguous, pick the most logical action for that file type."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "file_path": {
                    "type": "STRING",
                    "description": "Full path to the uploaded file. Leave empty to use the currently uploaded file.",
                },
                "action": {
                    "type": "STRING",
                    "description": (
                        "What to do with the file. Examples by type:\n"
                        "image: describe | ocr | resize | compress | convert | info\n"
                        "pdf: summarize | extract_text | to_word | info\n"
                        "docx/txt: summarize | fix | reformat | translate_hint | word_count | to_bullet\n"
                        "csv/excel: analyze | stats | filter | sort | convert | info\n"
                        "json: validate | format | analyze | to_csv\n"
                        "code: explain | review | fix | optimize | run | document | test\n"
                        "audio: transcribe | trim | convert | info\n"
                        "video: trim | extract_audio | extract_frame | compress | transcribe | info | convert\n"
                        "archive: list | extract\n"
                        "pptx: summarize | extract_text | analyze"
                    ),
                },
                "instruction": {
                    "type": "STRING",
                    "description": "Free-form instruction if action doesn't cover it. E.g. 'translate this to Turkish', 'find all email addresses'",
                },
                "format": {
                    "type": "STRING",
                    "description": "Target format for conversion. E.g. 'mp3', 'pdf', 'csv', 'png'",
                },
                "width": {"type": "INTEGER", "description": "Target width for image resize"},
                "height": {"type": "INTEGER", "description": "Target height for image resize"},
                "scale": {
                    "type": "NUMBER",
                    "description": "Scale factor for image resize (e.g. 0.5)",
                },
                "quality": {
                    "type": "INTEGER",
                    "description": "Quality 1-100 for image/video compress",
                },
                "start": {
                    "type": "STRING",
                    "description": "Start time for trim: seconds or HH:MM:SS",
                },
                "end": {"type": "STRING", "description": "End time for trim: seconds or HH:MM:SS"},
                "timestamp": {
                    "type": "STRING",
                    "description": "Timestamp for video frame extraction HH:MM:SS",
                },
                "column": {"type": "STRING", "description": "Column name for CSV filter/sort"},
                "value": {"type": "STRING", "description": "Filter value for CSV filter"},
                "condition": {
                    "type": "STRING",
                    "description": "Filter condition: equals|contains|gt|lt",
                },
                "ascending": {
                    "type": "BOOLEAN",
                    "description": "Sort order for CSV sort (default: true)",
                },
                "save": {"type": "BOOLEAN", "description": "Save result to file (default: true)"},
                "destination": {
                    "type": "STRING",
                    "description": "Output folder for archive extract",
                },
            },
            "required": [],
        },
    },
    {
        "name": "gmail_manager",
        "description": (
            "Manages Gmail emails: list, read, send, reply, search, summarize, mark as read, archive, delete. "
            "Use for any email-related task. Can read inbox, send new emails, reply to messages, "
            "search for specific emails, get unread count, and summarize recent emails."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {
                    "type": "STRING",
                    "description": "list | read | send | reply | search | unread_count | mark_read | archive | delete | summarize",
                },
                "message_id": {
                    "type": "STRING",
                    "description": "Email message ID (for read, reply, mark_read, archive, delete)",
                },
                "to": {"type": "STRING", "description": "Recipient email address (for send)"},
                "subject": {"type": "STRING", "description": "Email subject (for send)"},
                "body": {"type": "STRING", "description": "Email body content (for send, reply)"},
                "query": {"type": "STRING", "description": "Search query (for search, list)"},
                "max_results": {
                    "type": "INTEGER",
                    "description": "Maximum number of results (default: 10)",
                },
                "label": {
                    "type": "STRING",
                    "description": "Gmail label to filter (default: INBOX)",
                },
                "cc": {"type": "STRING", "description": "CC recipients (for send)"},
                "bcc": {"type": "STRING", "description": "BCC recipients (for send)"},
            },
            "required": ["action"],
        },
    },
    {
        "name": "calendar_manager",
        "description": (
            "Manages Google Calendar: list today's events, create/edit/delete appointments, "
            "search events, check free time slots, view weekly schedule. "
            "Use for ANY calendar, schedule, or appointment related request."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {
                    "type": "STRING",
                    "description": "today | tomorrow | this_week | list | create | delete | update | next | search | free_slots",
                },
                "title": {"type": "STRING", "description": "Event title (for create/update)"},
                "date": {"type": "STRING", "description": "Date in YYYY-MM-DD format"},
                "start_time": {"type": "STRING", "description": "Start time HH:MM (24h format)"},
                "end_time": {"type": "STRING", "description": "End time HH:MM (24h format)"},
                "start_date": {"type": "STRING", "description": "Start date for list range"},
                "end_date": {"type": "STRING", "description": "End date for list range"},
                "description": {"type": "STRING", "description": "Event description"},
                "location": {"type": "STRING", "description": "Event location"},
                "event_id": {"type": "STRING", "description": "Event ID for update/delete"},
                "query": {"type": "STRING", "description": "Search query"},
            },
            "required": ["action"],
        },
    },
    {
        "name": "daily_briefing",
        "description": (
            "Provides a daily briefing combining weather, calendar events, unread emails, "
            "and reminders into one summary. Use when the user asks for a morning briefing, "
            "daily update, 'what's on my schedule', or 'give me an overview of today'."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {
                    "type": "STRING",
                    "description": "morning | evening | status | schedule | enable | disable",
                },
                "morning_time": {
                    "type": "STRING",
                    "description": "Time for morning briefing HH:MM (default: 08:00)",
                },
                "evening_time": {
                    "type": "STRING",
                    "description": "Time for evening briefing HH:MM (default: 21:00)",
                },
            },
            "required": ["action"],
        },
    },
    {
        "name": "spotify_controller",
        "description": (
            "Controls Spotify music playback. Use for: playing songs, albums, playlists, "
            "artists, or direct Spotify URLs/URIs; pause/resume, skip, volume, shuffle, "
            "repeat, queue tracks, list playlists, show current playback, search music, "
            "and transfer playback between devices. Use this for ANY music-related request."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {
                    "type": "STRING",
                    "description": "play | pause | resume | next | previous | current | volume | search | queue | playlists | shuffle | repeat | devices | transfer | liked",
                },
                "query": {
                    "type": "STRING",
                    "description": "Song, album, playlist, artist name, or Spotify URL/URI for play/search/queue",
                },
                "kind": {
                    "type": "STRING",
                    "description": "Play target: track | album | playlist | artist | any (defaults to track)",
                },
                "value": {"type": "INTEGER", "description": "Volume level 0-100"},
                "state": {
                    "type": "STRING",
                    "description": "on/off for shuffle, off/track/context for repeat",
                },
                "device_name": {"type": "STRING", "description": "Device name for transfer"},
                "type": {
                    "type": "STRING",
                    "description": "Search type: track | album | playlist | artist | any (default: track)",
                },
                "limit": {
                    "type": "INTEGER",
                    "description": "Maximum search results to return (default: 5)",
                },
                "refresh": {
                    "type": "BOOLEAN",
                    "description": "Bypass the short-lived Spotify cache",
                },
            },
            "required": ["action"],
        },
    },
    {
        "name": "obsidian_manager",
        "description": (
            "Manages Obsidian Vault integration for conversation memory. "
            "Can start/end conversation tracking, search notes, create person/project notes. "
            "Each conversation is saved as a note and automatically linked to related notes using AI."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {
                    "type": "STRING",
                    "description": "start_tracking | end_tracking | search_notes | create_person_note | create_project_note | get_all_notes",
                },
                "user_input": {
                    "type": "STRING",
                    "description": "Initial user input to begin tracking",
                },
                "summary": {
                    "type": "STRING",
                    "description": "Conversation summary (for end_tracking)",
                },
                "query": {"type": "STRING", "description": "Search query (for search_notes)"},
                "name": {"type": "STRING", "description": "Name (for person/project notes)"},
                "information": {
                    "type": "OBJECT",
                    "description": "Information dict (for person/project notes)",
                },
            },
            "required": ["action"],
        },
    },
    {
        "name": "save_memory",
        "description": (
            "Save an important personal fact about the user to long-term memory. "
            "Call this silently whenever the user reveals something worth remembering: "
            "name, age, city, job, preferences, hobbies, relationships, projects, or future plans. "
            "Do NOT call for: weather, reminders, searches, or one-time commands. "
            "Do NOT announce that you are saving — just call it silently. "
            "Values must be in English regardless of the conversation language."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "category": {
                    "type": "STRING",
                    "description": (
                        "identity — name, age, birthday, city, job, language, nationality | "
                        "preferences — favorite food/color/music/film/game/sport, hobbies | "
                        "projects — active projects, goals, things being built | "
                        "relationships — friends, family, partner, colleagues | "
                        "wishes — future plans, things to buy, travel dreams | "
                        "notes — habits, schedule, anything else worth remembering"
                    ),
                },
                "key": {
                    "type": "STRING",
                    "description": "Short snake_case key (e.g. name, favorite_food, sister_name)",
                },
                "value": {
                    "type": "STRING",
                    "description": "Concise value in English (e.g. Fatih, pizza, older sister)",
                },
            },
            "required": ["category", "key", "value"],
        },
    },
    {
        "name": "roblox_controller",
        "description": (
            "Controls Roblox gameplay autonomously using AI and computer vision. "
            "Can play games automatically until a goal is reached or continuously. "
            "Uses screen capture and AI decision-making to play games. "
            "Supports multiple game types with specialized strategies."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "start | stop | status | set_goal"},
                "strategy": {
                    "type": "STRING",
                    "description": "Gameplay strategy: aggressive | defensive | balanced | farming (default: balanced)",
                },
                "game_type": {
                    "type": "STRING",
                    "description": "Type of Roblox game: tycoon | obby | simulator | battle_royale | racing | survival | war_tycoon | ring_farm | generic (default: generic)",
                },
                "goal": {
                    "type": "OBJECT",
                    "description": 'Target goal to achieve, e.g., {"type": "score", "target": 1000} or {"type": "coins", "target": 500}',
                },
            },
            "required": ["action"],
        },
    },
]

FEATURE_TOOL_DECLARATIONS = [
    {
        "name": "passive_vision",
        "description": (
            "Manages passive screen memory. Use this to start, stop, inspect, or query "
            "recent visual memory captured from the screen."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {
                    "type": "STRING",
                    "description": "start | stop | status | query | recent | save",
                },
                "question": {"type": "STRING", "description": "Question for visual memory query"},
                "minutes": {"type": "INTEGER", "description": "How many recent minutes to inspect"},
            },
            "required": ["action"],
        },
    },
    {
        "name": "semantic_search",
        "description": (
            "Indexes and searches local documents semantically. Use this for searching, "
            "asking questions about indexed files, or checking vector index status."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {
                    "type": "STRING",
                    "description": "index_directory | search | ask | stats | clear",
                },
                "path": {"type": "STRING", "description": "Directory path to index"},
                "query": {"type": "STRING", "description": "Search query or question"},
                "max_results": {"type": "INTEGER", "description": "Maximum number of results"},
            },
            "required": ["action"],
        },
    },
    {
        "name": "proactive_suggestions",
        "description": (
            "Shows or manages proactive suggestions gathered from recent user activity."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "list | clear | dismiss"},
                "index": {"type": "INTEGER", "description": "Suggestion index to dismiss"},
            },
            "required": ["action"],
        },
    },
    {
        "name": "cross_device",
        "description": (
            "Sends summaries, reminders, files, or completion notices to connected Telegram "
            "or Discord devices."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {
                    "type": "STRING",
                    "description": "send_summary | send_reminder | send_task_completion | send_file | status",
                },
                "message": {"type": "STRING", "description": "Summary or reminder message"},
                "task": {"type": "STRING", "description": "Task label for completion notices"},
                "result": {"type": "STRING", "description": "Completion result text"},
                "platform": {"type": "STRING", "description": "telegram | discord | both"},
                "file_path": {"type": "STRING", "description": "File path to send"},
                "caption": {"type": "STRING", "description": "Optional caption for file send"},
            },
            "required": ["action"],
        },
    },
    {
        "name": "vscode_bridge",
        "description": (
            "Talks to the optional VS Code bridge extension for selection, diagnostics, "
            "insertions, refactors, and run commands."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {
                    "type": "STRING",
                    "description": "connect | diagnostics | get_selection | insert_text | run_code | edit_file | refactor",
                },
                "file_path": {"type": "STRING", "description": "Target file path"},
                "old_text": {"type": "STRING", "description": "Text to replace"},
                "new_text": {"type": "STRING", "description": "Replacement text"},
                "pattern": {"type": "STRING", "description": "Pattern for refactor"},
                "replacement": {"type": "STRING", "description": "Replacement for refactor"},
                "text": {"type": "STRING", "description": "Text to insert"},
                "language": {"type": "STRING", "description": "Language for run_code"},
            },
            "required": ["action"],
        },
    },
    {
        "name": "system_diagnostics",
        "description": (
            "Runs an installation and runtime health check for JARVIS and reports whether "
            "the environment is ready."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "verbose": {"type": "BOOLEAN", "description": "Include module-by-module detail"},
            },
            "required": [],
        },
    },
]

# JarvisLive class has been moved to core/jarvis_live.py


def main():
    """Main entry point for JARVIS AI Assistant."""
    # Check for --gui argument
    use_gui = "--gui" in sys.argv
    
    if use_gui:
        print("=" * 60)
        print("JARVIS AI Assistant - GUI Mode")
        print("=" * 60)
        print("Starting JARVIS with Qt window...")
        print()
        
        # Import Qt components
        try:
            from PyQt6.QtWidgets import QApplication
            app = QApplication(sys.argv)
            app.setApplicationName("JARVIS")
        except Exception:
            app = None
        
        ui = JarvisUI(str(BASE_DIR / "face.png"))
    else:
        print("=" * 60)
        print("JARVIS AI Assistant - CLI Mode")
        print("=" * 60)
        print("Starting JARVIS in text-only mode...")
        print()
        
        # Create minimal CLI UI bridge
        class CLIUIBridge:
            """Minimal UI bridge for CLI mode without Qt/GUI components."""
            def __init__(self):
                self._muted = False
                self._current_file = None
                self._state = "LISTENING"
                self._on_text_command = None
            
            @property
            def muted(self):
                return self._muted
            
            @muted.setter
            def muted(self, value):
                self._muted = value
                print(f"[CLI] Microphone {'muted' if value else 'active'}")
            
            @property
            def current_file(self):
                return self._current_file
            
            @current_file.setter
            def current_file(self, value):
                self._current_file = value
                if value:
                    print(f"[CLI] Current file: {value}")
            
            @property
            def on_text_command(self):
                return self._on_text_command
            
            @on_text_command.setter
            def on_text_command(self, cb):
                self._on_text_command = cb
            
            def set_state(self, state):
                """Set the current state of JARVIS."""
                self._state = state
                print(f"[CLI] State: {state}")
            
            def write_log(self, message):
                print(f"[LOG] {message}")
            
            def wait_for_api_key(self):
                """Wait for API key - CLI mode assumes key is already configured."""
                print("[CLI] Assuming API key is configured in .env file")
            
            def root(self):
                """No root.mainloop in CLI mode."""
                pass

        ui = CLIUIBridge()

    # Load configuration
    config = get_config()

    # Initialize safety and approval system
    approval_flow = get_approval_flow()
    permission_profile = config.get("security.permission_profile", "normal")
    approval_flow.set_permission_level(permission_profile)

    # Configure confirmation requirements
    confirm_medium = config.get("security.confirmation_medium_risk", True)
    confirm_high = config.get("security.confirmation_high_risk", True)
    approval_flow.set_require_confirmation_for_medium(confirm_medium)

    # Load disabled actions from config
    disabled_actions = config.get("security.disabled_actions", [])
    for action in disabled_actions:
        disable_action(action)

    logger.info(
        f"Safety system initialized: profile={permission_profile}, "
        f"confirm_medium={confirm_medium}, confirm_high={confirm_high}, "
        f"disabled_actions={len(disabled_actions)}"
    )

    # Initialize action history
    action_history = get_action_history()
    if config.get("security.action_history_enabled", True):
        max_size = config.get("security.action_history_max_size", 1000)
        action_history._max_history_size = max_size
        logger.info(f"Action history enabled with max_size={max_size}")
    else:
        logger.info("Action history disabled by configuration")

    # Run setup check on first start (optional)
    setup_flow = get_setup_flow(BASE_DIR)
    try:
        # Only run setup check if config file doesn't exist or is new
        config_file = BASE_DIR / "config.yaml"
        if not config_file.exists() or config_file.stat().st_size < 100:
            logger.info("Running first-time setup check...")
            setup_report = setup_flow.run_all_checks()
            if setup_report.overall_status.value in ["failed", "warning"]:
                logger.warning(
                    "Setup check found issues:\n" + setup_flow.format_report(verbose=True)
                )
            else:
                logger.info("Setup check passed")
    except Exception as e:
        logger.warning(f"Setup check failed: {e}")

    # Initialize performance tracking
    if config.get("performance.enabled", True):
        perf_tracker = get_performance_tracker()
        perf_monitor = get_performance_monitor()

        # Configure thresholds
        slow_threshold = config.get("performance.slow_operation_threshold_ms", 2000)
        alert_threshold = config.get("performance.alert_threshold_ms", 5000)
        perf_tracker.slow_operation_threshold_ms = slow_threshold
        perf_tracker.alert_threshold_ms = alert_threshold

        # Start resource monitoring if enabled
        if config.get("performance.resource_monitoring", True):
            resource_interval = config.get("performance.resource_interval_seconds", 60)
            perf_monitor.resource_interval_seconds = resource_interval
            perf_monitor.start_monitoring()

        # Start background task manager if enabled
        if config.get("performance.background_tasks_enabled", True):
            bg_manager = get_background_task_manager()
            bg_workers = config.get("performance.background_workers", 4)
            bg_manager.max_workers = bg_workers
            bg_manager.start()

        # Initialize action loader for lazy loading
        if config.get("performance.flags.lazy_load_actions", False):
            action_loader = _get_action_loader()
            # Preload critical actions
            critical_actions = [
                "file_processor",
                "web_search",
                "computer_control",
                "gmail_manager",
                "calendar_manager",
            ]
            action_loader.preload_actions(critical_actions)

        # Initialize memory manager
        if config.get("performance.flags.reduce_memory_footprint", False):
            memory_manager = get_memory_manager()
            memory_manager.start_gc_thread()
            logger.info("Memory manager started with GC thread")

        logger.info("Performance tracking system initialized")
    else:
        logger.info("Performance tracking disabled by configuration")

    # Initialize workflow engine
    if config.get("workflow.enabled", True):
        workflow_engine = get_workflow_engine()
        max_concurrent = config.get("workflow.max_concurrent_workflows", 2)
        workflow_engine.max_concurrent_workflows = max_concurrent

        # Configure persistence
        if config.get("workflow.persistence_enabled", True):
            persistence_dir = config.get(
                "workflow.persistence_dir",
                str(project_path("data", "workflows")),
            )
            workflow_engine.persistence_dir = resolve_relative_path(persistence_dir)
            workflow_engine.persistence_dir.mkdir(parents=True, exist_ok=True)
            workflow_engine.persistence_file = (
                workflow_engine.persistence_dir / "workflows.json"
            )

        # Start executor
        workflow_engine.start_executor()

        # Auto-cleanup old workflows
        cleanup_hours = config.get("workflow.auto_cleanup_hours", 168)
        workflow_engine.cleanup_old_workflows(max_age_hours=cleanup_hours)

        logger.info("Workflow engine initialized")
    else:
        logger.info("Workflow engine disabled by configuration")

    # Initialize local analyzer
    if config.get("local_analysis.enabled", True):
        local_analyzer = get_local_analyzer()
        cache_size = config.get("local_analysis.max_cache_size", 1000)
        local_analyzer.max_cache_size = cache_size
        logger.info("Local analyzer initialized")
    else:
        logger.info("Local analyzer disabled by configuration")

    # Initialize morning routine
    if config.get("morning_routine.enabled", False):
        mode_str = config.get("morning_routine.mode", "manual")
        mode = RoutineMode(mode_str) if mode_str else RoutineMode.MANUAL

        routine_config = RoutineConfig(
            mode=mode,
            reminder_time=config.get("morning_routine.reminder_time", "08:00"),
            reminder_window_minutes=config.get("morning_routine.reminder_window_minutes", 60),
            photo_directory=config.get("morning_routine.photo_directory") or None,
            auto_analyze=config.get("morning_routine.auto_analyze", True),
            send_reminder_if_missed=config.get("morning_routine.send_reminder_if_missed", True),
            reminder_delay_minutes=config.get("morning_routine.reminder_delay_minutes", 120),
        )

        morning_routine = get_morning_routine(routine_config)
        morning_routine.start_monitoring()

        logger.info(f"Morning routine initialized (mode: {mode.value})")
    else:
        logger.info("Morning routine disabled by configuration")

    # Initialize hybrid retrieval
    if config.get("memory_retrieval.enabled", True):
        hybrid_retrieval = get_hybrid_retrieval()
        hybrid_retrieval.semantic_weight = config.get("memory_retrieval.semantic_weight", 0.4)
        hybrid_retrieval.keyword_weight = config.get("memory_retrieval.keyword_weight", 0.3)
        hybrid_retrieval.time_weight = config.get("memory_retrieval.time_weight", 0.2)
        hybrid_retrieval.confidence_weight = config.get(
            "memory_retrieval.confidence_weight", 0.1
        )
        hybrid_retrieval.max_results = config.get("memory_retrieval.max_results", 10)
        hybrid_retrieval.min_relevance_threshold = config.get(
            "memory_retrieval.min_relevance_threshold", 0.3
        )
        logger.info("Hybrid retrieval initialized")
    else:
        logger.info("Hybrid retrieval disabled by configuration")

    # Initialize multimodal context
    multimodal_context = get_multimodal_context()
    logger.info("Multimodal context processor initialized")

    # Initialize memory backup manager
    backup_manager = get_backup_manager()
    backup_manager.start_automatic_backup()
    logger.info("Memory backup system started")

    # Initialize performance monitoring
    perf_monitor = get_performance_monitor()
    perf_monitor.start_monitoring()
    logger.info("Performance monitoring started")

    # Verify memory integrity
    is_valid, message = backup_manager.verify_memory_integrity()
    if not is_valid:
        logger.warning(f"Memory integrity check failed: {message}")
        logger.info("Attempting emergency recovery...")
        if backup_manager.emergency_recovery():
            logger.info("Emergency recovery successful")
        else:
            logger.error("Emergency recovery failed")

    if use_gui:
        # GUI mode: use threading and mainloop
        def runner():
            ui.wait_for_api_key()
            jarvis = JarvisLive(ui)
            try:
                asyncio.run(jarvis.run())
            except KeyboardInterrupt:
                logger.info("Shutting down...")
            finally:
                # Cleanup
                get_session_manager().finalize_session()
                backup_manager.stop_automatic_backup()
                perf_monitor.stop_monitoring()
                logger.info("Systems shutdown complete")

        threading.Thread(target=runner, daemon=True).start()
        ui.root.mainloop()
    else:
        # CLI mode: run directly
        print()
        print("JARVIS is ready in CLI mode!")
        print("Press Ctrl+C to exit")
        print("=" * 60)
        print()

        jarvis = JarvisLive(ui)
        try:
            asyncio.run(jarvis.run())
        except KeyboardInterrupt:
            logger.info("Shutting down...")
            print()
            print("JARVIS shutting down...")
        finally:
            # Cleanup
            get_session_manager().finalize_session()
            backup_manager.stop_automatic_backup()
            perf_monitor.stop_monitoring()
            logger.info("Systems shutdown complete")
            print("Shutdown complete.")


if __name__ == "__main__":
    main()
