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

    backend_url = "https://llm-wiki-kar.onrender.com"

    # Add 3 Segregated Partition Servers
    current_config["mcpServers"]["wiki-skincare-science"] = {
        "command": sys.executable or "python",
        "args": [server_path],
        "env": {
            "BACKEND_API_URL": backend_url,
            "WIKI_API_KEY": "partition-1-skincare-key"
        }
    }
    current_config["mcpServers"]["wiki-complexion-bases"] = {
        "command": sys.executable or "python",
        "args": [server_path],
        "env": {
            "BACKEND_API_URL": backend_url,
            "WIKI_API_KEY": "partition-2-complexion-key"
        }
    }
    current_config["mcpServers"]["wiki-eyes-lips-culture"] = {
        "command": sys.executable or "python",
        "args": [server_path],
        "env": {
            "BACKEND_API_URL": backend_url,
            "WIKI_API_KEY": "partition-3-eyeslips-key"
        }
    }

    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(current_config, f, indent=2)

    print("================================================================")
    print("SUCCESS: Claude Desktop MCP configuration installed successfully!")
    print(f"Config File Updated: {config_path}")
    print(f"Server Script: {server_path}")
    print(f"Live Backend: {backend_url}")
    print("================================================================")
    print("\nNext Step: Open / Restart Claude Desktop to start querying the wiki.")

if __name__ == "__main__":
    install()
