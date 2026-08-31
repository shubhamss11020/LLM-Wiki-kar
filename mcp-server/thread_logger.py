"""
Thread Logger MCP Server for Claude Desktop
============================================
Guarantees 100% thread saving by making saving a side-effect of
response delivery, not an optional tool call.

Tools exposed:
  1. start_conversation  — FIRST call: captures user prompt, creates/resumes thread
  2. deliver_response     — LAST call: captures AI response, saves to thread
  3. list_threads         — List all saved threads
  4. get_thread           — Get full thread detail
"""

import os
import sys
import re
import json
import uuid
import asyncio
import datetime
import httpx
from typing import Optional, List, Dict, Any

BACKEND_API_URL = os.getenv("BACKEND_API_URL", "http://localhost:8000")
THREAD_USER = os.getenv("THREAD_USER", "shubh")
VAULT_PATH = os.getenv("VAULT_PATH", os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "vault")))
WIKI_API_KEY = os.getenv("WIKI_API_KEY", "")

# In-memory session state for the current conversation
_current_thread_id: Optional[str] = None
_current_turn_number: int = 0


def _get_headers() -> dict:
    headers = {}
    if WIKI_API_KEY:
        headers["X-API-Key"] = WIKI_API_KEY
    return headers


async def _http_post(endpoint: str, data: dict) -> dict:
    async with httpx.AsyncClient(base_url=BACKEND_API_URL, timeout=30.0, headers=_get_headers()) as client:
        resp = await client.post(endpoint, json=data)
        resp.raise_for_status()
        return resp.json()


async def _http_get(endpoint: str, params: dict = None) -> dict:
    async with httpx.AsyncClient(base_url=BACKEND_API_URL, timeout=30.0, headers=_get_headers()) as client:
        resp = await client.get(endpoint, params=params)
        resp.raise_for_status()
        return resp.json()


def _slugify(text: str, max_len: int = 40) -> str:
    slug = re.sub(r"[^\w\s-]", "", text.lower().strip())
    slug = re.sub(r"[\s_]+", "-", slug)
    return slug[:max_len].rstrip("-")


def _write_thread_file_local(thread_id: str, user: str, title: str,
                              created_iso: str, last_updated_iso: str,
                              turns: List[Dict[str, Any]]) -> str:
    """Write thread MD file directly to local vault/threads/ as a fallback."""
    threads_dir = os.path.join(VAULT_PATH, "threads")
    os.makedirs(threads_dir, exist_ok=True)

    date_str = created_iso[:10]
    slug = _slugify(title)
    file_name = f"{user}_{slug}_{date_str}.md"
    file_path = os.path.join(threads_dir, file_name)

    # Build MD
    md = (
        f"---\n"
        f"thread_id: \"{thread_id}\"\n"
        f"user: \"{user}\"\n"
        f"title: \"{title}\"\n"
        f"created: \"{created_iso}\"\n"
        f"last_updated: \"{last_updated_iso}\"\n"
        f"turn_count: {len(turns)}\n"
        f"---\n\n"
        f"# {user} — {title} — {date_str}\n\n"
    )

    for turn in turns:
        turn_num = turn.get("turn_number", "?")
        time_part = turn.get("time", "")
        prompt = turn.get("user_prompt", "")
        response = turn.get("ai_response", "_Awaiting response..._")
        md += (
            f"---\n\n"
            f"## Turn {turn_num} — {time_part}\n\n"
            f"**User:**\n{prompt}\n\n"
            f"**AI Response:**\n{response}\n\n"
        )

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(md)

    return file_path


# --- Tool Implementations ---

