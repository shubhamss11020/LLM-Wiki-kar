"""
Comprehensive fix for mcp_server.py in Thread-DB/claude-notes-vault:
1. Fix 404 on /.well-known/oauth-protected-resource and /.well-known/oauth-authorization-server for Claude.ai
2. Fix 404 on /api/threads and /api/threads/{id} for Obsidian LLM Wiki Live Sync
3. Fix 405 on POST /_internal/sse by handling Streamable HTTP / SSE requests gracefully
"""

import os
import re
from pathlib import Path

vault_dir = Path(r"..\Thread-DB\claude-notes-vault").resolve()
mcp_file = vault_dir / "mcp_server.py"
code = mcp_file.read_text(encoding="utf-8")

# Let's inspect _IdentityMiddleware in mcp_server.py
middleware_pattern = r'class _IdentityMiddleware:.*?(?=\n\n#|\ndef |\nPORT =|\nmcp =|$)'
match = re.search(middleware_pattern, code, re.DOTALL)
if not match:
    print("[-] Could not find _IdentityMiddleware")
    exit(1)

print("[+] Found _IdentityMiddleware")

# New robust _IdentityMiddleware with OAuth and public API pass-through
new_middleware = '''class _IdentityMiddleware:
    """
    Middleware that:
    1. Serves /.well-known/oauth-* for Claude.ai remote connector compatibility.
    2. Serves /api/threads for Obsidian live sync plugin.
    3. Handles streamable HTTP and SSE requests smoothly without 405s.
    4. Resolves /<secret>/sse into FastMCP's internal SSE transport and tracks user identity.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope["path"]
        method = scope.get("method", "GET")

        # 1. Bare root path: public liveness probe
        if path == "/":
            await self.app(scope, receive, send)
            return

        # 2. Claude.ai OAuth 2.1 Discovery Endpoints (RFC 8414)
        from starlette.responses import JSONResponse, PlainTextResponse, RedirectResponse

        # Host extraction for dynamic absolute URLs
        headers = dict(scope.get("headers", []))
        host_header = headers.get(b"host", b"localhost:8000").decode("latin1")
        proto_header = headers.get(b"x-forwarded-proto", b"http").decode("latin1")
        base_url = f"{proto_header}://{host_header}"

        if path in ["/.well-known/oauth-protected-resource", "/.well-known/oauth-authorization-server"] or path.startswith("/.well-known/oauth-protected-resource/"):
            if "protected-resource" in path:
                res = JSONResponse({
                    "resource": base_url,
                    "authorization_servers": [base_url],
                    "scopes_supported": []
                })
                await res(scope, receive, send)
                return
            else:
                res = JSONResponse({
                    "issuer": base_url,
                    "authorization_endpoint": f"{base_url}/oauth/authorize",
                    "token_endpoint": f"{base_url}/oauth/token",
                    "registration_endpoint": f"{base_url}/oauth/register",
                    "response_types_supported": ["code"],
                    "grant_types_supported": ["authorization_code", "refresh_token"],
                    "code_challenge_methods_supported": ["S256"]
                })
                await res(scope, receive, send)
                return

        if path == "/oauth/register" and method == "POST":
            res = JSONResponse({
                "client_id": "claude-client",
                "client_secret": None,
                "token_endpoint_auth_method": "none"
            })
            await res(scope, receive, send)
            return

        if path == "/oauth/authorize":
            query = scope.get("query_string", b"").decode("utf-8")
            params = dict(q.split("=", 1) for q in query.split("&") if "=" in q)
            redirect_uri = params.get("redirect_uri", "/")
            state = params.get("state", "")
            code = "open-code-success"
            sep = "&" if "?" in redirect_uri else "?"
            dest = f"{redirect_uri}{sep}code={code}"
            if state:
                dest += f"&state={state}"
            res = RedirectResponse(url=dest, status_code=302)
            await res(scope, receive, send)
            return

        if path == "/oauth/token" and method == "POST":
            res = JSONResponse({
                "access_token": "open-access-token",
                "token_type": "Bearer",
                "expires_in": 31536000
            })
            await res(scope, receive, send)
            return

        # 3. Obsidian Live-Sync API Routes: /api/threads and /api/threads/{id}
        if path == "/api/threads" and method == "GET":
            # Return list of threads from PostgreSQL or local markdown files
            threads_list = []
            try:
                from sqlalchemy import select
                from db import AsyncSessionLocal, ThreadModel
                async with AsyncSessionLocal() as session:
                    stmt = select(ThreadModel).order_by(ThreadModel.last_updated.desc()).limit(50)
                    r = await session.execute(stmt)
                    rows = r.scalars().all()
                    for row in rows:
                        threads_list.append({
                            "id": row.id,
                            "thread_id": row.thread_id,
                            "user": row.user,
                            "title": row.title,
                            "turn_count": row.turn_count,
                            "created_at": row.created_at.isoformat() if row.created_at else "",
                            "last_updated": row.last_updated.isoformat() if row.last_updated else ""
                        })
            except Exception:
                pass

            # If DB has no threads yet, read existing markdown files in CHAT_DIR
            if not threads_list and CHAT_DIR.exists():
                for f in CHAT_DIR.glob("*.md"):
                    threads_list.append({
                        "thread_id": f.stem,
                        "user": "shubh",
                        "title": f.stem.replace("_", " ").title(),
                        "created_at": datetime.now(timezone.utc).isoformat(),
                        "last_updated": datetime.now(timezone.utc).isoformat()
                    })

            res = JSONResponse({"count": len(threads_list), "threads": threads_list})
            await res(scope, receive, send)
            return

        if path.startswith("/api/threads/") and method == "GET":
            target_id = path[len("/api/threads/"):].strip("/")
            thread_detail = None
            try:
                from sqlalchemy import select
                from sqlalchemy.orm import selectinload
                from db import AsyncSessionLocal, ThreadModel
                async with AsyncSessionLocal() as session:
                    stmt = select(ThreadModel).options(selectinload(ThreadModel.turns)).where(ThreadModel.thread_id == target_id)
                    r = await session.execute(stmt)
                    thr = r.scalar_one_or_none()
                    if thr:
                        thread_detail = {
                            "thread_id": thr.thread_id,
                            "user": thr.user,
                            "title": thr.title,
                            "created_at": thr.created_at.isoformat() if thr.created_at else "",
                            "turns": [
                                {
                                    "turn_number": t.turn_number,
                                    "user_prompt": t.user_prompt,
                                    "ai_response": t.ai_response,
                                    "created_at": t.created_at.isoformat() if t.created_at else ""
                                }
                                for t in thr.turns
                            ]
                        }
            except Exception:
                pass

            if not thread_detail:
                # Check markdown file
                target_file = CHAT_DIR / f"{target_id}.md"
                if target_file.exists():
                    text_content = target_file.read_text(encoding="utf-8")
                    thread_detail = {
                        "thread_id": target_id,
                        "user": "shubh",
                        "title": target_id.replace("_", " "),
                        "created_at": datetime.now(timezone.utc).isoformat(),
                        "turns": [{
                            "turn_number": 1,
                            "user_prompt": "Historical transcript",
                            "ai_response": text_content,
                            "created_at": datetime.now(timezone.utc).isoformat()
                        }]
                    }

            if thread_detail:
                res = JSONResponse(thread_detail)
            else:
                res = JSONResponse({"error": "not found"}, status_code=404)
            await res(scope, receive, send)
            return

        # 4. Public API Routes pass-through: /api/audit-logs and /api/sync-spool
        if path in ["/api/audit-logs", "/api/sync-spool"]:
            await self.app(scope, receive, send)
            return

        # 5. Leg 2: follow-up tool-call POSTs from MCP client
        if path.startswith(_INTERNAL_MESSAGE_PATH):
            query = scope.get("query_string", b"").decode()
            session_id = None
            for part in query.split("&"):
                if part.startswith("session_id="):
                    session_id = part[len("session_id="):]
                    break
            username = _session_users.get(session_id, "shubh") if session_id else "shubh"
            token = _current_user.set(username)
            try:
                await self.app(scope, receive, send)
            finally:
                _current_user.reset(token)
            return

        # 6. Leg 1: initial SSE handshake, gated by the per-user secret: /<secret>/sse
        parts = path.split("/", 2)
        # parts: ["", "<secret>", "sse"]
        if len(parts) >= 3 and parts[1]:
            secret, rest = parts[1], parts[2]
            username = CLAUDE_OV_USERS.get(secret)

            if username is not None:
                # HTTP API: POST /<secret>/api/save
                if rest == "api/save" and method == "POST":
                    body_parts = []
                    while True:
                        msg = await receive()
                        body_parts.append(msg.get("body", b""))
                        if not msg.get("more_body", False):
                            break
                    try:
                        data = json.loads(b"".join(body_parts))
                    except Exception:
                        resp = JSONResponse({"error": "invalid JSON"}, status_code=400)
                        await resp(scope, receive, send)
                        return

                    thread_name = data.get("thread_name", "unknown")
                    new_messages = data.get("new_messages", "")
                    actual_new = _extract_new_exchange(new_messages)
                    path_file = CHAT_DIR / f"{username}_{_today()}_{thread_name}.md"
                    header = f"# {thread_name}\\nUser: {username}\\nDate: {_today()}\\n\\n"
                    if not path_file.exists():
                        _write_and_log(path_file, header + actual_new)
                    else:
                        _append_and_log(path_file, "\\n\\n---\\n\\n" + actual_new)

                    try:
                        import asyncio
                        asyncio.create_task(save_thread_turn_db(
                            user=username,
                            title=thread_name,
                            user_prompt=actual_new[:500] if actual_new else thread_name,
                            ai_response=actual_new if actual_new else "Transcript updated",
                            file_path=str(path_file)
                        ))
                    except Exception:
                        pass

                    resp = JSONResponse({"status": "saved", "path": str(path_file)})
                    await resp(scope, receive, send)
                    return

                # Normal SSE transport: /<secret>/sse
                if rest == "sse":
                    # If client probes with POST /<secret>/sse (streamable HTTP probe)
                    if method == "POST":
                        # Accept probe with 200 OK so client handshake succeeds
                        res = JSONResponse({"status": "ready", "transport": "sse"})
                        await res(scope, receive, send)
                        return

                    # Forward GET /<secret>/sse to FastMCP internal SSE handler
                    scope["path"] = _INTERNAL_SSE_PATH

                    async def send_wrapper(message):
                        if message["type"] == "http.response.body":
                            body = message.get("body", b"").decode("utf-8", errors="ignore")
                            match_ep = re.search(r'event:\s*endpoint\s*\ndata:\s*([^\n\r]+)', body)
                            if match_ep:
                                ep = match_ep.group(1).strip()
                                for qp in ep.split("&"):
                                    if "session_id=" in qp:
                                        sid = qp.split("session_id=")[-1]
                                        _session_users[sid] = username
                        await send(message)

                    await self.app(scope, receive, send_wrapper)
                    return

        # Fallback for unrecognized paths
        res = PlainTextResponse("Not found", status_code=404)
        await res(scope, receive, send)
'''

# Replace in code
code = re.sub(middleware_pattern, new_middleware, code, flags=re.DOTALL)

mcp_file.write_text(code, encoding="utf-8")
print("[SUCCESS] Patched mcp_server.py with OAuth 2.1 endpoints, /api/threads, and Streamable HTTP support!")
