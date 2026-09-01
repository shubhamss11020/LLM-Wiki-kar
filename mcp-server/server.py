"""
Fast, Resilient Multi-Tier Knowledge Wiki MCP Server for Claude Desktop
Connects directly to the PostgreSQL Knowledge Base API.
"""

import os
import sys
import json
import asyncio
import httpx
import re
from typing import Optional, List, Dict, Any

BACKEND_API_URL = os.getenv("BACKEND_API_URL", "https://llm-wiki-kar.onrender.com")
WIKI_API_KEY = os.getenv("WIKI_API_KEY", "")
THREAD_USER = os.getenv("THREAD_USER", "shubh")

def _get_headers() -> dict:
    headers = {}
    if WIKI_API_KEY:
        headers["X-API-Key"] = WIKI_API_KEY
    return headers

async def _http_get(endpoint: str, params: dict = None) -> dict:
    async with httpx.AsyncClient(base_url=BACKEND_API_URL, timeout=30.0, headers=_get_headers()) as client:
        resp = await client.get(endpoint, params=params)
        resp.raise_for_status()
        return resp.json()

async def _http_post(endpoint: str, data: dict) -> dict:
    async with httpx.AsyncClient(base_url=BACKEND_API_URL, timeout=30.0, headers=_get_headers()) as client:
        resp = await client.post(endpoint, json=data)
        resp.raise_for_status()
        return resp.json()

def _slugify(text: str, max_len: int = 50) -> str:
    slug = re.sub(r"[^\w\s-]", "", text.lower().strip())
    slug = re.sub(r"[\s_]+", "-", slug)
    return slug[:max_len].rstrip("-") or "conversation"

def _git_commit_file(file_path: str, message: str) -> None:
    """Auto-stages and commits the thread file into the Git repository in real time."""
    try:
        import subprocess
        repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        if os.path.exists(os.path.join(repo_root, ".git")):
            rel_path = os.path.relpath(file_path, repo_root)
            subprocess.run(["git", "add", rel_path], cwd=repo_root, capture_output=True, text=True, check=False)
            subprocess.run(["git", "commit", "-m", message], cwd=repo_root, capture_output=True, text=True, check=False)
    except Exception:
        pass

def _save_local_thread_md(local_vault: str, user: str, title: str, prompt: str, response: str) -> str:
    """Creates or appends to vault/threads/<user>_<thread_name>_<date>.md and auto-commits to Git."""
    try:
        import datetime, pytz
        tz = pytz.timezone("Asia/Kolkata")
        now = datetime.datetime.now(tz)
        date_str = now.strftime("%Y-%m-%d")
        time_str = now.strftime("%H:%M:%S")
        slug = _slugify(title)
        
        threads_dir = os.path.join(local_vault, "threads")
        os.makedirs(threads_dir, exist_ok=True)
        file_name = f"{user}_{slug}_{date_str}.md"
        file_path = os.path.join(threads_dir, file_name)

        if os.path.exists(file_path):
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            # Find turn count
            m = re.search(r'turn_count:\s*(\d+)', content)
            current_turns = int(m.group(1)) if m else 1
            new_turns = current_turns + 1

            content = re.sub(r'turn_count:\s*\d+', f'turn_count: {new_turns}', content)
            content = re.sub(r'last_updated:\s*"[^"]*"', f'last_updated: "{now.isoformat()}"', content)

            new_turn_md = (
                f"\n---\n\n"
                f"## Turn {new_turns} — {time_str}\n\n"
                f"**User:**\n{prompt}\n\n"
                f"**AI Response:**\n{response}\n"
            )
            content += new_turn_md

            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)

            _git_commit_file(file_path, f"thread: update {slug} (turn {new_turns})")
        else:
            thread_id = f"thr-{uuid.uuid4().hex[:8]}" if "uuid" in globals() else "thr-local"
            content = f"""---
thread_id: "{thread_id}"
user: "{user}"
title: "{title}"
created: "{now.isoformat()}"
last_updated: "{now.isoformat()}"
turn_count: 1
---

# {user} — {title} — {date_str}

---

## Turn 1 — {time_str}

**User:**
{prompt}

**AI Response:**
{response}
"""
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)

            _git_commit_file(file_path, f"thread: create {slug} (turn 1)")

        return file_path
    except Exception:
        return ""

