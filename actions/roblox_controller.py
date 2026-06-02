"""
Roblox Controller - AI-powered Roblox gameplay automation
Uses computer vision and AI to play Roblox games autonomously
"""

import json
import threading
import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional


class GameState(Enum):
    """Possible game states"""

    MENU = "menu"
    PLAYING = "playing"
    GAME_OVER = "game_over"
    PAUSED = "paused"
    LOADING = "loading"
    UNKNOWN = "unknown"


class GameType(Enum):
    """Supported Roblox game types"""

    GENERIC = "generic"
    TYCOON = "tycoon"
    OBBY = "obby"
    SIMULATOR = "simulator"
    BATTLE_ROYALE = "battle_royale"
    RACING = "racing"
    SURVIVAL = "survival"
    WAR_TYCOON = "war_tycoon"
    RING_FARM = "ring_farm"


@dataclass
class GameMetrics:
    """Current game metrics"""

    health: int = 100
    score: int = 0
    level: int = 1
    position: tuple = (0, 0)
    coins: int = 0
    time_elapsed: float = 0.0
    enemies_defeated: int = 0
    items_collected: int = 0


class RobloxController:
    """Main Roblox gameplay controller"""

    def __init__(self, speak_callback: Optional[Callable] = None):
        self.speak = speak_callback
        self.is_playing = False
        self.should_stop = threading.Event()
        self.current_state = GameState.UNKNOWN
        self.metrics = GameMetrics()
        self.game_strategy = None
        self.target_goal = None
        self.action_history = []
        self.vision_analyzer = None
        self.game_type = GameType.GENERIC
        self.ml_model = None

    def _log(self, message: str):
        """Log message"""
        print(f"[RobloxController] {message}")
        if self.speak:
            self.speak(message)

    def _initialize_vision(self):
        """Initialize vision system for game state detection"""
        try:
            import cv2
            import numpy as np

            self.vision_analyzer = cv2
            self._log("Vision system initialized")
            return True
        except ImportError:
            self._log("OpenCV not available - using basic controls")
            return False

    def _capture_screen(self):
        """Capture current screen"""
        try:
            import mss
            import numpy as np

            with mss.mss() as sct:
                monitor = sct.monitors[1]  # Primary monitor
                screenshot = sct.grab(monitor)
                img = np.array(screenshot)
                img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
                return img
        except Exception as e:
            self._log(f"Screen capture failed: {e}")
            return None

    def _detect_game_state(self, screen) -> GameState:
        """Detect current game state from screen using advanced vision analysis"""
        if screen is None:
            return GameState.UNKNOWN

        try:
            # Advanced color-based detection with region analysis
            import cv2
            import numpy as np

            # Analyze different screen regions
            height, width = screen.shape[:2]

            # Top region (usually HUD/health bar)
            top_region = screen[0 : height // 4, :]
            # Center region (gameplay)
            center_region = screen[height // 4 : 3 * height // 4, :]
            # Bottom region (controls/inventory)
            bottom_region = screen[3 * height // 4 :, :]

            # Calculate average colors for each region
            top_avg = top_region.mean(axis=(0, 1))
            center_avg = center_region.mean(axis=(0, 1))
            bottom_avg = bottom_region.mean(axis=(0, 1))

            # Menu detection - dark screen with bright text areas
            overall_avg = screen.mean(axis=(0, 1))
            if overall_avg[0] < 40 and overall_avg[1] < 40 and overall_avg[2] < 40:
                # Check for bright UI elements (menus have bright buttons)
                bright_pixels = np.sum(screen > 200)
                if bright_pixels > (width * height * 0.1):  # More than 10% bright pixels
                    return GameState.MENU

            # Game over detection - red/orange tint or specific patterns
            if overall_avg[0] > 140 and overall_avg[1] < 90 and overall_avg[2] < 90:
                return GameState.GAME_OVER

            # Pause detection - typically overlay with semi-transparent dark layer
            if top_avg[0] < 60 and top_avg[1] < 60 and top_avg[2] < 60:
                if center_avg[0] > 80:  # Center still visible (paused game)
                    return GameState.PAUSED

            # Loading detection - spinning icons or progress bars
            # Check for high contrast patterns typical of loading screens
            gray = cv2.cvtColor(screen, cv2.COLOR_BGR2GRAY)
            edges = cv2.Canny(gray, 50, 150)
            edge_density = np.sum(edges > 0) / (width * height)

            if edge_density > 0.15:  # High edge density suggests loading animation
                return GameState.LOADING

            # Default to playing
            return GameState.PLAYING

        except Exception as e:
            self._log(f"Advanced state detection failed: {e}, using basic detection")
            return self._basic_state_detection(screen)

    def _basic_state_detection(self, screen) -> GameState:
        """Fallback basic state detection"""
        if screen is None:
            return GameState.UNKNOWN

        try:
            import numpy as np

            avg_color = screen.mean(axis=(0, 1))

            # Menu detection (dark screen)
            if avg_color[0] < 50 and avg_color[1] < 50 and avg_color[2] < 50:
                return GameState.MENU

            # Game over detection (red/orange tint)
            if avg_color[0] > 150 and avg_color[1] < 100 and avg_color[2] < 100:
                return GameState.GAME_OVER

            return GameState.PLAYING
        except:
            return GameState.UNKNOWN

    def _extract_metrics(self, screen) -> GameMetrics:
        """Extract game metrics from screen using OCR/vision"""
        metrics = GameMetrics()

        if screen is None:
            return metrics

        try:
            # Try EasyOCR first (more accurate for game UI)
            import easyocr

            reader = easyocr.Reader(["en"], gpu=False)

            # Extract text from screen
            results = reader.readtext(screen)

            for bbox, text, confidence in results:
                text = text.strip()
                if confidence < 0.5:
                    continue

                # Parse health values (typically numbers like 100, 50, etc.)
                if text.isdigit() and 0 <= int(text) <= 100:
                    # Could be health, prioritize higher values as health
                    if int(text) > metrics.health:
                        metrics.health = int(text)

                # Parse score values (typically larger numbers)
                elif text.isdigit() and int(text) > 100:
                    metrics.score = int(text)

                # Parse coins
                elif "coin" in text.lower() or "$" in text:
                    numbers = "".join(filter(str.isdigit, text))
                    if numbers:
                        metrics.coins = int(numbers)

                # Parse level
                elif "level" in text.lower() or "lvl" in text.lower():
                    numbers = "".join(filter(str.isdigit, text))
                    if numbers:
                        metrics.level = int(numbers)

            self._log(
                f"OCR extracted - Health: {metrics.health}, Score: {metrics.score}, Coins: {metrics.coins}"
            )

        except ImportError:
            # Fallback to Tesseract
            try:
                import pytesseract
                from PIL import Image

                # Convert OpenCV image to PIL
                pil_image = Image.fromarray(cv2.cvtColor(screen, cv2.COLOR_BGR2RGB))

                # Extract text
                text = pytesseract.image_to_string(pil_image)

                # Parse metrics from text
                for line in text.split("\n"):
                    line = line.strip()
                    if not line:
                        continue

                    # Simple pattern matching
                    if "health" in line.lower():
                        numbers = "".join(filter(str.isdigit, line))
                        if numbers:
                            metrics.health = int(numbers)

                    elif "score" in line.lower():
                        numbers = "".join(filter(str.isdigit, line))
                        if numbers:
                            metrics.score = int(numbers)

                    elif "coin" in line.lower():
                        numbers = "".join(filter(str.isdigit, line))
                        if numbers:
                            metrics.coins = int(numbers)

                self._log(f"Tesseract extracted - Health: {metrics.health}, Score: {metrics.score}")

            except ImportError:
                self._log("OCR not available - using default metrics")

        except Exception as e:
            self._log(f"OCR extraction failed: {e}")

        return metrics

    def _analyze_game_situation(self, screen) -> Dict[str, Any]:
        """Analyze current game situation and recommend actions based on game type"""
        situation = {
            "state": self._detect_game_state(screen),
            "metrics": self._extract_metrics(screen),
            "recommended_actions": [],
        }

        # Game-specific decision making
        if self.game_type == GameType.TYCOON:
            situation["recommended_actions"].extend(self._tycoon_strategy(situation))
        elif self.game_type == GameType.OBBY:
            situation["recommended_actions"].extend(self._obby_strategy(situation))
        elif self.game_type == GameType.SIMULATOR:
            situation["recommended_actions"].extend(self._simulator_strategy(situation))
        elif self.game_type == GameType.BATTLE_ROYALE:
            situation["recommended_actions"].extend(self._battle_royale_strategy(situation))
        elif self.game_type == GameType.RACING:
            situation["recommended_actions"].extend(self._racing_strategy(situation))
        elif self.game_type == GameType.SURVIVAL:
            situation["recommended_actions"].extend(self._survival_strategy(situation))
        elif self.game_type == GameType.WAR_TYCOON:
            situation["recommended_actions"].extend(self._war_tycoon_strategy(situation))
        elif self.game_type == GameType.RING_FARM:
            situation["recommended_actions"].extend(self._ring_farm_strategy(situation))
        else:
            situation["recommended_actions"].extend(self._generic_strategy(situation))

        return situation

    def _generic_strategy(self, situation: Dict[str, Any]) -> List[str]:
        """Generic gameplay strategy"""
        actions = []

        if situation["state"] == GameState.MENU:
            actions.append("press_start")

        elif situation["state"] == GameState.PLAYING:
            if situation["metrics"].health < 30:
                actions.append("seek_healing")
            else:
                actions.append("continue_objective")

        elif situation["state"] == GameState.GAME_OVER:
            actions.append("restart_game")

        return actions

    def _tycoon_strategy(self, situation: Dict[str, Any]) -> List[str]:
        """Tycoon game strategy - focus on building and income"""
        actions = []

        if situation["state"] == GameState.MENU:
            actions.append("press_start")

        elif situation["state"] == GameState.PLAYING:
            # Prioritize income generation
            if situation["metrics"].coins < 100:
                actions.append("collect_income")
                actions.append("buy_basic_upgrade")
            elif situation["metrics"].coins < 500:
                actions.append("buy_mid_upgrade")
                actions.append("expand_building")
            else:
                actions.append("buy_premium_upgrade")
                actions.append("maximize_income")

            # Always collect income
            actions.append("collect_income")

        return actions

    def _obby_strategy(self, situation: Dict[str, Any]) -> List[str]:
        """Obby (obstacle course) strategy - focus on navigation"""
        actions = []

        if situation["state"] == GameState.MENU:
            actions.append("press_start")

        elif situation["state"] == GameState.PLAYING:
            # Navigate obstacles carefully
            if situation["metrics"].health < 50:
                actions.append("proceed_carefully")
                actions.append("time_jumps")
            else:
                actions.append("move_forward")
                actions.append("jump_obstacles")

            # Check for checkpoints
            actions.append("reach_checkpoint")

        return actions

    def _simulator_strategy(self, situation: Dict[str, Any]) -> List[str]:
        """Simulator game strategy - focus on progression and upgrades"""
        actions = []

        if situation["state"] == GameState.MENU:
            actions.append("press_start")

        elif situation["state"] == GameState.PLAYING:
            # Balance grinding and upgrading
            if situation["metrics"].coins < 200:
                actions.append("grind_resources")
                actions.append("complete_basic_tasks")
            else:
                actions.append("purchase_upgrades")
                actions.append("unlock_new_areas")

            # Always look for opportunities
            actions.append("check_events")
            actions.append("collect_free_rewards")

        return actions

    def _battle_royale_strategy(self, situation: Dict[str, Any]) -> List[str]:
        """Battle Royale strategy - focus on survival and combat"""
        actions = []

        if situation["state"] == GameState.MENU:
            actions.append("press_start")

        elif situation["state"] == GameState.PLAYING:
            # Survival priority
            if situation["metrics"].health < 40:
                actions.append("seek_cover")
                actions.append("find_health")
                actions.append("avoid_combat")
            elif situation["metrics"].health < 70:
                actions.append("cautious_engagement")
                actions.append("gather_supplies")
            else:
                actions.append("aggressive_play")
                actions.append("hunt_enemies")

            # Always be aware of zone
            actions.append("check_zone")
            actions.append("position_advantageously")

        return actions

    def _racing_strategy(self, situation: Dict[str, Any]) -> List[str]:
        """Racing game strategy - focus on speed and optimization"""
        actions = []

        if situation["state"] == GameState.MENU:
            actions.append("press_start")

        elif situation["state"] == GameState.PLAYING:
            # Speed optimization
            actions.append("maintain_speed")
            actions.append("use_boosts_wisely")
            actions.append("optimal_racing_line")

            # Avoid obstacles
            actions.append("dodge_obstacles")
            actions.append("drift_corners")

        return actions

    def _survival_strategy(self, situation: Dict[str, Any]) -> List[str]:
        """Survival game strategy - focus on resource management"""
        actions = []

        if situation["state"] == GameState.MENU:
            actions.append("press_start")

        elif situation["state"] == GameState.PLAYING:
            # Resource management
            if situation["metrics"].health < 50:
                actions.append("find_food")
                actions.append("find_water")
                actions.append("build_shelter")
            else:
                actions.append("gather_resources")
                actions.append("craft_tools")
                actions.append("expand_base")

            # Always be prepared
            actions.append("monitor_threats")
            actions.append("maintain_inventory")

        return actions

    def _war_tycoon_strategy(self, situation: Dict[str, Any]) -> List[str]:
        """War Tycoon strategy - focus on military upgrades and conquest"""
        actions = []

        if situation["state"] == GameState.MENU:
            actions.append("press_start")

        elif situation["state"] == GameState.PLAYING:
            # Military progression
            if situation["metrics"].coins < 50:
                actions.append("collect_income")
                actions.append("recruit_basic_soldiers")
                actions.append("build_barracks")
            elif situation["metrics"].coins < 200:
                actions.append("upgrade_weapons")
                actions.append("train_troops")
                actions.append("expand_territory")
            elif situation["metrics"].coins < 500:
                actions.append("build_tanks")
                actions.append("research_tech")
                actions.append("fortify_base")
            else:
                actions.append("launch_attacks")
                actions.append("conquer_territories")
                actions.append("dominate_battlefield")

            # Always collect income and maintain military
            actions.append("collect_income")
            actions.append("maintain_army")
            actions.append("check_enemy_activity")

        return actions

    def _ring_farm_strategy(self, situation: Dict[str, Any]) -> List[str]:
        """Build a ring farm strategy - focus on ring production and optimization"""
        actions = []

        if situation["state"] == GameState.MENU:
            actions.append("press_start")

        elif situation["state"] == GameState.PLAYING:
            # Ring production optimization
            if situation["metrics"].coins < 100:
                actions.append("collect_rings")
                actions.append("build_basic_ring_machine")
                actions.append("upgrade_collector")
            elif situation["metrics"].coins < 300:
                actions.append("build_advanced_ring_machine")
                actions.append("optimize_production")
                actions.append("expand_storage")
            elif situation["metrics"].coins < 1000:
                actions.append("automate_collection")
                actions.append("build_ring_factory")
                actions.append("maximize_output")
            else:
                actions.append("build_premium_machines")
                actions.append("unlock_rare_rings")
                actions.append("dominate_market")

            # Always collect rings and optimize
            actions.append("collect_rings")
            actions.append("check_machine_status")
            actions.append("repair_machines")

        return actions

    def _execute_action(self, action: str):
        """Execute a game action"""
        try:
            import pyautogui

            pyautogui.PAUSE = 0.1

            action_map = {
                # Basic controls
                "press_start": lambda: pyautogui.press("enter"),
                "move_forward": lambda: pyautogui.keyDown("w"),
                "move_backward": lambda: pyautogui.keyDown("s"),
                "move_left": lambda: pyautogui.keyDown("a"),
                "move_right": lambda: pyautogui.keyDown("d"),
                "jump": lambda: pyautogui.press("space"),
                "attack": lambda: pyautogui.click(),
                "restart_game": lambda: pyautogui.press("r"),
                "pause": lambda: pyautogui.press("escape"),
                # Tycoon actions
                "collect_income": lambda: pyautogui.press("e"),
                "buy_basic_upgrade": lambda: self._complex_action("buy_basic"),
                "buy_mid_upgrade": lambda: self._complex_action("buy_mid"),
                "buy_premium_upgrade": lambda: self._complex_action("buy_premium"),
                "expand_building": lambda: self._complex_action("expand"),
                "maximize_income": lambda: self._complex_action("max_income"),
                # Obby actions
                "proceed_carefully": lambda: self._complex_action("careful"),
                "time_jumps": lambda: self._complex_action("timed_jump"),
                "jump_obstacles": lambda: pyautogui.press("space"),
                "reach_checkpoint": lambda: self._complex_action("checkpoint"),
                # Simulator actions
                "grind_resources": lambda: self._complex_action("grind"),
                "complete_basic_tasks": lambda: self._complex_action("tasks"),
                "purchase_upgrades": lambda: self._complex_action("upgrades"),
                "unlock_new_areas": lambda: self._complex_action("unlock"),
                "check_events": lambda: self._complex_action("events"),
                "collect_free_rewards": lambda: self._complex_action("rewards"),
                # Battle Royale actions
                "seek_cover": lambda: self._complex_action("cover"),
                "find_health": lambda: self._complex_action("health_item"),
                "avoid_combat": lambda: self._complex_action("avoid"),
                "cautious_engagement": lambda: self._complex_action("cautious"),
                "gather_supplies": lambda: self._complex_action("supplies"),
                "aggressive_play": lambda: self._complex_action("aggressive"),
                "hunt_enemies": lambda: self._complex_action("hunt"),
                "check_zone": lambda: self._complex_action("zone"),
                "position_advantageously": lambda: self._complex_action("position"),
                # Racing actions
                "maintain_speed": lambda: pyautogui.keyDown("w"),
                "use_boosts_wisely": lambda: self._complex_action("boost"),
                "optimal_racing_line": lambda: self._complex_action("racing_line"),
                "dodge_obstacles": lambda: self._complex_action("dodge"),
                "drift_corners": lambda: self._complex_action("drift"),
                # Survival actions
                "find_food": lambda: self._complex_action("food"),
                "find_water": lambda: self._complex_action("water"),
                "build_shelter": lambda: self._complex_action("shelter"),
                "gather_resources": lambda: self._complex_action("gather"),
                "craft_tools": lambda: self._complex_action("craft"),
                "expand_base": lambda: self._complex_action("base"),
                "monitor_threats": lambda: self._complex_action("threats"),
                "maintain_inventory": lambda: self._complex_action("inventory"),
                # War Tycoon actions
                "recruit_basic_soldiers": lambda: self._complex_action("recruit_basic"),
                "build_barracks": lambda: self._complex_action("barracks"),
                "upgrade_weapons": lambda: self._complex_action("weapons"),
                "train_troops": lambda: self._complex_action("train"),
                "expand_territory": lambda: self._complex_action("territory"),
                "build_tanks": lambda: self._complex_action("tanks"),
                "research_tech": lambda: self._complex_action("research"),
                "fortify_base": lambda: self._complex_action("fortify"),
                "launch_attacks": lambda: self._complex_action("attack"),
                "conquer_territories": lambda: self._complex_action("conquer"),
                "dominate_battlefield": lambda: self._complex_action("dominate"),
                "maintain_army": lambda: self._complex_action("army_maintain"),
                "check_enemy_activity": lambda: self._complex_action("enemy_check"),
                # Ring Farm actions
                "collect_rings": lambda: pyautogui.press("e"),
                "build_basic_ring_machine": lambda: self._complex_action("basic_machine"),
                "upgrade_collector": lambda: self._complex_action("collector"),
                "build_advanced_ring_machine": lambda: self._complex_action("advanced_machine"),
                "optimize_production": lambda: self._complex_action("optimize"),
                "expand_storage": lambda: self._complex_action("storage"),
                "automate_collection": lambda: self._complex_action("automate"),
                "build_ring_factory": lambda: self._complex_action("factory"),
                "maximize_output": lambda: self._complex_action("maximize"),
                "build_premium_machines": lambda: self._complex_action("premium"),
                "unlock_rare_rings": lambda: self._complex_action("rare"),
                "dominate_market": lambda: self._complex_action("market"),
                "check_machine_status": lambda: self._complex_action("machine_status"),
                "repair_machines": lambda: self._complex_action("repair"),
                # Generic actions
                "seek_healing": lambda: self._complex_action("heal"),
                "continue_objective": lambda: self._complex_action("objective"),
            }

            if action in action_map:
                action_map[action]()
                self.action_history.append({"action": action, "timestamp": time.time()})
                self._log(f"Executed: {action}")
            else:
                self._log(f"Unknown action: {action}")

        except Exception as e:
            self._log(f"Action execution failed: {e}")

    def _complex_action(self, action_type: str):
        """Execute complex multi-step actions"""
        if action_type == "heal":
            # Navigate to healing location
            import pyautogui

            pyautogui.keyDown("s")
            time.sleep(2)
            pyautogui.keyUp("s")
            pyautogui.press("e")  # Interact key

        elif action_type == "objective":
            # Continue towards objective
            import pyautogui

            pyautogui.keyDown("w")
            time.sleep(1)
            pyautogui.keyUp("w")

    def _check_goal_completion(self) -> bool:
        """Check if the target goal has been achieved"""
        if not self.target_goal:
            return False

        goal_type = self.target_goal.get("type", "")
        target_value = self.target_goal.get("target", 0)

        if goal_type == "score":
            return self.metrics.score >= target_value
        elif goal_type == "level":
            return self.metrics.level >= target_value
        elif goal_type == "coins":
            return self.metrics.coins >= target_value
        elif goal_type == "time":
            return self.metrics.time_elapsed >= target_value

        return False

    def _gameplay_loop(self):
        """Main gameplay loop"""
        self._log("Starting gameplay loop...")

        while not self.should_stop.is_set():
            try:
                # Capture screen
                screen = self._capture_screen()

                # Analyze situation
                situation = self._analyze_game_situation(screen)
                self.current_state = situation["state"]
                self.metrics = situation["metrics"]

                # Check goal completion
                if self._check_goal_completion():
                    self._log("Goal achieved! Stopping gameplay.")
                    break

                # Execute recommended actions
                for action in situation["recommended_actions"]:
                    if self.should_stop.is_set():
                        break
                    self._execute_action(action)
                    time.sleep(0.5)  # Small delay between actions

                # Update time
                self.metrics.time_elapsed += 0.5

                # Small delay to prevent CPU overload
                time.sleep(0.5)

            except Exception as e:
                self._log(f"Gameplay loop error: {e}")
                time.sleep(1)

        self.is_playing = False
        self._log("Gameplay stopped")

    def start_playing(
        self, strategy: str = "balanced", goal: Optional[Dict] = None, game_type: str = "generic"
    ):
        """Start autonomous gameplay

        Args:
            strategy: Gameplay strategy (aggressive, defensive, balanced, farming)
            goal: Target goal to achieve (e.g., {"type": "score", "target": 1000})
            game_type: Type of Roblox game (tycoon, obby, simulator, battle_royale, racing, survival, generic)
        """
        if self.is_playing:
            self._log("Already playing!")
            return False

        # Set game type
        try:
            self.game_type = GameType(game_type.lower())
        except ValueError:
            self._log(f"Unknown game type: {game_type}, using generic")
            self.game_type = GameType.GENERIC

        self.game_strategy = strategy
        self.target_goal = goal
        self.is_playing = True
        self.should_stop.clear()

        # Initialize vision
        self._initialize_vision()

        # Start gameplay in separate thread
        gameplay_thread = threading.Thread(target=self._gameplay_loop, daemon=True)
        gameplay_thread.start()

        goal_desc = f"Goal: {goal}" if goal else "Continuous play"
        self._log(
            f"Started Roblox gameplay - Type: {self.game_type.value}, Strategy: {strategy}, {goal_desc}"
        )

        return True

    def stop_playing(self):
        """Stop autonomous gameplay"""
        self.should_stop.set()
        self._log("Stopping gameplay...")

        # Release any pressed keys
        try:
            import pyautogui

            pyautogui.keyUp("w")
            pyautogui.keyUp("a")
            pyautogui.keyUp("s")
            pyautogui.keyUp("d")
        except:
            pass

    def get_status(self) -> Dict[str, Any]:
        """Get current gameplay status"""
        return {
            "is_playing": self.is_playing,
            "current_state": self.current_state.value,
            "metrics": {
                "health": self.metrics.health,
                "score": self.metrics.score,
                "level": self.metrics.level,
                "coins": self.metrics.coins,
                "time_elapsed": self.metrics.time_elapsed,
            },
            "strategy": self.game_strategy,
            "goal": self.target_goal,
            "actions_taken": len(self.action_history),
        }


def roblox_controller(parameters: dict, player=None, speak: Callable = None) -> str:
    """Main entry point for Roblox control"""

    action = parameters.get("action", "status")
    controller = getattr(roblox_controller, "_controller", None)

    if action == "start":
        if controller is None:
            controller = RobloxController(speak)
            roblox_controller._controller = controller

        strategy = parameters.get("strategy", "balanced")
        goal = parameters.get("goal")
        game_type = parameters.get("game_type", "generic")

        if controller.start_playing(strategy, goal, game_type):
            return f"Started playing Roblox - Type: {game_type}, Strategy: {strategy}"
        else:
            return "Failed to start - already playing"

    elif action == "stop":
        if controller:
            controller.stop_playing()
            return "Stopped Roblox gameplay"
        else:
            return "Not currently playing"

    elif action == "status":
        if controller:
            status = controller.get_status()
            return json.dumps(status, indent=2)
        else:
            return "Not currently playing - no active session"

    elif action == "set_goal":
        if controller:
            goal = parameters.get("goal")
            controller.target_goal = goal
            return f"Goal updated: {goal}"
        else:
            return "No active session - start playing first"

    else:
        return f"Unknown action: {action}"
