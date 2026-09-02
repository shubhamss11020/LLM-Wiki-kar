"""
Thread persistence service.
Dual-writes every conversation thread to:
  1. A structured Markdown file in vault/threads/<user>_<thread_name>_<date>.md (appended per turn)
  2. The threads + thread_turns tables in PostgreSQL with GIN / B-tree indexing
"""

import os
import re
import json
import uuid
import datetime
import pytz
from typing import List, Optional, Dict, Any

from sqlalchemy import select, update, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.app.database.models import ThreadModel, ThreadTurnModel
from backend.app.config import settings


def _slugify(text: str, max_len: int = 50) -> str:
    """Convert text to a clean filesystem-safe slug."""
    slug = re.sub(r"[^\w\s-]", "", text.lower().strip())
    slug = re.sub(r"[\s_]+", "-", slug)
    return slug[:max_len].rstrip("-") or "conversation"


def _build_thread_md(thread_id: str, user: str, title: str,
                     created: str, last_updated: str,
                     turns: List[Dict[str, Any]]) -> str:
    """Render the full thread Markdown content from all turns."""
    md = (
        f"---\n"
        f"thread_id: \"{thread_id}\"\n"
        f"user: \"{user}\"\n"
        f"title: \"{title}\"\n"
        f"created: \"{created}\"\n"
        f"last_updated: \"{last_updated}\"\n"
        f"turn_count: {len(turns)}\n"
        f"---\n\n"
        f"# {user} — {title} — {created[:10]}\n\n"
    )

    for turn in turns:
        time_part = turn.get("time", "")
        turn_num = turn.get("turn_number", "?")
        prompt = turn.get("user_prompt", "")
        response = turn.get("ai_response", "_Awaiting response..._")

        md += (
            f"---\n\n"
            f"## Turn {turn_num} — {time_part}\n\n"
            f"**User:**\n{prompt}\n\n"
            f"**AI Response:**\n{response}\n\n"
        )

    return md


def _git_commit_file(file_path: str, message: str) -> None:
    """Auto-stages and commits the thread file into the Git repository in real time."""
    try:
        import subprocess
        repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
        if os.path.exists(os.path.join(repo_root, ".git")):
            rel_path = os.path.relpath(file_path, repo_root)
            subprocess.run(["git", "add", rel_path], cwd=repo_root, capture_output=True, text=True, check=False)
            subprocess.run(["git", "commit", "-m", message], cwd=repo_root, capture_output=True, text=True, check=False)
    except Exception:
        pass