# --- MCP Tool Handlers ---

async def tool_search_wiki(query: str, category: Optional[str] = None, limit: int = 5) -> str:
    try:
        data = await _http_post("/api/search", {
            "query": query,
            "category": category,
            "limit": limit
        })
        results = data.get("results", [])
        if not results:
            return f"No matching notes found for query: '{query}'."
        
        formatted = [f"Found {len(results)} relevant note(s) in knowledge base:\n"]
        for r in results:
            tags_str = ", ".join(r.get("tags") or [])
            formatted.append(
                f"### [[{r['file_name']}]] - {r['title']}\n"
                f"- **Category:** {r['category']} | **Tags:** {tags_str}\n"
                f"- **Heading:** {r['heading']}\n"
                f"- **Snippet:** {r['snippet']}\n"
            )
        return "\n".join(formatted)
    except Exception as e:
        return f"Error querying wiki: {str(e)}"

async def tool_get_file(file_name: str) -> str:
    try:
        clean_name = file_name.strip("[]'\"")
        data = await _http_get(f"/api/notes/{clean_name}")
        chunks = data.get("chunks", [])
        body = "\n\n".join([f"### {c['heading']}\n{c['content']}" for c in chunks])
        links = ", ".join(data.get("outgoing_wikilinks", [])) or "None"
        return (
            f"# {data.get('title')} ({data.get('file_name')})\n"
            f"- **Category:** {data.get('category')}\n"
            f"- **Tags:** {', '.join(data.get('tags') or [])}\n"
            f"- **Outgoing Wikilinks:** {links}\n\n"
            f"## Content\n{body}"
        )
    except Exception as e:
        return f"Error retrieving note '{file_name}': {str(e)}"

async def tool_get_records_by_date(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    topic: Optional[str] = None
) -> str:
    try:
        params = {}
        if start_date: params["start_date"] = start_date
        if end_date: params["end_date"] = end_date
        if topic: params["topic"] = topic
        
        data = await _http_get("/api/records", params=params)
        records = data.get("records", [])
        if not records:
            return f"No generation records found for interval start='{start_date}', end='{end_date}'."
        
        formatted = [f"Found {len(records)} generation record(s):\n"]
        for rec in records:
            formatted.append(
                f"- **ID:** `{rec['record_id']}` | **Date:** {rec['created_at']} ({rec['timezone']})\n"
                f"  - **Topics:** {', '.join(rec.get('topics') or [])}\n"
                f"  - **Prompt:** {rec['prompt_preview']}\n"
                f"  - **File:** `{rec['file_path']}`\n"
            )
        return "\n".join(formatted)
    except Exception as e:
        return f"Error querying records: {str(e)}"

async def tool_refresh_vault() -> str:
    try:
        res = await _http_post("/api/ingest", {})
        return (
            f"Vault sync complete!\n"
            f"- Total Scanned: {res.get('total_scanned')}\n"
            f"- Newly Indexed / Updated: {res.get('indexed')}\n"
            f"- Unchanged (Skipped): {res.get('skipped')}\n"
            f"- Deleted: {res.get('deleted')}"
        )
    except Exception as e:
        return f"Error refreshing vault: {str(e)}"

