from __future__ import annotations

"""
Cross-Device Handover System
Send summaries/reminders to phone via Telegram or Discord
"""

import asyncio
import json
from datetime import datetime
from pathlib import Path
from uuid import uuid4
from typing import Dict, List, Optional

try:
    import aiohttp

    AIOHTTP_AVAILABLE = True
except ImportError:
    AIOHTTP_AVAILABLE = False

from config.config_loader import get_config


class CrossDevice:
    """Local device/session registry used by tests and non-network handoff flows."""

    def __init__(self):
        self.devices: Dict[str, dict] = {}
        self.sessions: Dict[str, dict] = {}
        self.enable_discovery = False
        self.discovery_active = False

    def register_device(
        self, device_name: str, device_type: str, capabilities: List[str] | None = None
    ) -> str:
        device_id = f"{device_type}_{uuid4().hex[:10]}"
        self.devices[device_id] = {
            "device_id": device_id,
            "device_name": device_name,
            "device_type": device_type,
            "capabilities": list(capabilities or []),
            "registered_at": datetime.now().isoformat(),
            "last_sync": None,
        }
        return device_id

    def get_device(self, device_id: str) -> Optional[dict]:
        return self.devices.get(device_id)

    def get_devices(self) -> List[dict]:
        return list(self.devices.values())

    def unregister_device(self, device_id: str) -> bool:
        if device_id not in self.devices:
            return False
        del self.devices[device_id]
        return True

    def create_session(self, device_id: str) -> str:
        if device_id not in self.devices:
            raise KeyError(device_id)
        session_id = f"session_{uuid4().hex[:10]}"
        self.sessions[session_id] = {
            "session_id": session_id,
            "current_device": device_id,
            "origin_device": device_id,
            "messages": [],
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
        }
        return session_id

    def get_session(self, session_id: str) -> Optional[dict]:
        return self.sessions.get(session_id)

    def get_active_sessions(self) -> List[dict]:
        return list(self.sessions.values())

    def add_message_to_session(self, session_id: str, role: str, content: str) -> bool:
        session = self.sessions.get(session_id)
        if not session:
            return False
        session["messages"].append(
            {"role": role, "content": content, "timestamp": datetime.now().isoformat()}
        )
        session["updated_at"] = datetime.now().isoformat()
        return True

    def handoff_session(self, session_id: str, from_device: str, to_device: str) -> bool:
        session = self.sessions.get(session_id)
        if not session or from_device not in self.devices or to_device not in self.devices:
            return False
        if session.get("current_device") != from_device:
            return False
        session["current_device"] = to_device
        session["updated_at"] = datetime.now().isoformat()
        return True

    def sync_devices(self, from_device: str, to_device: str) -> bool:
        if from_device not in self.devices or to_device not in self.devices:
            return False
        now = datetime.now().isoformat()
        self.devices[from_device]["last_sync"] = now
        self.devices[to_device]["last_sync"] = now
        return True

    def sync_all_devices(self) -> bool:
        now = datetime.now().isoformat()
        for device in self.devices.values():
            device["last_sync"] = now
        return True

    def device_has_capability(self, device_id: str, capability: str | None) -> bool:
        if not capability:
            return False
        device = self.devices.get(device_id)
        return bool(device and capability in device.get("capabilities", []))

    def start_discovery(self) -> None:
        self.discovery_active = bool(self.enable_discovery)