def _update_timeline_md(vault_path: Optional[str] = None) -> None:
    """Regenerate vault/threads/Timeline.md in ascending chronological order."""
    try:
        if vault_path is None:
            vault_path = settings.VAULT_PATH

        threads_root = os.path.join(vault_path, "threads")
        if not os.path.exists(threads_root):
            return

        entries = []
        for root, dirs, files in os.walk(threads_root):
            dir_name = os.path.basename(root)
            if not re.match(r'^\d{4}-\d{2}-\d{2}$', dir_name):
                continue
            for file in files:
                if file.endswith(".md") and not file.startswith("."):
                    fp = os.path.join(root, file)
                    try:
                        with open(fp, "r", encoding="utf-8", errors="ignore") as f:
                            content = f.read()

                        m_title = re.search(r'title:\s*"([^"]+)"', content)
                        title = m_title.group(1) if m_title else file[:-3]

                        m_turns = re.search(r'turn_count:\s*(\d+)', content)
                        turns = int(m_turns.group(1)) if m_turns else 1

                        m_prompt = re.search(r'\*\*User:\*\*\s*\n(.*?)(?=\n\n\*\*AI Response:\*\*|\Z)', content, re.DOTALL)
                        prompt = m_prompt.group(1).strip().replace("\n", " ") if m_prompt else title
                        if len(prompt) > 80:
                            prompt = prompt[:77] + "..."

                        m_time = re.match(r'^(\d{2}-\d{2}-\d{2})_', file)
                        time_display = m_time.group(1).replace("-", ":") if m_time else "12:00:00"

                        entries.append({
                            "date": dir_name,
                            "time": time_display,
                            "dt_key": f"{dir_name} {time_display}",
                            "title": title,
                            "turns": turns,
                            "prompt": prompt,
                            "rel_link": f"{dir_name}/{file[:-3]}"
                        })
                    except Exception:
                        pass

        entries.sort(key=lambda x: x["dt_key"])

        lines = [
            "---",
            "id: threads-timeline",
            "title: Chronological Conversation Threads Timeline",
            "category: Index",
            "tags:",
            "  - timeline",
            "  - threads",
            "  - index",
            f'last_updated: "{datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}"',
            f"total_threads: {len(entries)}",
            "---",
            "",
            "# 🕒 Chronological Conversation Threads Timeline",
            "",
            "> Master catalogue of all conversational interactions with AskCruz & LLM Wiki, sorted in **ascending chronological order** (oldest to newest).",
            "",
            f"**Total Segregated Threads:** `{len(entries)}` across `{len(set(e['date'] for e in entries))}` dates.",
            "",
            "---",
            ""
        ]

        current_date = None
        for entry in entries:
            if entry["date"] != current_date:
                current_date = entry["date"]
                lines.append(f"\n## 📅 {current_date}\n")
                lines.append("| Time | Thread Title | Turns | First Prompt Preview |")
                lines.append("| :--- | :--- | :---: | :--- |")

            title_escaped = entry['title'].replace("|", "\\|")
            prompt_escaped = entry['prompt'].replace("|", "\\|")
            lines.append(f"| `{entry['time']}` | [[{entry['rel_link']}\\|{title_escaped}]] | **{entry['turns']}** | {prompt_escaped} |")

        timeline_fp = os.path.join(threads_root, "Timeline.md")
        with open(timeline_fp, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
    except Exception:
        pass


def _write_thread_file(thread_id: str, user: str, title: str,
                       created_iso: str, last_updated_iso: str,
                       turns: List[Dict[str, Any]],
                       vault_path: Optional[str] = None) -> str:
    """Write or overwrite the full thread MD file in vault/threads/YYYY-MM-DD/ and auto-commit to Git."""
    try:
        if vault_path is None:
            vault_path = settings.VAULT_PATH

        date_str = created_iso[:10]  # YYYY-MM-DD
        date_dir = os.path.join(vault_path, "threads", date_str)
        os.makedirs(date_dir, exist_ok=True)

        time_part = "12-00-00"
        if len(created_iso) >= 19:
            time_part = created_iso[11:19].replace(":", "-")
        elif turns and turns[0].get("time"):
            time_part = turns[0]["time"].replace(":", "-")

        slug = _slugify(title)
        
        # Check if existing file matching this slug exists in date_dir
        existing_matches = [f for f in os.listdir(date_dir) if f.endswith(f"_{user}_{slug}.md")]
        if existing_matches:
            file_name = existing_matches[0]
        else:
            file_name = f"{time_part}_{user}_{slug}.md"

        file_path = os.path.join(date_dir, file_name)

        md_content = _build_thread_md(
            thread_id=thread_id,
            user=user,
            title=title,
            created=created_iso,
            last_updated=last_updated_iso,
            turns=turns
        )

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(md_content)

        _git_commit_file(file_path, f"thread: save {date_str}/{user}_{slug} ({len(turns)} turns)")

        _update_timeline_md(vault_path)

        return file_path
    except Exception:
        return ""


def _format_dt_tz(dt: Optional[datetime.datetime], tz: pytz.BaseTzInfo) -> str:
    if not dt:
        return ""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=pytz.utc).astimezone(tz).isoformat()
    return dt.astimezone(tz).isoformat()


