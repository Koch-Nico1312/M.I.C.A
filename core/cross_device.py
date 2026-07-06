from __future__ import annotations

"""
Cross-Device Handover System
Send summaries/reminders to phone via Telegram or Discord
"""

import asyncio
import json
from datetime import datetime
from typing import Dict, List, Optional

try:
    import aiohttp

    AIOHTTP_AVAILABLE = True
except ImportError:
    AIOHTTP_AVAILABLE = False

from config.config_loader import get_config


class TelegramBot:
    """Telegram bot integration"""

    def __init__(self, bot_token: str, chat_id: str):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.base_url = f"https://api.telegram.org/bot{bot_token}"
        self.session: Optional[aiohttp.ClientSession] = None

    async def send_message(self, text: str, parse_mode: str = "Markdown") -> bool:
        """Send a message via Telegram"""
        if not self.session:
            self.session = aiohttp.ClientSession()

        try:
            url = f"{self.base_url}/sendMessage"
            data = {"chat_id": self.chat_id, "text": text, "parse_mode": parse_mode}

            async with self.session.post(url, json=data) as response:
                result = await response.json()
                return result.get("ok", False)

        except Exception as e:
            print(f"[Telegram] ❌ Send error: {e}")
            return False

    async def send_file(self, file_path: str, caption: str = "") -> bool:
        """Send a file via Telegram"""
        if not self.session:
            self.session = aiohttp.ClientSession()

        try:
            url = f"{self.base_url}/sendDocument"

            with open(file_path, "rb") as f:
                data = aiohttp.FormData()
                data.add_field("chat_id", self.chat_id)
                data.add_field("document", f, filename=file_path.split("/")[-1])
                if caption:
                    data.add_field("caption", caption)

                async with self.session.post(url, data=data) as response:
                    result = await response.json()
                    return result.get("ok", False)

        except Exception as e:
            print(f"[Telegram] ❌ File send error: {e}")
            return False

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
        if not self.session:
            self.session = aiohttp.ClientSession()

        try:
            url = f"{self.base_url}/channels/{self.channel_id}/messages"
            headers = {"Authorization": f"Bot {self.bot_token}", "Content-Type": "application/json"}
            data = {"content": text}

            async with self.session.post(url, headers=headers, json=data) as response:
                return response.status == 200

        except Exception as e:
            print(f"[Discord] ❌ Send error: {e}")
            return False

    async def send_file(self, file_path: str, comment: str = "") -> bool:
        """Send a file via Discord"""
        if not self.session:
            self.session = aiohttp.ClientSession()

        try:
            url = f"{self.base_url}/channels/{self.channel_id}/messages"
            headers = {"Authorization": f"Bot {self.bot_token}"}

            with open(file_path, "rb") as f:
                data = aiohttp.FormData()
                data.add_field("payload_json", json.dumps({"content": comment}))
                data.add_field("file[0]", f, filename=file_path.split("/")[-1])

                async with self.session.post(url, headers=headers, data=data) as response:
                    return response.status == 200

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