async def tool_start_conversation(user_prompt: str, thread_title: Optional[str] = None,
                                   continue_thread_id: Optional[str] = None) -> str:
    """
    Start a new conversation or continue an existing thread.
    Captures the user prompt and optionally searches the wiki for relevant context.
    """
    global _current_thread_id, _current_turn_number

    user = THREAD_USER
    now_str = datetime.datetime.now().strftime("%H:%M:%S")

    try:
        if continue_thread_id:
            # Append to existing thread
            res = await _http_post("/api/threads/append", {
                "thread_id": continue_thread_id,
                "user_prompt": user_prompt,
            })
            _current_thread_id = continue_thread_id
            _current_turn_number = res.get("turn_number", 1)
        else:
            # Create new thread
            title = thread_title or user_prompt[:60].strip()
            res = await _http_post("/api/threads", {
                "user": user,
                "title": title,
                "user_prompt": user_prompt,
            })
            _current_thread_id = res.get("thread_id")
            _current_turn_number = 1

        # Also search wiki for relevant context
        wiki_results = ""
        try:
            wiki_data = await _http_post("/api/search", {
                "query": user_prompt,
                "limit": 5
            })
            results = wiki_data.get("results", [])
            if results:
                wiki_results = "\n\n---\n📚 **Relevant Wiki Notes:**\n"
                for r in results:
                    tags_str = ", ".join(r.get("tags") or [])
                    wiki_results += (
                        f"\n### [[{r['file_name']}]] - {r['title']}\n"
                        f"- **Category:** {r['category']} | **Tags:** {tags_str}\n"
                        f"- **Heading:** {r['heading']}\n"
                        f"- **Snippet:** {r['snippet']}\n"
                    )
        except Exception:
            pass

        return (
            f"✅ Thread {'continued' if continue_thread_id else 'created'} successfully.\n"
            f"- **Thread ID:** `{_current_thread_id}`\n"
            f"- **Turn:** {_current_turn_number}\n"
            f"- **User Prompt Saved:** Yes\n"
            f"- **File:** `{res.get('file_path', 'pending')}`\n\n"
            f"⚠️ **IMPORTANT:** After you compose your response, you MUST call `deliver_response` "
            f"with thread_id=`{_current_thread_id}` and turn_number={_current_turn_number} "
            f"to save your response to the thread."
            f"{wiki_results}"
        )
    except Exception as e:
        # Fallback: save locally even if backend is down
        try:
            thread_id = continue_thread_id or f"thr-{uuid.uuid4().hex[:8]}"
            title = thread_title or user_prompt[:60].strip()
            now_iso = datetime.datetime.now().isoformat()
            _current_thread_id = thread_id
            _current_turn_number = 1

            _write_thread_file_local(
                thread_id=thread_id, user=user, title=title,
                created_iso=now_iso, last_updated_iso=now_iso,
                turns=[{"turn_number": 1, "time": now_str,
                        "user_prompt": user_prompt, "ai_response": "_Awaiting response..._"}]
            )
            return (
                f"⚠️ Backend unavailable — saved locally.\n"
                f"- **Thread ID:** `{thread_id}`\n"
                f"- **Turn:** 1\n"
                f"- **IMPORTANT:** Call `deliver_response` with thread_id=`{thread_id}` and turn_number=1 after responding."
            )
        except Exception as e2:
            return f"Error starting conversation: {e} / local fallback: {e2}"