async def save_thread_turn(
    user: str,
    title: str,
    user_prompt: str,
    ai_response: str,
    thread_id: Optional[str] = None,
    session: Optional[AsyncSession] = None,
    vault_path: Optional[str] = None,
    tz_name: str = "America/New_York"
) -> Dict[str, Any]:
    """
    Main function to save or append an interaction turn to a thread.
    - If thread_id or matching thread today exists: appends turn & rewrites MD.
    - If new thread: creates <user>_<thread_name>_<date>.md & inserts to PostgreSQL.
    """
    tz = pytz.timezone(tz_name)
    now = datetime.datetime.now(tz)
    utc_now = now.astimezone(pytz.utc).replace(tzinfo=None)
    time_str = now.strftime("%H:%M:%S")

    clean_title = title.strip() if title else user_prompt[:60].strip()
    if not clean_title:
        clean_title = "Skincare Inquiry"

    existing_thread: Optional[ThreadModel] = None

    if session:
        if thread_id:
            stmt = select(ThreadModel).options(selectinload(ThreadModel.turns)).where(ThreadModel.thread_id == thread_id)
            res = await session.execute(stmt)
            existing_thread = res.scalar_one_or_none()
        else:
            # Look for active thread with same title and user today
            today_start = utc_now.replace(hour=0, minute=0, second=0, microsecond=0)
            stmt = (
                select(ThreadModel)
                .options(selectinload(ThreadModel.turns))
                .where(
                    and_(
                        ThreadModel.user == user,
                        ThreadModel.title == clean_title,
                        ThreadModel.created_at >= today_start
                    )
                )
                .order_by(ThreadModel.last_updated.desc())
            )
            res = await session.execute(stmt)
            existing_thread = res.scalar_one_or_none()

    threads_dir = os.path.join(vault_path, "threads")
    os.makedirs(threads_dir, exist_ok=True)
    date_str = now.strftime("%Y-%m-%d")
    date_dir = os.path.join(threads_dir, date_str)
    os.makedirs(date_dir, exist_ok=True)
    slug = _slugify(clean_title)

    local_file_path = None
    existing_files = [f for f in os.listdir(date_dir) if f.endswith(f"_{user}_{slug}.md")]
    if existing_files:
        local_file_path = os.path.join(date_dir, existing_files[0])
    else:
        legacy_flat = os.path.join(threads_dir, f"{user}_{slug}_{date_str}.md")
        if os.path.exists(legacy_flat):
            local_file_path = legacy_flat

    if existing_thread:
        # Append turn to existing DB thread
        target_thread_id = existing_thread.thread_id
        new_turn_number = (existing_thread.turn_count or 0) + 1
        existing_thread.turn_count = new_turn_number
        existing_thread.last_updated = utc_now

        if session:
            turn_model = ThreadTurnModel(
                thread_id=target_thread_id,
                turn_number=new_turn_number,
                user_prompt=user_prompt,
                ai_response=ai_response,
                created_at=utc_now
            )
            session.add(turn_model)
            await session.commit()
            await session.refresh(existing_thread, attribute_names=["turns"])

            # Rebuild MD
            created_tz = existing_thread.created_at.replace(tzinfo=pytz.utc).astimezone(tz)
            turns_data = []
            for t in existing_thread.turns:
                t_tz = t.created_at.replace(tzinfo=pytz.utc).astimezone(tz)
                turns_data.append({
                    "turn_number": t.turn_number,
                    "time": t_tz.strftime("%H:%M:%S"),
                    "user_prompt": t.user_prompt,
                    "ai_response": t.ai_response or "_Awaiting response..._"
                })

            file_path = _write_thread_file(
                thread_id=target_thread_id,
                user=user,
                title=clean_title,
                created_iso=created_tz.isoformat(),
                last_updated_iso=now.isoformat(),
                turns=turns_data,
                vault_path=vault_path
            )
            existing_thread.file_path = file_path
            await session.commit()
        else:
            file_path = local_file_path

        return {
            "status": "appended",
            "thread_id": target_thread_id,
            "turn_number": new_turn_number,
            "file_path": file_path,
            "title": clean_title,
            "last_updated": now.isoformat()
        }
    elif local_file_path and os.path.exists(local_file_path):
        # File exists on disk — append turn to local file
        try:
            with open(local_file_path, "r", encoding="utf-8") as f:
                raw_content = f.read()
            
            m_id = re.search(r'thread_id:\s*"([^"]+)"', raw_content)
            extracted_thread_id = m_id.group(1) if m_id else (thread_id or f"thr-{uuid.uuid4().hex[:8]}")
            
            m_count = re.search(r'turn_count:\s*(\d+)', raw_content)
            curr_count = int(m_count.group(1)) if m_count else 1
            new_turn_number = curr_count + 1
            
            new_turn_md = (
                f"\n---\n\n"
                f"## Turn {new_turn_number} — {time_str}\n\n"
                f"**User:**\n{user_prompt}\n\n"
                f"**AI Response:**\n{ai_response}\n"
            )
            raw_content = re.sub(r'turn_count:\s*\d+', f'turn_count: {new_turn_number}', raw_content)
            raw_content = re.sub(r'last_updated:\s*"[^"]*"', f'last_updated: "{now.isoformat()}"', raw_content)
            raw_content += new_turn_md
            
            with open(local_file_path, "w", encoding="utf-8") as f:
                f.write(raw_content)

            return {
                "status": "appended",
                "thread_id": extracted_thread_id,
                "turn_number": new_turn_number,
                "file_path": local_file_path,
                "title": clean_title,
                "last_updated": now.isoformat()
            }
        except Exception:
            pass

    # Create new thread
    target_thread_id = thread_id or f"thr-{uuid.uuid4().hex[:8]}"
    turns_data = [{
        "turn_number": 1,
        "time": time_str,
        "user_prompt": user_prompt,
        "ai_response": ai_response
    }]

    file_path = _write_thread_file(
        thread_id=target_thread_id,
        user=user,
        title=clean_title,
        created_iso=now.isoformat(),
        last_updated_iso=now.isoformat(),
        turns=turns_data,
        vault_path=vault_path
    )

    if session:
        new_thr = ThreadModel(
            thread_id=target_thread_id,
            user=user,
            title=clean_title,
            file_path=file_path,
            turn_count=1,
            timezone=tz_name,
            created_at=utc_now,
            last_updated=utc_now
        )
        session.add(new_thr)
        turn_model = ThreadTurnModel(
            thread_id=target_thread_id,
            turn_number=1,
            user_prompt=user_prompt,
            ai_response=ai_response,
            created_at=utc_now
        )
        session.add(turn_model)
        await session.commit()

    return {
        "status": "created",
        "thread_id": target_thread_id,
        "turn_number": 1,
        "file_path": file_path,
        "title": clean_title,
        "created_at": now.isoformat()
    }


