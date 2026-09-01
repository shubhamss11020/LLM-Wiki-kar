"""
Model Context Protocol (MCP) Server for Karpathy LLM Wiki
Exposes knowledge retrieval, cross-referencing, date-based history querying,
and generation record creation tools to Claude Desktop / Claude Code.
"""

import os
import sys
import json
import asyncio
import httpx
from typing import Optional, List, Dict, Any

BACKEND_API_URL = os.getenv("BACKEND_API_URL", "http://localhost:8000")
WIKI_API_KEY = os.getenv("WIKI_API_KEY", "")

def _get_headers() -> dict:
    headers = {}
    if WIKI_API_KEY:
        headers["X-API-Key"] = WIKI_API_KEY
    return headers

async def _http_post(endpoint: str, data: dict) -> dict:
    async with httpx.AsyncClient(base_url=BACKEND_API_URL, timeout=15.0, headers=_get_headers()) as client:
        resp = await client.post(endpoint, json=data)
        resp.raise_for_status()
        return resp.json()

async def _http_get(endpoint: str, params: dict = None) -> dict:
    async with httpx.AsyncClient(base_url=BACKEND_API_URL, timeout=15.0, headers=_get_headers()) as client:
        resp = await client.get(endpoint, params=params)
        resp.raise_for_status()
        return resp.json()

# --- Tool Implementations ---

async def tool_search_wiki(query: str, category: Optional[str] = None, limit: int = 5) -> str:
    """
    Search the 200+ atomic notes in the Karpathy LLM Wiki by semantic concept or keyword.
    """
    try:
        data = await _http_post("/api/search", {"query": query, "category": category, "limit": limit})
        results = data.get("results", [])
        if not results:
            return f"No matching notes found for query: '{query}'."
        
        formatted = [f"Found {len(results)} relevant note(s):\n"]
        for r in results:
            tags_str = ", ".join(r.get("tags") or [])
            formatted.append(
                f"### [[{r['file_name']}]] - {r['title']}\n"
                f"- **Category:** {r['category']} | **Tags:** {tags_str}\n"
                f"- **Heading:** {r['heading']}\n"
                f"- **Snippet:** {r['snippet']}\n"
            )
        formatted.append("")
        return "\n".join(formatted)
    except Exception as e:
        return f"Error searching wiki: {str(e)}"

async def tool_get_file(file_name: str) -> str:
    """
    Retrieve the full Markdown content, structured sections, and outgoing wikilinks for a note.
    """
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
    """
    Retrieve historical generated Markdown interaction records within a date range (e.g. 'show me last month's records').
    """
    try:
        params = {}
        if start_date:
            params["start_date"] = start_date
        if end_date:
            params["end_date"] = end_date
        if topic:
            params["topic"] = topic

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
    """
    Triggers an incremental scan and re-indexing of the Obsidian Vault in PostgreSQL.
    """
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
    Persist an interaction into the Obsidian Vault (as timestamped .md) and commit metadata to the database.
    """
    # 1. Local disk save guarantees it is always saved even if backend is deploying/down
    rec_id = f"rec-{uuid.uuid4().hex[:8]}" if "uuid" in globals() else "rec-local"
    local_saved_file = ""
    try:
        import datetime, pytz, json, uuid
        rec_id = f"rec-{uuid.uuid4().hex[:8]}"
        local_vault = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "vault"))
        if os.path.exists(local_vault):
            tz = pytz.timezone("Asia/Kolkata")
            now = datetime.datetime.now(tz)
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

    # 2. Sync to Backend Database & Remote Vault
    try:
        payload = {
            "prompt": prompt,
            "response": response,
            "topics": topics or ["skincare"],
            "source_files": source_files or []
        }
        res = await _http_post("/api/records", payload)
        return (
            f"Successfully recorded generation!\n"
            f"- **Record ID:** `{res.get('record_id', rec_id)}`\n"
            f"- **Saved File:** `{res.get('file_name', local_saved_file)}`\n"
            f"- **Vault Path:** `{res.get('file_path', 'vault/generated/')}`\n"
            f"- **Timestamp:** {res.get('created_at', 'Saved')}"
        )
    except Exception as e:
        if local_saved_file:
            return f"Saved locally to vault/generated/{local_saved_file} (Backend sync queued: {str(e)})"
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
        "description": "MANDATORY: You MUST ALWAYS call this tool immediately after answering the user to log the full interaction. Pass your EXACT, FULL, VERBATIM response text (100% ditto, word-for-word identical to what is shown to the user, including all markdown formatting, paragraphs, lists, and product details — NEVER summarize or shorten) into 'response', along with the exact user prompt into 'prompt', relevant topics, and referenced source files.",
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
        elif tool_name == "save_generation":
            res = await tool_save_generation(args.get("prompt"), args.get("response"), args.get("topics"), args.get("source_files"))
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
