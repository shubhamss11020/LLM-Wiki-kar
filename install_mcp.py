"""
One-Click Automated MCP Installer for Claude Desktop
Works on Windows, macOS, and Linux automatically.
"""

import os
import sys
import json
import platform

def get_claude_config_path() -> str:
    system = platform.system()
    if system == "Windows":
        app_data = os.getenv("APPDATA")
        if not app_data:
            app_data = os.path.expanduser("~\\AppData\\Roaming")
        return os.path.join(app_data, "Claude", "claude_desktop_config.json")
    elif system == "Darwin": # macOS
        return os.path.expanduser("~/Library/Application Support/Claude/claude_desktop_config.json")
    else: # Linux
        return os.path.expanduser("~/.config/Claude/claude_desktop_config.json")

def install():
    config_path = get_claude_config_path()
    os.makedirs(os.path.dirname(config_path), exist_ok=True)

    # Detect current repository server.py absolute path
    repo_root = os.path.abspath(os.path.dirname(__file__))
    server_path = os.path.join(repo_root, "mcp-server", "server.py")

    # Read existing config if present
    current_config = {}
    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                current_config = json.load(f)
        except Exception:
            current_config = {}

    if "mcpServers" not in current_config:
        current_config["mcpServers"] = {}

    # Clean up any legacy server entries
    for old_name in [
        "karpathy-llm-wiki", "knowledge-wiki", 
        "wiki-skincare-science", "wiki-complexion-bases", "wiki-eyes-lips-culture", "wiki-master-all"
    ]:
        current_config["mcpServers"].pop(old_name, None)

    backend_url = "https://llm-wiki-kar.onrender.com"

    # Add 3 Hierarchically Segregated MCP Servers:
    # MCP 1: Full Access (Tiers 1, 2, 3)
    current_config["mcpServers"]["mcp-1-all-tiers"] = {
        "command": sys.executable or "python",
        "args": [server_path],
        "env": {
            "BACKEND_API_URL": backend_url,
            "WIKI_API_KEY": "mcp1-all-tiers-key"
        }
    }
    # MCP 2: Tiers 2 & 3 only
    current_config["mcpServers"]["mcp-2-tier2-3"] = {
        "command": sys.executable or "python",
        "args": [server_path],
        "env": {
            "BACKEND_API_URL": backend_url,
            "WIKI_API_KEY": "mcp2-tier2-3-key"
        }
    }
    # MCP 3: Tier 3 only
    current_config["mcpServers"]["mcp-3-tier3-only"] = {
        "command": sys.executable or "python",
        "args": [server_path],
        "env": {
            "BACKEND_API_URL": backend_url,
            "WIKI_API_KEY": "mcp3-tier3-only-key"
        }
    }

    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(current_config, f, indent=2)

    print("================================================================")
    print("SUCCESS: Claude Desktop MCP configuration installed successfully!")
    print(f"Config File Updated: {config_path}")
    print(f"Server Script: {server_path}")
    print(f"Live Backend: {backend_url}")
    print("\nConfigured MCP Tiers:")
    print(" - mcp-1-all-tiers: Full Access (Tier 1 + Tier 2 + Tier 3)")
    print(" - mcp-2-tier2-3: Segregated Access (Tier 2 & Tier 3 only)")
    print(" - mcp-3-tier3-only: Restricted Access (Tier 3 only)")
    print("================================================================")
    print("\nNext Step: Open / Restart Claude Desktop to start querying the wiki.")

if __name__ == "__main__":
    install()