async def create_thread(
    user: str,
    title: str,
    user_prompt: str,
    session: AsyncSession,
    vault_path: Optional[str] = None,
    tz_name: str = "America/New_York"
) -> Dict[str, Any]:
    """Create a new thread with pending turn 1."""
    return await save_thread_turn(
        user=user,
        title=title,
        user_prompt=user_prompt,
        ai_response="_Awaiting response..._",
        session=session,
        vault_path=vault_path,
        tz_name=tz_name
    )


async def append_turn(
    thread_id: str,
    user_prompt: str,
    session: AsyncSession,
    vault_path: Optional[str] = None,
    tz_name: str = "America/New_York"
) -> Dict[str, Any]:
    """Append a pending prompt to an existing thread."""
    tz = pytz.timezone(tz_name)
    now = datetime.datetime.now(tz)
    utc_now = now.astimezone(pytz.utc).replace(tzinfo=None)

    stmt = (
        select(ThreadModel)
        .options(selectinload(ThreadModel.turns))
        .where(ThreadModel.thread_id == thread_id)
    )
    res = await session.execute(stmt)
    thread = res.scalar_one_or_none()
    if not thread:
        raise ValueError(f"Thread '{thread_id}' not found.")

    new_turn = (thread.turn_count or 0) + 1
    thread.turn_count = new_turn
    thread.last_updated = utc_now

    turn = ThreadTurnModel(
        thread_id=thread_id,
        turn_number=new_turn,
        user_prompt=user_prompt,
        ai_response="_Awaiting response..._",
        created_at=utc_now
    )
    session.add(turn)
    await session.commit()
    await session.refresh(thread, attribute_names=["turns"])

    created_tz = thread.created_at.replace(tzinfo=pytz.utc).astimezone(tz)
    turns_data = []
    for t in thread.turns:
        t_tz = t.created_at.replace(tzinfo=pytz.utc).astimezone(tz)
        turns_data.append({
            "turn_number": t.turn_number,
            "time": t_tz.strftime("%H:%M:%S"),
            "user_prompt": t.user_prompt,
            "ai_response": t.ai_response or "_Awaiting response..._"
        })

    file_path = _write_thread_file(
        thread_id=thread_id,
        user=thread.user,
        title=thread.title,
        created_iso=created_tz.isoformat(),
        last_updated_iso=now.isoformat(),
        turns=turns_data,
        vault_path=vault_path
    )

    return {
        "thread_id": thread_id,
        "turn_number": new_turn,
        "file_path": file_path,
        "last_updated": now.isoformat()
    }