class TelegramBot:
    """Telegram bot integration"""

    def __init__(self, bot_token: str, chat_id: str):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.base_url = f"https://api.telegram.org/bot{bot_token}"
        self.session: Optional[aiohttp.ClientSession] = None

    async def send_message(
        self,
        text: str,
        parse_mode: str = "Markdown",
        *,
        chat_id: str | None = None,
        reply_markup: dict | None = None,
    ) -> bool:
        """Send a message via Telegram"""
        try:
            url = f"{self.base_url}/sendMessage"
            data = {"chat_id": chat_id or self.chat_id, "text": text}
            if parse_mode:
                data["parse_mode"] = parse_mode
            if reply_markup:
                data["reply_markup"] = reply_markup

            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=data) as response:
                    result = await response.json()
                    return result.get("ok", False)

        except Exception as e:
            print(f"[Telegram] ❌ Send error: {e}")
            return False

    async def send_file(self, file_path: str, caption: str = "") -> bool:
        """Send a file via Telegram"""
        try:
            url = f"{self.base_url}/sendDocument"

            with open(file_path, "rb") as f:
                data = aiohttp.FormData()
                data.add_field("chat_id", self.chat_id)
                data.add_field("document", f, filename=file_path.split("/")[-1])
                if caption:
                    data.add_field("caption", caption)

                async with aiohttp.ClientSession() as session:
                    async with session.post(url, data=data) as response:
                        result = await response.json()
                        return result.get("ok", False)

        except Exception as e:
            print(f"[Telegram] ❌ File send error: {e}")
            return False

    async def get_updates(self, offset: int = 0, timeout: int = 0) -> list[dict]:
        """Fetch Telegram updates for local long-polling mode."""
        try:
            url = f"{self.base_url}/getUpdates"
            payload = {
                "offset": max(0, int(offset)),
                "timeout": max(0, min(30, int(timeout))),
                "allowed_updates": ["message", "callback_query"],
            }
            client_timeout = aiohttp.ClientTimeout(total=max(10, payload["timeout"] + 5))
            async with aiohttp.ClientSession(timeout=client_timeout) as session:
                async with session.post(url, json=payload) as response:
                    result = await response.json()
            if not result.get("ok"):
                raise RuntimeError(str(result.get("description") or "Telegram update request failed"))
            return [item for item in result.get("result", []) if isinstance(item, dict)]
        except Exception as exc:
            print(f"[Telegram] ❌ Poll error: {exc}")
            return []

    async def answer_callback(self, callback_query_id: str, text: str = "") -> bool:
        """Acknowledge an inline-button callback."""
        try:
            url = f"{self.base_url}/answerCallbackQuery"
            payload = {"callback_query_id": callback_query_id, "text": text[:180]}
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload) as response:
                    result = await response.json()
            return bool(result.get("ok"))
        except Exception as exc:
            print(f"[Telegram] ❌ Callback error: {exc}")
            return False

    async def resolve_file(self, file_id: str) -> str:
        """Return the authenticated Telegram download URL for a file id."""
        try:
            url = f"{self.base_url}/getFile"
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json={"file_id": file_id}) as response:
                    result = await response.json()
            file_path = str((result.get("result") or {}).get("file_path") or "")
            return f"https://api.telegram.org/file/bot{self.bot_token}/{file_path}" if file_path else ""
        except Exception as exc:
            print(f"[Telegram] ❌ File lookup error: {exc}")
            return ""

    async def download_file(self, file_id: str, destination: str | Path) -> str:
        """Download a Telegram attachment without exposing the bot token to callers."""
        download_url = await self.resolve_file(file_id)
        if not download_url:
            return ""
        target = Path(destination)
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(download_url) as response:
                    if response.status != 200:
                        return ""
                    target.write_bytes(await response.read())
            return str(target)
        except Exception as exc:
            print(f"[Telegram] ❌ File download error: {exc}")
            return ""

    async def close(self):
        """Close the session"""
        if self.session:
            await self.session.close()


class DiscordBot:
    """Discord bot integration"""

    def __init__(self, bot_token: str, channel_id: str):
        self.bot_token = bot_token
        self.channel_id = channel_id
        self.base_url = "https://discord.com/api/v10"
        self.session: Optional[aiohttp.ClientSession] = None

    async def send_message(self, text: str) -> bool:
        """Send a message via Discord"""
        try:
            url = f"{self.base_url}/channels/{self.channel_id}/messages"
            headers = {"Authorization": f"Bot {self.bot_token}", "Content-Type": "application/json"}
            data = {"content": text}

            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, json=data) as response:
                    return response.status in {200, 201}

        except Exception as e:
            print(f"[Discord] ❌ Send error: {e}")
            return False

    async def send_file(self, file_path: str, comment: str = "") -> bool:
        """Send a file via Discord"""
        try:
            url = f"{self.base_url}/channels/{self.channel_id}/messages"
            headers = {"Authorization": f"Bot {self.bot_token}"}

            with open(file_path, "rb") as f:
                data = aiohttp.FormData()
                data.add_field("payload_json", json.dumps({"content": comment}))
                data.add_field("file[0]", f, filename=file_path.split("/")[-1])

                async with aiohttp.ClientSession() as session:
                    async with session.post(url, headers=headers, data=data) as response:
                        return response.status in {200, 201}

        except Exception as e:
            print(f"[Discord] ❌ File send error: {e}")
            return False

    async def close(self):
        """Close the session"""
        if self.session:
            await self.session.close()