async def tool_save_generation(
    prompt: str,
    response: str,
    topics: Optional[List[str]] = None,
    source_files: Optional[List[str]] = None
) -> str:
    """
    Persist an interaction into vault/threads/ (as <user>_<title>_<date>.md),
    vault/generated/ (timestamped note), and PostgreSQL database.
    """
    import datetime, pytz, json, uuid
    rec_id = f"rec-{uuid.uuid4().hex[:8]}"
    local_saved_file = ""
    local_thread_file = ""
    thread_title = (topics[0].replace("-", " ").title()) if (topics and topics[0] != "skincare") else prompt[:60].strip()

    try:
        local_vault = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "vault"))
        if os.path.exists(local_vault):
            tz = pytz.timezone("Asia/Kolkata")
            now = datetime.datetime.now(tz)

            # 1. Save or append to vault/threads/
            local_thread_file = _save_local_thread_md(local_vault, THREAD_USER, thread_title, prompt, response)

            # 2. Save individual note in vault/generated/
            date_dir = os.path.join(local_vault, "generated", str(now.year), f"{now.month:02d}", f"{now.day:02d}")
            os.makedirs(date_dir, exist_ok=True)
            topic_slug = ((topics[0] if topics else "skincare")).replace(" ", "-").lower()
            local_file_name = f"{now.strftime('%Y%m%dT%H%M%S%z')}_{topic_slug}_{rec_id}.md"
            full_local_path = os.path.join(date_dir, local_file_name)
            
            sources_str = "\n".join([f"- [[{s}]]" for s in (source_files or [])]) or "- None"
            md_content = f"""---
id: {rec_id}
created: {now.isoformat()}
topics: {json.dumps(topics or ['skincare'])}
sources: {json.dumps(source_files or [])}
---

# Generation Record: {now.strftime('%Y-%m-%d %H:%M:%S')}

## Prompt
{prompt}

## Referenced Sources
{sources_str}

## Generated Response
{response}
"""
            with open(full_local_path, "w", encoding="utf-8") as f:
                f.write(md_content)
            local_saved_file = local_file_name
    except Exception:
        pass

    # 3. Sync to PostgreSQL Database via Backend
    try:
        payload = {
            "prompt": prompt,
            "response": response,
            "topics": topics or ["skincare"],
            "source_files": source_files or []
        }
        res = await _http_post("/api/records", payload)
        return (
            f"Successfully recorded generation and thread turn!\n"
            f"- **Record ID:** `{res.get('record_id', rec_id)}`\n"
            f"- **Vault Thread:** `{local_thread_file or 'vault/threads/'}`\n"
            f"- **PostgreSQL Sync:** Saved & Indexed"
        )
    except Exception as e:
        if local_saved_file:
            return f"Saved locally to vault/threads/ and vault/generated/ (Backend sync queued: {str(e)})"
        return f"Error saving generation record: {str(e)}"


