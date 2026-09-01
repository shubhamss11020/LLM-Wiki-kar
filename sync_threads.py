"""
Sync threads and interaction records from Neon DB / Remote Render Backend into local Obsidian vault.
"""

import os
import sys
import asyncio
import httpx
import re
import datetime
import pytz

BACKEND_API_URL = os.getenv("BACKEND_API_URL", "https://llm-wiki-kar.onrender.com")
VAULT_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "vault"))

def _slugify(text: str, max_len: int = 50) -> str:
    slug = re.sub(r"[^\w\s-]", "", text.lower().strip())
    slug = re.sub(r"[\s_]+", "-", slug)
    return slug[:max_len].rstrip("-") or "conversation"

def _git_commit_file(file_path: str, message: str) -> None:
    try:
        import subprocess
        repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__)))
        if os.path.exists(os.path.join(repo_root, ".git")):
            rel_path = os.path.relpath(file_path, repo_root)
            subprocess.run(["git", "add", rel_path], cwd=repo_root, capture_output=True, text=True, check=False)
            subprocess.run(["git", "commit", "-m", message], cwd=repo_root, capture_output=True, text=True, check=False)
    except Exception:
        pass

async def sync_remote_to_local_vault():
    print(f"[*] Syncing threads from {BACKEND_API_URL} to local vault: {VAULT_PATH}...")
    threads_dir = os.path.join(VAULT_PATH, "threads")
    os.makedirs(threads_dir, exist_ok=True)
    tz = pytz.timezone("Asia/Kolkata")

    async with httpx.AsyncClient(base_url=BACKEND_API_URL, timeout=30.0) as client:
        # 1. Fetch remote threads
        try:
            r = await client.get("/api/threads")
            if r.status_code == 200:
                threads = r.json().get("threads", [])
                print(f"[+] Found {len(threads)} thread(s) in remote database.")
                for th in threads:
                    th_id = th["thread_id"]
                    detail_resp = await client.get(f"/api/threads/{th_id}")
                    if detail_resp.status_code == 200:
                        detail = detail_resp.json()
                        user = detail.get("user", "shubh")
                        title = detail.get("title", "Skincare Inquiry")
                        slug = _slugify(title)
                        created_dt = detail.get("created_at") or datetime.datetime.now(tz).isoformat()
                        date_str = created_dt[:10]
                        file_name = f"{user}_{slug}_{date_str}.md"
                        file_path = os.path.join(threads_dir, file_name)

                        turns = detail.get("turns", [])
                        turns_md = []
                        for t in turns:
                            t_time = t.get("created_at", "")[11:19] if t.get("created_at") else ""
                            turns_md.append(
                                f"## Turn {t.get('turn_number', 1)} — {t_time}\n\n"
                                f"**User:**\n{t.get('user_prompt', '')}\n\n"
                                f"**AI Response:**\n{t.get('ai_response', '')}\n"
                            )

                        body_content = "\n---\n\n".join(turns_md)
                        md_content = f"""---
thread_id: "{th_id}"
user: "{user}"
title: "{title}"
created: "{detail.get('created_at')}"
last_updated: "{detail.get('last_updated')}"
turn_count: {len(turns)}
---

# {user} — {title} — {date_str}

---

{body_content}
"""
                        with open(file_path, "w", encoding="utf-8") as f:
                            f.write(md_content)
                        _git_commit_file(file_path, f"sync(threads): update {file_name}")
                        print(f"    [Synced] {file_name} ({len(turns)} turns)")
        except Exception as e:
            print(f"[-] Error fetching threads: {e}")

        # 2. Fetch remote generated records & sync to vault/generated/
        try:
            r = await client.get("/api/records")
            if r.status_code == 200:
                records = r.json().get("records", [])
                print(f"[+] Found {len(records)} generation record(s) in remote database.")
                for rec in records:
                    rec_id = rec.get("record_id")
                    created_raw = rec.get("created_at", "")
                    topics = rec.get("topics", ["skincare"])
                    topic_slug = (topics[0] if topics else "skincare").replace(" ", "-").lower()

                    # Parse date for folder structure
                    try:
                        dt = datetime.datetime.fromisoformat(created_raw)
                    except Exception:
                        dt = datetime.datetime.now(tz)

                    date_dir = os.path.join(VAULT_PATH, "generated", str(dt.year), f"{dt.month:02d}", f"{dt.day:02d}")
                    os.makedirs(date_dir, exist_ok=True)
                    gen_filename = f"{dt.strftime('%Y%m%dT%H%M%S%z')}_{topic_slug}_{rec_id}.md"
                    gen_path = os.path.join(date_dir, gen_filename)

                    if not os.path.exists(gen_path):
                        # Fetch full prompt & response
                        prompt = rec.get("prompt_preview", "")
                        response = rec.get("response_preview", "")
                        sources = rec.get("source_files", [])
                        sources_str = "\n".join([f"- [[{s}]]" for s in sources]) or "- None"

                        content = f"""---
id: {rec_id}
created: {rec.get('created_at')}
topics: {topics}
sources: {sources}
---

# Generation Record: {dt.strftime('%Y-%m-%d %H:%M:%S')}

## Prompt
{prompt}

## Referenced Sources
{sources_str}

## Generated Response
{response}
"""
                        with open(gen_path, "w", encoding="utf-8") as f:
                            f.write(content)
                        print(f"    [Synced Note] {gen_filename}")
        except Exception as e:
            print(f"[-] Error fetching records: {e}")

    print("[SUCCESS] Vault sync complete! All remote cloud threads and notes are synchronized locally.")

async def main():
    watch_mode = "--watch" in sys.argv or "-w" in sys.argv
    if watch_mode:
        print("[*] Starting continuous real-time sync watcher (polling every 3s)... Press Ctrl+C to stop.\n")
        while True:
            try:
                await sync_remote_to_local_vault()
            except Exception as e:
                print(f"[-] Sync error: {e}")
            await asyncio.sleep(3)
    else:
        await sync_remote_to_local_vault()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[!] Watcher stopped.")
