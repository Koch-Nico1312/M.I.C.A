import unittest
import json
import os
from pathlib import Path
from core.mcp_client import get_mcp_client, MCP_CONFIG_FILE

class MCPClientTests(unittest.TestCase):
    
    def setUp(self):
        # Save original config if exists
        self.config_existed = MCP_CONFIG_FILE.exists()
        if self.config_existed:
            self.original_config = MCP_CONFIG_FILE.read_text(encoding="utf-8")
        else:
            self.original_config = None

    def tearDown(self):
        # Restore original config
        if self.config_existed and self.original_config:
            MCP_CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
            MCP_CONFIG_FILE.write_text(self.original_config, encoding="utf-8")
        elif MCP_CONFIG_FILE.exists():
            try:
                os.remove(MCP_CONFIG_FILE)
            except Exception:
                pass

    def test_config_loading_and_creation(self):
        # Remove config file to test creation
        if MCP_CONFIG_FILE.exists():
            os.remove(MCP_CONFIG_FILE)
            
        client = get_mcp_client()
        client._load_config()
        
        # Should have created the default config file
        self.assertTrue(Path(MCP_CONFIG_FILE).exists())
        
        # Default config has 'fetch' server
        self.assertIn("fetch", client.servers)
        self.assertEqual(client.servers["fetch"].name, "Fetch MCP Server")
        self.assertEqual(client.servers["fetch"].transport, "http")
        self.assertFalse(client.servers["fetch"].enabled)

    def test_add_and_remove_server(self):
        client = get_mcp_client()
        server_config = {
            "name": "Test Server",
            "transport": "http",
            "url": "http://localhost:9999",
            "enabled": True
        }
        
        # Add server
        success = client.add_server("test_srv", "Test Server", server_config)
        self.assertTrue(success)
        self.assertIn("test_srv", client.servers)
        self.assertEqual(client.servers["test_srv"].name, "Test Server")
        
        # Verify it is written to the config file
        with open(MCP_CONFIG_FILE, "r", encoding="utf-8") as f:
            cfg = json.load(f)
            self.assertIn("test_srv", cfg.get("servers", {}))
            
        # Remove server
        success = client.remove_server("test_srv")
        self.assertTrue(success)
        self.assertNotIn("test_srv", client.servers)

if __name__ == "__main__":
    unittest.main()
