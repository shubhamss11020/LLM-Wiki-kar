"""
Thread persistence service.
Dual-writes every conversation thread to:
  1. A single Markdown file in vault/threads/ (appended per turn)
  2. The threads + thread_turns tables in PostgreSQL / SQLite
"""

import os
import re
import json
import uuid
import datetime
import pytz
from typing import List, Optional, Dict, Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.app.database.models import ThreadModel, ThreadTurnModel
from backend.app.config import settings


def _slugify(text: str, max_len: int = 40) -> str:
    """Convert text to a filesystem-safe slug."""
    slug = re.sub(r"[^\w\s-]", "", text.lower().strip())
    slug = re.sub(r"[\s_]+", "-", slug)
    return slug[:max_len].rstrip("-")


def _build_thread_md(thread_id: str, user: str, title: str,
                     created: str, last_updated: str,
                     turns: List[Dict[str, Any]]) -> str:
    """Render the full thread Markdown content from all turns."""
    # YAML frontmatter
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


def _write_thread_file(thread_id: str, user: str, title: str,
                       created_iso: str, last_updated_iso: str,
                       turns: List[Dict[str, Any]],
                       vault_path: Optional[str] = None) -> str:
    try:
        if vault_path is None:
            vault_path = settings.VAULT_PATH

        threads_dir = os.path.join(vault_path, "threads")
        os.makedirs(threads_dir, exist_ok=True)

        date_str = created_iso[:10]  # YYYY-MM-DD
        slug = _slugify(title)
        file_name = f"{user}_{slug}_{date_str}.md"
        file_path = os.path.join(threads_dir, file_name)

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

        return file_path
    except Exception:
        return ""


async def create_thread(
    user: str,
    title: str,
    user_prompt: str,
    session: AsyncSession,
    vault_path: Optional[str] = None,
    tz_name: str = "Asia/Kolkata"
) -> Dict[str, Any]:
    """
    Create a new thread and its first turn (prompt only, response pending).
    Returns thread metadata including thread_id.
    """
    tz = pytz.timezone(tz_name)
    now = datetime.datetime.now(tz)
    thread_id = f"thr-{uuid.uuid4().hex[:8]}"

    utc_now = now.astimezone(pytz.utc).replace(tzinfo=None)

    # Build the first turn data for the MD file
    turns_data = [{
        "turn_number": 1,
        "time": now.strftime("%H:%M:%S"),
        "user_prompt": user_prompt,
        "ai_response": "_Awaiting response..._"
    }]

    file_path = _write_thread_file(
        thread_id=thread_id,
        user=user,
        title=title,
        created_iso=now.isoformat(),
        last_updated_iso=now.isoformat(),
        turns=turns_data,
        vault_path=vault_path
    )

    # DB: Create thread record
    db_thread = ThreadModel(
        thread_id=thread_id,
        user=user,
        title=title,
        file_path=file_path,
        turn_count=1,
        timezone=tz_name,
        created_at=utc_now,
        last_updated=utc_now,
    )
    session.add(db_thread)

    # DB: Create first turn (response is NULL until deliver_response)
    db_turn = ThreadTurnModel(
        thread_id=thread_id,
        turn_number=1,
        user_prompt=user_prompt,
        ai_response=None,
        created_at=utc_now,
    )
    session.add(db_turn)
    await session.commit()

    return {
        "thread_id": thread_id,
        "user": user,
        "title": title,
        "turn_number": 1,
        "file_path": file_path,
        "created_at": now.isoformat(),
    }


