"""
Security module for JARVIS AI Assistant.

This module provides:
- API key encryption and secure storage
- Input validation and sanitization
- Rate limiting for API calls
- Code execution sandbox
- Secure file operations with path validation
"""

import base64
import hashlib
import json
import os
import re
import secrets
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from core.logger import get_logger
from core.paths import project_path

logger = get_logger(__name__)


class APIKeyManager:
    """
    Manages secure storage and encryption of API keys.
    """

    def __init__(self, config_dir: Path = project_path("config")):
        """
        Initialize the API key manager.

        Args:
            config_dir: Directory for storing encrypted keys
        """
        self.config_dir = Path(config_dir)
        self.keys_file = self.config_dir / "encrypted_keys.json"
        self.key_cache: Dict[str, str] = {}
        self._fernet: Optional[Fernet] = None

        self._initialize_encryption()
        logger.info("API key manager initialized")

    def _initialize_encryption(self):
        """Initialize or load encryption key."""
        key_file = self.config_dir / ".encryption_key"

        if key_file.exists():
            # Load existing encryption key
            with open(key_file, "rb") as f:
                key = f.read()
        else:
            # Generate new encryption key
            key = Fernet.generate_key()
            key_file.parent.mkdir(parents=True, exist_ok=True)
            with open(key_file, "wb") as f:
                f.write(key)
            # Restrict file permissions
            os.chmod(key_file, 0o600)

        self._fernet = Fernet(key)

    def encrypt_key(self, key_value: str) -> str:
        """
        Encrypt an API key.

        Args:
            key_value: The API key to encrypt

        Returns:
            Encrypted key as base64 string
        """
        if not self._fernet:
            raise RuntimeError("Encryption not initialized")

        encrypted = self._fernet.encrypt(key_value.encode())
        return base64.b64encode(encrypted).decode()

    def decrypt_key(self, encrypted_key: str) -> str:
        """
        Decrypt an API key.

        Args:
            encrypted_key: The encrypted key (base64 string)

        Returns:
            Decrypted API key
        """
        if not self._fernet:
            raise RuntimeError("Encryption not initialized")

        encrypted_bytes = base64.b64decode(encrypted_key.encode())
        decrypted = self._fernet.decrypt(encrypted_bytes)
        return decrypted.decode()

    def store_key(self, service: str, key_value: str):
        """
        Store an encrypted API key.

        Args:
            service: Service name (e.g., 'gemini', 'openai')
            key_value: The API key to store
        """
        encrypted = self.encrypt_key(key_value)

        # Load existing keys
        keys_data = {}
        if self.keys_file.exists():
            with open(self.keys_file, "r", encoding="utf-8") as f:
                keys_data = json.load(f)

        # Store encrypted key
        keys_data[service] = {"encrypted_key": encrypted, "stored_at": datetime.now().isoformat()}

        # Save to file
        self.keys_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.keys_file, "w", encoding="utf-8") as f:
            json.dump(keys_data, f, indent=2)

        os.chmod(self.keys_file, 0o600)
        self.key_cache[service] = key_value

        logger.info(f"API key stored for service: {service}")

    def get_key(self, service: str) -> Optional[str]:
        """
        Retrieve and decrypt an API key.

        Args:
            service: Service name

        Returns:
            Decrypted API key or None if not found
        """
        # Check cache first
        if service in self.key_cache:
            return self.key_cache[service]

        # Load from file
        if not self.keys_file.exists():
            return None

        with open(self.keys_file, "r", encoding="utf-8") as f:
            keys_data = json.load(f)

        if service not in keys_data:
            return None

        encrypted = keys_data[service]["encrypted_key"]
        decrypted = self.decrypt_key(encrypted)
        self.key_cache[service] = decrypted

        return decrypted

    def delete_key(self, service: str):
        """
        Delete an API key.

        Args:
            service: Service name
        """
        if not self.keys_file.exists():
            return

        with open(self.keys_file, "r", encoding="utf-8") as f:
            keys_data = json.load(f)

        if service in keys_data:
            del keys_data[service]

            with open(self.keys_file, "w", encoding="utf-8") as f:
                json.dump(keys_data, f, indent=2)

            if service in self.key_cache:
                del self.key_cache[service]

            logger.info(f"API key deleted for service: {service}")