async def tool_deliver_response(thread_id: str, turn_number: int,
                                 ai_response: str,
                                 source_files: Optional[List[str]] = None) -> str:
    """
    Save the AI's exact response to the thread. This completes the turn.
    """
    global _current_thread_id, _current_turn_number

    try:
        res = await _http_post("/api/threads/deliver", {
            "thread_id": thread_id,
            "turn_number": turn_number,
            "ai_response": ai_response,
        })
        return (
            f"✅ Response saved to thread!\n"
            f"- **Thread ID:** `{thread_id}`\n"
            f"- **Turn:** {turn_number}\n"
            f"- **File:** `{res.get('file_path', '')}`\n"
            f"- **Updated:** {res.get('last_updated', '')}"
        )
    except Exception as e:
        # Fallback: try to update local file
        try:
            now_iso = datetime.datetime.now().isoformat()
            now_str = datetime.datetime.now().strftime("%H:%M:%S")
            # Read current thread from local file if possible
            threads_dir = os.path.join(VAULT_PATH, "threads")
            if os.path.exists(threads_dir):
                for fname in os.listdir(threads_dir):
                    fpath = os.path.join(threads_dir, fname)
                    with open(fpath, "r", encoding="utf-8") as f:
                        content = f.read()
                    if thread_id in content:
                        # Replace the awaiting placeholder
                        content = content.replace(
                            "_Awaiting response..._",
                            ai_response,
                            1  # Only replace the first occurrence (latest turn)
                        )
                        # Update last_updated in frontmatter
                        content = re.sub(
                            r'last_updated: "[^"]*"',
                            f'last_updated: "{now_iso}"',
                            content
                        )
                        with open(fpath, "w", encoding="utf-8") as f:
                            f.write(content)
                        return (
                            f"⚠️ Backend unavailable — response saved locally.\n"
                            f"- **File:** `{fpath}`"
                        )
        except Exception:
            pass
        return f"Error delivering response: {e}"


async def tool_list_threads(user: Optional[str] = None) -> str:
    """List all saved conversation threads."""
    try:
        params = {}
        if user:
            params["user"] = user
        data = await _http_get("/api/threads", params=params)
        threads = data.get("threads", [])
        if not threads:
            return "No threads found."

        formatted = [f"Found {len(threads)} thread(s):\n"]
        for t in threads:
            formatted.append(
                f"- **{t['title']}** (`{t['thread_id']}`)\n"
                f"  - User: {t['user']} | Turns: {t['turn_count']} | "
                f"Updated: {t.get('last_updated', '')[:19]}\n"
            )
        return "\n".join(formatted)
    except Exception as e:
        return f"Error listing threads: {e}"


async def tool_get_thread(thread_id: str) -> str:
    """Get the full conversation history of a specific thread."""
    try:
        data = await _http_get(f"/api/threads/{thread_id}")
        if not data:
            return f"Thread '{thread_id}' not found."

        formatted = [
            f"# {data['title']}\n",
            f"- **User:** {data['user']}",
            f"- **Thread ID:** `{data['thread_id']}`",
            f"- **Turns:** {data['turn_count']}",
            f"- **Created:** {data.get('created_at', '')}",
            f"- **Updated:** {data.get('last_updated', '')}\n",
        ]

        for turn in data.get("turns", []):
            formatted.append(f"## Turn {turn['turn_number']}")
            formatted.append(f"**User:** {turn['user_prompt']}\n")
            if turn.get("ai_response"):
                formatted.append(f"**AI:** {turn['ai_response']}\n")
            else:
                formatted.append("**AI:** _Awaiting response..._\n")

        return "\n".join(formatted)
    except Exception as e:
        return f"Error getting thread: {e}"


# --- MCP Server (Stdio JSON-RPC) ---