async def deliver_response(
    thread_id: str,
    turn_number: int,
    ai_response: str,
    session: AsyncSession,
    vault_path: Optional[str] = None,
    tz_name: str = "America/New_York"
) -> Dict[str, Any]:
    """Write the completed AI response into the specified turn."""
    tz = pytz.timezone(tz_name)
    now = datetime.datetime.now(tz)
    utc_now = now.astimezone(pytz.utc).replace(tzinfo=None)

    stmt = (
        select(ThreadTurnModel)
        .where(
            ThreadTurnModel.thread_id == thread_id,
            ThreadTurnModel.turn_number == turn_number
        )
    )
    res = await session.execute(stmt)
    turn = res.scalar_one_or_none()
    if not turn:
        raise ValueError(f"Turn {turn_number} in thread '{thread_id}' not found.")

    turn.ai_response = ai_response
    await session.flush()

    thread_stmt = (
        select(ThreadModel)
        .options(selectinload(ThreadModel.turns))
        .where(ThreadModel.thread_id == thread_id)
    )
    res_thr = await session.execute(thread_stmt)
    thread = res_thr.scalar_one_or_none()
    if thread:
        thread.last_updated = utc_now

    await session.commit()

    if thread:
        created_tz = thread.created_at.replace(tzinfo=pytz.utc).astimezone(tz)
        turns_data = []
        for t in thread.turns:
            t_tz = t.created_at.replace(tzinfo=pytz.utc).astimezone(tz)
            turns_data.append({
                "turn_number": t.turn_number,
                "time": t_tz.strftime("%H:%M:%S"),
                "user_prompt": t.user_prompt,
                "ai_response": t.ai_response or "_Awaiting response..._"
            })

        file_path = _write_thread_file(
            thread_id=thread_id,
            user=thread.user,
            title=thread.title,
            created_iso=created_tz.isoformat(),
            last_updated_iso=now.isoformat(),
            turns=turns_data,
            vault_path=vault_path
        )
    else:
        file_path = ""

    return {
        "thread_id": thread_id,
        "turn_number": turn_number,
        "status": "response_saved",
        "file_path": file_path,
        "last_updated": now.isoformat()
    }


async def list_threads(
    user: Optional[str] = None,
    session: Optional[AsyncSession] = None,
    limit: int = 50,
    tz_name: str = "America/New_York"
) -> List[Dict[str, Any]]:
    """List all threads, optionally filtered by user."""
    if not session:
        return []

    tz = pytz.timezone(tz_name)
    stmt = select(ThreadModel).order_by(ThreadModel.last_updated.desc()).limit(limit)
    if user:
        stmt = stmt.where(ThreadModel.user == user)

    result = await session.execute(stmt)
    threads = result.scalars().all()

    return [
        {
            "thread_id": t.thread_id,
            "user": t.user,
            "title": t.title,
            "turn_count": t.turn_count,
            "file_path": t.file_path,
            "created_at": _format_dt_tz(t.created_at, tz),
            "last_updated": _format_dt_tz(t.last_updated, tz),
        }
        for t in threads
    ]


async def get_thread_detail(
    thread_id: str,
    session: AsyncSession,
    tz_name: str = "America/New_York"
) -> Optional[Dict[str, Any]]:
    """Get a full thread with all turns."""
    tz = pytz.timezone(tz_name)

    stmt = (
        select(ThreadModel)
        .options(selectinload(ThreadModel.turns))
        .where(ThreadModel.thread_id == thread_id)
    )
    result = await session.execute(stmt)
    thread = result.scalar_one_or_none()
    if not thread:
        return None

    turns = []
    for t in thread.turns:
        turns.append({
            "turn_number": t.turn_number,
            "user_prompt": t.user_prompt,
            "ai_response": t.ai_response,
            "created_at": _format_dt_tz(t.created_at, tz),
        })

    return {
        "thread_id": thread.thread_id,
        "user": thread.user,
        "title": thread.title,
        "turn_count": thread.turn_count,
        "file_path": thread.file_path,
        "created_at": _format_dt_tz(thread.created_at, tz),
        "last_updated": _format_dt_tz(thread.last_updated, tz),
        "turns": turns,
    }
