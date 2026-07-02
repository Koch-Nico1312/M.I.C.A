"""Example manifest-based Jarvis plugin."""

TOOL_DECLARATION = {
    "name": "example_echo",
    "description": "Echoes a short text payload for plugin health checks.",
    "parameters": {
        "type": "object",
        "properties": {
            "text": {"type": "string", "description": "Text to echo."}
        },
        "required": ["text"],
    },
    "category": "example",
    "enabled": True,
}


def example_echo(parameters: dict, **_kwargs) -> str:
    return str(parameters.get("text", ""))[:200]