# --- Robust Windows & Cross-Platform Stdio JSON-RPC MCP Server ---
TOOLS_LIST = [
    {
        "name": "search_wiki",
        "description": "Search the official SUGAR Cosmetics knowledge base wiki (covering SUGAR products, clinical skincare actives, ingredients, beauty formulations, routines, shade matching, comparisons, and guides) by concept or keyword. ALWAYS call this tool first when the user asks for recommendations, best products, active ingredients, or refers to 'your brand / label' to retrieve facts and official catalog details from the wiki.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query or concept (e.g. 'SUGAR oily skin products', 'Vitamin C layering', 'Niacinamide in humidity')"},
                "category": {"type": "string", "description": "Optional category filter e.g. 'Actives', 'Formulations', 'Guides', 'Comparisons', 'Sources'"},
                "limit": {"type": "integer", "description": "Number of results to return"}
            },
            "required": ["query"]
        }
    },
    {
        "name": "get_file",
        "description": "Retrieve full Markdown content, headings, and backlinks for any note in the wiki vault (e.g. 'Vitamin C.md', 'Niacinamide.md', 'Vitamin C vs Niacinamide.md', 'Kojic Acid.md').",
        "inputSchema": {
            "type": "object",
            "properties": {
                "file_name": {"type": "string", "description": "Name of the file e.g. 'Vitamin C.md' or 'Vitamin C vs Niacinamide.md'"}
            },
            "required": ["file_name"]
        }
    },
    {
        "name": "get_records_by_date",
        "description": "Retrieve historical generated interaction logs within a date range (e.g. 'show me recent records')",
        "inputSchema": {
            "type": "object",
            "properties": {
                "start_date": {"type": "string", "description": "ISO start date e.g. 2026-07-01"},
                "end_date": {"type": "string", "description": "ISO end date e.g. 2026-08-01"},
                "topic": {"type": "string", "description": "Optional topic filter e.g. 'skincare'"}
            }
        }
    },
    {
        "name": "refresh_vault",
        "description": "Trigger an incremental scan and re-indexing of the Obsidian Vault in the database.",
        "inputSchema": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "save_generation",
        "description": "MANDATORY: You MUST ALWAYS call this tool immediately after answering the user to log the full interaction into vault/threads/ and the database. Pass your EXACT, FULL, VERBATIM response text (100% ditto, word-for-word identical to what is shown to the user, including all markdown formatting, paragraphs, lists, and product details — NEVER summarize or shorten) into 'response', along with the exact user prompt into 'prompt', relevant topics, and referenced source files.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "prompt": {
                    "type": "string",
                    "description": "The exact user prompt/question verbatim as asked by the user."
                },
                "response": {
                    "type": "string",
                    "description": "CRITICAL: The EXACT, FULL, COMPLETE, VERBATIM response text generated for the user. It MUST be 100% ditto, word-for-word identical to what was shown to the user, including all markdown formatting, paragraphs, lists, and explanations. NEVER summarize, condense, shorten, or paraphrase your answer."
                },
                "topics": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of topic tags e.g. ['skincare', 'layering']"
                },
                "source_files": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of referenced note file names without path e.g. ['Vitamin C vs Niacinamide', 'Vitamin C']"
                }
            },
            "required": ["prompt", "response"]
        }
    },
    {
        "name": "save_chat_transcript",
        "description": "Save complete chat interaction into vault/threads/, raw/claude-chat-queries/, and the database.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "prompt": {"type": "string", "description": "The user prompt."},
                "response": {"type": "string", "description": "The verbatim AI response."},
                "transcript": {"type": "string", "description": "Optional full transcript string."},
                "title": {"type": "string", "description": "Optional thread title."},
                "topics": {"type": "array", "items": {"type": "string"}, "description": "Topic tags."},
                "source_files": {"type": "array", "items": {"type": "string"}, "description": "Referenced files."}
            }
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
                "serverInfo": {"name": "knowledge-wiki-mcp", "version": "1.0.0"}
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
        if tool_name == "search_wiki":
            res = await tool_search_wiki(args.get("query", ""), args.get("category"), args.get("limit", 5))
        elif tool_name == "get_file":
            res = await tool_get_file(args.get("file_name", ""))
        elif tool_name == "get_records_by_date":
            res = await tool_get_records_by_date(args.get("start_date"), args.get("end_date"), args.get("topic"))
        elif tool_name == "refresh_vault":
            res = await tool_refresh_vault()
        elif tool_name in ["save_generation", "save_chat_transcript"]:
            prompt_val = args.get("prompt") or (args.get("transcript", "").split("\n")[0] if args.get("transcript") else "Chat Query")
            resp_val = args.get("response") or args.get("transcript") or "Response recorded."
            res = await tool_save_generation(prompt_val, resp_val, args.get("topics"), args.get("source_files"))
        else:
            res = f"Unknown tool: {tool_name}"
        return {"jsonrpc": "2.0", "id": req_id, "result": {"content": [{"type": "text", "text": res}]}}
    elif req_id is not None:
        return {"jsonrpc": "2.0", "id": req_id, "result": {}}
    return None

def main():
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
            sys.stderr.write(f"Error handling MCP JSON-RPC: {e}\n")
            sys.stderr.flush()

if __name__ == "__main__":
    main()