class CrossDeviceHandover:
    """Manages cross-device communication"""

    def __init__(self):
        self.config = get_config()

        # Telegram
        telegram_config = self.config.get("cross_device.telegram", {})
        self.telegram_enabled = telegram_config.get("enabled", False)
        self.telegram_bot: Optional[TelegramBot] = None
        if self.telegram_enabled:
            bot_token = telegram_config.get("bot_token", "")
            chat_id = telegram_config.get("chat_id", "")
            if bot_token and chat_id:
                self.telegram_bot = TelegramBot(bot_token, chat_id)
                print("[CrossDevice] ✅ Telegram enabled")

        # Discord
        discord_config = self.config.get("cross_device.discord", {})
        self.discord_enabled = discord_config.get("enabled", False)
        self.discord_bot: Optional[DiscordBot] = None
        if self.discord_enabled:
            bot_token = discord_config.get("bot_token", "")
            channel_id = discord_config.get("channel_id", "")
            if bot_token and channel_id:
                self.discord_bot = DiscordBot(bot_token, channel_id)
                print("[CrossDevice] ✅ Discord enabled")

    async def send_summary(self, summary: str, platform: str = "both") -> bool:
        """Send a summary to configured platforms"""
        success = False

        if platform in ["both", "telegram"] and self.telegram_enabled and self.telegram_bot:
            telegram_success = await self.telegram_bot.send_message(
                f"📋 *M.I.C.A Summary*\n\n{summary}"
            )
            success = success or telegram_success

        if platform in ["both", "discord"] and self.discord_enabled and self.discord_bot:
            discord_success = await self.discord_bot.send_message(f"📋 M.I.C.A Summary\n\n{summary}")
            success = success or discord_success

        return success

    async def send_reminder(self, reminder: str, platform: str = "both") -> bool:
        """Send a reminder to configured platforms"""
        success = False

        if platform in ["both", "telegram"] and self.telegram_enabled and self.telegram_bot:
            telegram_success = await self.telegram_bot.send_message(f"⏰ *Reminder*\n\n{reminder}")
            success = success or telegram_success

        if platform in ["both", "discord"] and self.discord_enabled and self.discord_bot:
            discord_success = await self.discord_bot.send_message(f"⏰ Reminder\n\n{reminder}")
            success = success or discord_success

        return success

    async def send_task_completion(self, task: str, result: str, platform: str = "both") -> bool:
        """Send task completion notification"""
        message = f"✅ *Task Completed*\n\n**Task:** {task}\n\n**Result:** {result}"
        success = False

        if platform in ["both", "telegram"] and self.telegram_enabled and self.telegram_bot:
            telegram_success = await self.telegram_bot.send_message(message)
            success = success or telegram_success

        if platform in ["both", "discord"] and self.discord_enabled and self.discord_bot:
            discord_success = await self.discord_bot.send_message(
                f"✅ Task Completed\n\nTask: {task}\n\nResult: {result}"
            )
            success = success or discord_success

        return success

    async def send_file(self, file_path: str, caption: str = "", platform: str = "both") -> bool:
        """Send a file to configured platforms"""
        success = False

        if platform in ["both", "telegram"] and self.telegram_enabled and self.telegram_bot:
            telegram_success = await self.telegram_bot.send_file(file_path, caption)
            success = success or telegram_success

        if platform in ["both", "discord"] and self.discord_enabled and self.discord_bot:
            discord_success = await self.discord_bot.send_file(file_path, caption)
            success = success or discord_success

        return success

    def sync_send_summary(self, summary: str, platform: str = "both") -> bool:
        """Synchronous wrapper for send_summary"""
        if not AIOHTTP_AVAILABLE:
            print("[CrossDevice] ⚠️ aiohttp not available")
            return False

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(self.send_summary(summary, platform))
            return result
        finally:
            loop.close()

    def sync_send_reminder(self, reminder: str, platform: str = "both") -> bool:
        """Synchronous wrapper for send_reminder"""
        if not AIOHTTP_AVAILABLE:
            print("[CrossDevice] ⚠️ aiohttp not available")
            return False

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(self.send_reminder(reminder, platform))
            return result
        finally:
            loop.close()

    def sync_send_task_completion(self, task: str, result: str, platform: str = "both") -> bool:
        """Synchronous wrapper for send_task_completion"""
        if not AIOHTTP_AVAILABLE:
            print("[CrossDevice] ⚠️ aiohttp not available")
            return False

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(self.send_task_completion(task, result, platform))
        finally:
            loop.close()

    def sync_send_file(self, file_path: str, caption: str = "", platform: str = "both") -> bool:
        """Synchronous wrapper for send_file"""
        if not AIOHTTP_AVAILABLE:
            print("[CrossDevice] ⚠️ aiohttp not available")
            return False

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(self.send_file(file_path, caption, platform))
        finally:
            loop.close()

    def sync_get_telegram_updates(self, offset: int = 0, timeout: int = 0) -> list[dict]:
        """Synchronous update fetch used by the UI bridge and background poller."""
        if not AIOHTTP_AVAILABLE or not self.telegram_bot:
            return []
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(self.telegram_bot.get_updates(offset, timeout))
        finally:
            loop.close()

    def sync_answer_telegram_callback(self, callback_query_id: str, text: str = "") -> bool:
        if not AIOHTTP_AVAILABLE or not self.telegram_bot:
            return False
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(self.telegram_bot.answer_callback(callback_query_id, text))
        finally:
            loop.close()

    def sync_download_telegram_file(self, file_id: str, destination: str | Path) -> str:
        if not AIOHTTP_AVAILABLE or not self.telegram_bot:
            return ""
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(self.telegram_bot.download_file(file_id, destination))
        finally:
            loop.close()

    async def close(self):
        """Close all connections"""
        if self.telegram_bot:
            await self.telegram_bot.close()
        if self.discord_bot:
            await self.discord_bot.close()


# Global instance
_cross_device: Optional[CrossDeviceHandover] = None


def get_cross_device() -> CrossDeviceHandover:
    """Get the global cross-device handover instance"""
    global _cross_device
    if _cross_device is None:
        _cross_device = CrossDeviceHandover()
    return _cross_device


def reset_cross_device() -> None:
    """Reload channel configuration on the next gateway access."""
    global _cross_device
    _cross_device = None


__all__ = [
    "CrossDevice",
    "CrossDeviceHandover",
    "DiscordBot",
    "TelegramBot",
    "get_cross_device",
    "reset_cross_device",
]