async def append_turn(
    thread_id: str,
    user_prompt: str,
    session: AsyncSession,
    vault_path: Optional[str] = None,
    tz_name: str = "Asia/Kolkata"
) -> Dict[str, Any]:
    """
    Append a new turn (prompt) to an existing thread.
    Returns the updated thread metadata.
    """
    tz = pytz.timezone(tz_name)
    now = datetime.datetime.now(tz)
    utc_now = now.astimezone(pytz.utc).replace(tzinfo=None)

    # Fetch the thread with its turns
    stmt = (
        select(ThreadModel)
        .options(selectinload(ThreadModel.turns))
        .where(ThreadModel.thread_id == thread_id)
    )
    result = await session.execute(stmt)
    thread = result.scalar_one_or_none()
    if not thread:
        raise ValueError(f"Thread '{thread_id}' not found.")

    new_turn_number = thread.turn_count + 1

    # DB: Create new turn
    db_turn = ThreadTurnModel(
        thread_id=thread_id,
        turn_number=new_turn_number,
        user_prompt=user_prompt,
        ai_response=None,
        created_at=utc_now,
    )
    session.add(db_turn)

    # DB: Update thread metadata
    thread.turn_count = new_turn_number
    thread.last_updated = utc_now
    await session.commit()

    # Refresh to get the new turn in the list
    await session.refresh(thread, attribute_names=["turns"])

    # Rebuild and rewrite the full MD file
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
        "turn_number": new_turn_number,
        "file_path": file_path,
        "last_updated": now.isoformat(),
    }


async def deliver_response(
    thread_id: str,
    turn_number: int,
    ai_response: str,
    session: AsyncSession,
    vault_path: Optional[str] = None,
    tz_name: str = "Asia/Kolkata"
) -> Dict[str, Any]:
    """
    Write the AI response into the specified turn and rewrite the MD file.
    """
    tz = pytz.timezone(tz_name)
    now = datetime.datetime.now(tz)
    utc_now = now.astimezone(pytz.utc).replace(tzinfo=None)

    # Update the turn's ai_response
    stmt = (
        select(ThreadTurnModel)
        .where(
            ThreadTurnModel.thread_id == thread_id,
            ThreadTurnModel.turn_number == turn_number
        )
    )
    result = await session.execute(stmt)
    turn = result.scalar_one_or_none()
    if not turn:
        raise ValueError(f"Turn {turn_number} in thread '{thread_id}' not found.")

    turn.ai_response = ai_response
    await session.flush()

    # Update thread's last_updated
    thread_stmt = (
        select(ThreadModel)
        .options(selectinload(ThreadModel.turns))
        .where(ThreadModel.thread_id == thread_id)
    )
    result = await session.execute(thread_stmt)
    thread = result.scalar_one_or_none()
    if thread:
        thread.last_updated = utc_now

    await session.commit()

    # Rebuild the full MD file
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
        "last_updated": now.isoformat(),
    }


async def list_threads(
    user: Optional[str] = None,
    session: Optional[AsyncSession] = None,
    limit: int = 50
) -> List[Dict[str, Any]]:
    """List all threads, optionally filtered by user."""
    if not session:
        return []

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
            "created_at": t.created_at.isoformat() if t.created_at else "",
            "last_updated": t.last_updated.isoformat() if t.last_updated else "",
        }
        for t in threads
    ]


async def get_thread_detail(
    thread_id: str,
    session: AsyncSession,
    tz_name: str = "Asia/Kolkata"
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
        t_tz = t.created_at.replace(tzinfo=pytz.utc).astimezone(tz) if t.created_at else None
        turns.append({
            "turn_number": t.turn_number,
            "user_prompt": t.user_prompt,
            "ai_response": t.ai_response,
            "created_at": t_tz.isoformat() if t_tz else "",
        })

    created_tz = thread.created_at.replace(tzinfo=pytz.utc).astimezone(tz) if thread.created_at else None
    updated_tz = thread.last_updated.replace(tzinfo=pytz.utc).astimezone(tz) if thread.last_updated else None

    return {
        "thread_id": thread.thread_id,
        "user": thread.user,
        "title": thread.title,
        "turn_count": thread.turn_count,
        "file_path": thread.file_path,
        "created_at": created_tz.isoformat() if created_tz else "",
        "last_updated": updated_tz.isoformat() if updated_tz else "",
        "turns": turns,
    }