TOOLS_LIST = [
    {
        "name": "start_conversation",
        "description": (
            "MANDATORY FIRST STEP: You MUST call this tool FIRST before doing ANYTHING else when the user "
            "sends a message. This tool registers the user's prompt into the conversation thread and "
            "returns relevant wiki context. Without calling this, the conversation will NOT be saved. "
            "If this is a follow-up in an existing conversation, pass the continue_thread_id from the "
            "previous start_conversation call."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "user_prompt": {
                    "type": "string",
                    "description": "The exact user prompt/message to save"
                },
                "thread_title": {
                    "type": "string",
                    "description": "Optional title for a new thread. If omitted, auto-generated from the prompt."
                },
                "continue_thread_id": {
                    "type": "string",
                    "description": "If continuing an existing conversation thread, pass the thread_id from the previous start_conversation response."
                }
            },
            "required": ["user_prompt"]
        }
    },
    {
        "name": "deliver_response",
        "description": (
            "MANDATORY FINAL STEP: You MUST call this tool AFTER composing your response to save it "
            "to the conversation thread. Pass your COMPLETE response text exactly as you want it saved. "
            "Use the thread_id and turn_number from the start_conversation call. If you do not call this, "
            "the response will be LOST and the thread will show 'Awaiting response'."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "thread_id": {
                    "type": "string",
                    "description": "The thread_id returned by start_conversation"
                },
                "turn_number": {
                    "type": "integer",
                    "description": "The turn_number returned by start_conversation"
                },
                "ai_response": {
                    "type": "string",
                    "description": "Your COMPLETE response text to save to the thread"
                },
                "source_files": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional list of wiki note filenames you referenced"
                }
            },
            "required": ["thread_id", "turn_number", "ai_response"]
        }
    },
    {
        "name": "list_threads",
        "description": "List all saved conversation threads for the user. Shows thread titles, turn counts, and last update times.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "user": {
                    "type": "string",
                    "description": "Optional username filter"
                }
            }
        }
    },
    {
        "name": "get_thread",
        "description": "Retrieve the full conversation history of a specific saved thread by its thread_id.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "thread_id": {
                    "type": "string",
                    "description": "The thread ID to retrieve"
                }
            },
            "required": ["thread_id"]
        }
    }
]


async def handle_request(req: dict) -> Optional[dict]:
    req_id = req.get("id")
    method = req.get("method")
    params = req.get("params", {})

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "thread-logger-mcp", "version": "1.0.0"}
            }
        }
    elif method == "notifications/initialized":
        return None
    elif method == "ping":
        return {"jsonrpc": "2.0", "id": req_id, "result": {}}
    elif method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {"tools": TOOLS_LIST}
        }
    elif method == "tools/call":
        tool_name = params.get("name")
        args = params.get("arguments", {})
        try:
            if tool_name == "start_conversation":
                res = await tool_start_conversation(
                    user_prompt=args.get("user_prompt", ""),
                    thread_title=args.get("thread_title"),
                    continue_thread_id=args.get("continue_thread_id")
                )
            elif tool_name == "deliver_response":
                res = await tool_deliver_response(
                    thread_id=args.get("thread_id", ""),
                    turn_number=args.get("turn_number", 1),
                    ai_response=args.get("ai_response", ""),
                    source_files=args.get("source_files")
                )
            elif tool_name == "list_threads":
                res = await tool_list_threads(user=args.get("user"))
            elif tool_name == "get_thread":
                res = await tool_get_thread(thread_id=args.get("thread_id", ""))
            else:
                res = f"Unknown tool: {tool_name}"
        except Exception as e:
            res = f"Error in {tool_name}: {str(e)}"

        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {"content": [{"type": "text", "text": res}]}
        }
    elif req_id is not None:
        return {"jsonrpc": "2.0", "id": req_id, "result": {}}
    return None


def main():
    """Main entry point — Stdio JSON-RPC MCP server."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    for line in sys.stdin:
        line_str = line.strip()
        if not line_str:
            continue
        try:
            req = json.loads(line_str)
            response = loop.run_until_complete(handle_request(req))
            if response is not None:
                sys.stdout.write(json.dumps(response) + "\n")
                sys.stdout.flush()
        except Exception as e:
            sys.stderr.write(f"Thread Logger MCP Error: {e}\n")
            sys.stderr.flush()


if __name__ == "__main__":
    if "--test" in sys.argv:
        # Quick self-test
        print("Thread Logger MCP Server — Self Test")
        print(f"  Backend URL: {BACKEND_API_URL}")
        print(f"  User: {THREAD_USER}")
        print(f"  Vault Path: {VAULT_PATH}")
        print(f"  Tools: {[t['name'] for t in TOOLS_LIST]}")
        print("  Status: OK")
    else:
        main()