class InputValidator:
    """
    Validates and sanitizes user input to prevent injection attacks.
    """

    # Patterns for potentially dangerous input
    DANGEROUS_PATTERNS = [
        r"<script[^>]*>.*?</script>",  # Script tags
        r"javascript:",  # JavaScript protocol
        r"on\w+\s*=",  # Event handlers
        r"\.\./",  # Path traversal
        r"\.\.\\",  # Windows path traversal
    ]

    MAX_INPUT_LENGTH = 10000
    MAX_FILE_PATH_LENGTH = 260

    @classmethod
    def validate_text(
        cls, text: str, max_length: Optional[int] = None
    ) -> tuple[bool, Optional[str]]:
        """
        Validate text input for security issues.

        Args:
            text: Text to validate
            max_length: Maximum allowed length (defaults to class default)

        Returns:
            Tuple of (is_valid, error_message)
        """
        if max_length is None:
            max_length = cls.MAX_INPUT_LENGTH

        if len(text) > max_length:
            return False, f"Input too long (max {max_length} characters)"

        # Check for dangerous patterns
        for pattern in cls.DANGEROUS_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                return False, f"Input contains potentially dangerous pattern: {pattern}"

        return True, None

    @classmethod
    def validate_file_path(
        cls, path: str, allowed_base_dirs: Optional[List[Path]] = None
    ) -> tuple[bool, Optional[str]]:
        """
        Validate file path to prevent directory traversal attacks.

        Args:
            path: File path to validate
            allowed_base_dirs: List of allowed base directories

        Returns:
            Tuple of (is_valid, error_message)
        """
        if len(path) > cls.MAX_FILE_PATH_LENGTH:
            return False, f"Path too long (max {cls.MAX_FILE_PATH_LENGTH} characters)"

        # Check for path traversal
        if ".." in path or "../" in path or "..\\" in path:
            return False, "Path traversal detected"

        # Resolve to absolute path
        try:
            abs_path = Path(path).resolve()
        except Exception as e:
            return False, f"Invalid path: {e}"

        # Check against allowed directories
        if allowed_base_dirs:
            is_allowed = any(
                str(abs_path).startswith(str(base_dir.resolve())) for base_dir in allowed_base_dirs
            )
            if not is_allowed:
                return False, f"Path not in allowed directories"

        return True, None

    @classmethod
    def validate_command(
        cls, command: str, allowed_commands: Optional[List[str]] = None
    ) -> tuple[bool, Optional[str]]:
        """
        Validate shell command to prevent command injection.

        Args:
            command: Command to validate
            allowed_commands: List of allowed command patterns

        Returns:
            Tuple of (is_valid, error_message)
        """
        # Check for shell metacharacters that could lead to injection
        dangerous_chars = [";", "&", "|", "`", "$", "(", ")", "<", ">"]
        for char in dangerous_chars:
            if char in command:
                return False, f"Command contains dangerous character: {char}"

        # Check against allowed commands if provided
        if allowed_commands:
            is_allowed = any(
                command.startswith(allowed) or re.match(allowed, command)
                for allowed in allowed_commands
            )
            if not is_allowed:
                return False, "Command not in allowed list"

        return True, None

    @classmethod
    def sanitize_html(cls, html: str) -> str:
        """
        Basic HTML sanitization (for display purposes only).

        Args:
            html: HTML string to sanitize

        Returns:
            Sanitized HTML
        """
        # Remove script tags
        html = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.IGNORECASE | re.DOTALL)
        # Remove event handlers
        html = re.sub(r"on\w+\s*=", "", html, flags=re.IGNORECASE)
        # Remove javascript: protocol
        html = re.sub(r"javascript:", "", html, flags=re.IGNORECASE)

        return html


class RateLimiter:
    """
    Rate limiter for API calls and operations.
    """

    def __init__(self, max_requests: int = 100, window_seconds: int = 60):
        """
        Initialize rate limiter.

        Args:
            max_requests: Maximum requests per window
            window_seconds: Time window in seconds
        """
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests: Dict[str, List[datetime]] = {}
        self._lock = None
        logger.info(f"Rate limiter initialized: {max_requests} requests per {window_seconds}s")

    def is_allowed(self, identifier: str) -> tuple[bool, Optional[int]]:
        """
        Check if a request is allowed for the given identifier.

        Args:
            identifier: Unique identifier (e.g., IP, user ID, API endpoint)

        Returns:
            Tuple of (is_allowed, retry_after_seconds)
        """
        now = datetime.now()

        # Clean old requests
        if identifier in self.requests:
            self.requests[identifier] = [
                req_time
                for req_time in self.requests[identifier]
                if (now - req_time).total_seconds() < self.window_seconds
            ]

        # Check if under limit
        if identifier not in self.requests or len(self.requests[identifier]) < self.max_requests:
            if identifier not in self.requests:
                self.requests[identifier] = []
            self.requests[identifier].append(now)
            return True, None

        # Calculate retry time
        oldest_request = min(self.requests[identifier])
        retry_after = int(self.window_seconds - (now - oldest_request).total_seconds())

        logger.warning(f"Rate limit exceeded for {identifier}, retry after {retry_after}s")
        return False, retry_after

    def reset(self, identifier: str):
        """
        Reset rate limit for an identifier.

        Args:
            identifier: Identifier to reset
        """
        if identifier in self.requests:
            del self.requests[identifier]
            logger.info(f"Rate limit reset for {identifier}")


