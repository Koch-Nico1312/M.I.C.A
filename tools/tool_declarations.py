"""
Tool declarations for JARVIS AI Assistant.

This module contains all tool declarations used by the AI system.
Tools are separated into core tools (TOOL_DECLARATIONS) and feature tools (FEATURE_TOOL_DECLARATIONS).
"""

from typing import List, Dict, Any

# Core tool declarations - always available
TOOL_DECLARATIONS: List[Dict[str, Any]] = [
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
        "name": "self_dev_agent",
        "description": (
            "Runs controlled self-development cycles for the Jarvis repository. "
            "Use for repo status, branch creation, test runs, diff review, and applying provided unified diffs. "
            "Never merges automatically."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {
                    "type": "STRING",
                    "description": "status | branch | plan | test | review | patch | cycle",
                },
                "goal": {"type": "STRING", "description": "Development goal or improvement request"},
                "branch": {"type": "STRING", "description": "Optional codex/* branch name"},
                "test_command": {
                    "type": "STRING",
                    "description": "Test command to run, default: pytest -q",
                },
                "timeout": {"type": "INTEGER", "description": "Command timeout in seconds"},
                "patch": {
                    "type": "STRING",
                    "description": "Unified diff to validate and apply for patch action",
                },
                "context": {"type": "STRING", "description": "Extra review/planning context"},
                "use_model": {
                    "type": "BOOLEAN",
                    "description": "Allow routed model to draft plan/review text",
                },
                "create_branch": {
                    "type": "BOOLEAN",
                    "description": "Create a codex/self-dev branch during cycle action",
                },
            },
            "required": ["action"],
        },
    },
    {
        "name": "daily_mode",
        "description": (
            "Lists or applies daily-driver mode presets such as safe, work, focus, offline, and admin."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "list | apply"},
                "mode": {"type": "STRING", "description": "safe | work | focus | offline | admin"},
            },
            "required": ["action"],
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
            "name, age, city, job, preferences, hobbies, relationships, projects, future plans, or durable facts learned from conversation. "
            "Also use it for direct requests like 'füge ... hinzu', 'merke dir ...', or 'remember that ...'. "
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
                        "knowledge — durable facts learned from conversation | "
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
        "name": "memory_brain",
        "description": (
            "Queries, summarizes, or forgets entries from JARVIS long-term memory. "
            "Use this when the user asks what JARVIS remembers, wants a summary of stored facts, "
            "or asks to delete a memory."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {
                    "type": "STRING",
                    "description": "query | summary | forget | status",
                },
                "query": {
                    "type": "STRING",
                    "description": "Search term or memory topic, e.g. name, city, projects, football",
                },
                "limit": {
                    "type": "INTEGER",
                    "description": "Maximum number of entries to return for summaries",
                },
            },
            "required": ["action"],
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

# Feature tool declarations - only available when features are enabled
FEATURE_TOOL_DECLARATIONS: List[Dict[str, Any]] = [
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
