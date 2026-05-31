import unittest
from core.permission_profiles import check_action, PermissionLevel

class SafetyPermissionTests(unittest.TestCase):
    
    def test_admin_profile_allows_everything(self):
        # Admin profile should allow everything and never require confirmation
        is_allowed, msg = check_action("admin", "delete", {"path": "desktop", "name": "important.txt"})
        self.assertTrue(is_allowed)
        self.assertEqual(msg, "Allowed")
        
        is_allowed, msg = check_action("admin", "shutdown")
        self.assertTrue(is_allowed)
        
        is_allowed, msg = check_action("admin", "write", {"content": "hello"})
        self.assertTrue(is_allowed)

    def test_safe_profile_blocks_destructive_and_modification_actions(self):
        # Safe profile should block dangerous actions
        is_allowed, msg = check_action("safe", "delete", {"path": "desktop", "name": "important.txt"})
        self.assertFalse(is_allowed)
        self.assertIn("blocked", msg)
        
        is_allowed, msg = check_action("safe", "shutdown")
        self.assertFalse(is_allowed)
        
        # Safe profile should block file modifications
        is_allowed, msg = check_action("safe", "create_file", {"name": "test.py"})
        self.assertFalse(is_allowed)
        self.assertIn("blocked", msg)
        
        # Safe profile should allow read actions
        is_allowed, msg = check_action("safe", "read", {"name": "test.txt"})
        self.assertTrue(is_allowed)
        
        is_allowed, msg = check_action("safe", "list")
        self.assertTrue(is_allowed)

    def test_normal_profile_requires_confirmation_for_destructive_actions(self):
        # Normal profile should block dangerous actions if not confirmed
        is_allowed, msg = check_action("normal", "delete")
        self.assertFalse(is_allowed)
        self.assertIn("Confirmation required", msg)
        
        # Normal profile should allow dangerous actions if confirmed
        is_allowed, msg = check_action("normal", "delete", {"confirmed": "yes"})
        self.assertTrue(is_allowed)
        self.assertEqual(msg, "Allowed")
        
        is_allowed, msg = check_action("normal", "shutdown", {"confirmed": "confirm"})
        self.assertTrue(is_allowed)
        
        # Normal profile should allow non-destructive actions without confirmation
        is_allowed, msg = check_action("normal", "create_file")
        self.assertTrue(is_allowed)
        self.assertEqual(msg, "Allowed")

if __name__ == "__main__":
    unittest.main()