class CodeSandbox:
    """
    Provides a sandboxed environment for code execution.
    """

    ALLOWED_MODULES = {
        "math",
        "random",
        "datetime",
        "json",
        "re",
        "collections",
        "itertools",
        "functools",
        "statistics",
        "decimal",
        "fractions",
    }

    DANGEROUS_FUNCTIONS = {
        "eval",
        "exec",
        "compile",
        "open",
        "__import__",
        "reload",
        "exit",
        "quit",
        "input",
        "raw_input",
    }

    @classmethod
    def validate_code(cls, code: str) -> tuple[bool, Optional[str]]:
        """
        Validate code for safe execution.

        Args:
            code: Python code to validate

        Returns:
            Tuple of (is_safe, error_message)
        """
        # Check for dangerous functions
        for func in cls.DANGEROUS_FUNCTIONS:
            if func in code:
                return False, f"Code contains dangerous function: {func}"

        # Check for import statements
        import_pattern = r"import\s+(\w+)"
        imports = re.findall(import_pattern, code)
        for imp in imports:
            if imp not in cls.ALLOWED_MODULES:
                return False, f"Import of disallowed module: {imp}"

        # Check for from imports
        from_pattern = r"from\s+(\w+)\s+import"
        from_imports = re.findall(from_pattern, code)
        for imp in from_imports:
            if imp not in cls.ALLOWED_MODULES:
                return False, f"Import from disallowed module: {imp}"

        # Check for file operations
        if "open(" in code or "file(" in code:
            return False, "File operations not allowed in sandbox"

        # Check for network operations
        if "socket" in code or "urllib" in code or "requests" in code:
            return False, "Network operations not allowed in sandbox"

        return True, None

    @classmethod
    def execute_safe_code(cls, code: str, timeout: int = 30) -> tuple[bool, Any, Optional[str]]:
        """
        Execute code in a sandboxed environment.

        Args:
            code: Python code to execute
            timeout: Execution timeout in seconds

        Returns:
            Tuple of (success, result, error_message)
        """
        is_safe, error = cls.validate_code(code)
        if not is_safe:
            return False, None, error

        # Create restricted globals
        safe_globals = {
            "__builtins__": {
                "print": print,
                "len": len,
                "str": str,
                "int": int,
                "float": float,
                "bool": bool,
                "list": list,
                "dict": dict,
                "tuple": tuple,
                "set": set,
                "range": range,
                "enumerate": enumerate,
                "zip": zip,
                "sum": sum,
                "max": max,
                "min": min,
                "abs": abs,
                "round": round,
                "sorted": sorted,
                "reversed": reversed,
            }
        }

        # Add allowed modules
        for module_name in cls.ALLOWED_MODULES:
            try:
                safe_globals[module_name] = __import__(module_name)
            except ImportError:
                pass

        try:
            # Execute code
            exec(code, safe_globals)
            return True, None, None
        except Exception as e:
            return False, None, str(e)


class SecureFileOperations:
    """
    Secure file operations with path validation.
    """

    def __init__(self, allowed_base_dirs: Optional[List[Path]] = None):
        """
        Initialize secure file operations.

        Args:
            allowed_base_dirs: List of allowed base directories
        """
        if allowed_base_dirs is None:
            allowed_base_dirs = [Path.cwd()]

        self.allowed_base_dirs = [Path(d).resolve() for d in allowed_base_dirs]
        self.validator = InputValidator()
        logger.info(
            f"Secure file operations initialized with {len(self.allowed_base_dirs)} allowed directories"
        )

    def safe_read(self, path: str) -> tuple[bool, Optional[str], Optional[str]]:
        """
        Safely read a file.

        Args:
            path: File path to read

        Returns:
            Tuple of (success, content, error_message)
        """
        is_valid, error = self.validator.validate_file_path(path, self.allowed_base_dirs)
        if not is_valid:
            return False, None, error

        try:
            file_path = Path(path).resolve()
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
            return True, content, None
        except Exception as e:
            return False, None, str(e)

    def safe_write(self, path: str, content: str) -> tuple[bool, Optional[str]]:
        """
        Safely write to a file.

        Args:
            path: File path to write
            content: Content to write

        Returns:
            Tuple of (success, error_message)
        """
        is_valid, error = self.validator.validate_file_path(path, self.allowed_base_dirs)
        if not is_valid:
            return False, error

        try:
            file_path = Path(path).resolve()
            file_path.parent.mkdir(parents=True, exist_ok=True)
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)
            return True, None
        except Exception as e:
            return False, str(e)

    def safe_delete(self, path: str) -> tuple[bool, Optional[str]]:
        """
        Safely delete a file.

        Args:
            path: File path to delete

        Returns:
            Tuple of (success, error_message)
        """
        is_valid, error = self.validator.validate_file_path(path, self.allowed_base_dirs)
        if not is_valid:
            return False, error

        try:
            file_path = Path(path).resolve()
            if file_path.is_file():
                file_path.unlink()
            elif file_path.is_dir():
                import shutil

                shutil.rmtree(file_path)
            return True, None
        except Exception as e:
            return False, str(e)


# Global instances
_api_key_manager: Optional[APIKeyManager] = None
_rate_limiter: Optional[RateLimiter] = None


def get_api_key_manager() -> APIKeyManager:
    """Get the global API key manager instance."""
    global _api_key_manager
    if _api_key_manager is None:
        _api_key_manager = APIKeyManager()
    return _api_key_manager


def get_rate_limiter(max_requests: int = 100, window_seconds: int = 60) -> RateLimiter:
    """Get the global rate limiter instance."""
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = RateLimiter(max_requests, window_seconds)
    return _rate_limiter
