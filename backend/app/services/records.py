import os
import uuid
import datetime
import pytz
from typing import List, Optional, Dict, Any
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.database.models import GenerationRecordModel
from backend.app.config import settings

async def save_generation_record(
    prompt: str,
    response: str,
    topics: Optional[List[str]] = None,
    source_files: Optional[List[str]] = None,
    vault_path: Optional[str] = None,
    session: Optional[AsyncSession] = None,
    tz_name: str = "Asia/Kolkata"
) -> Dict[str, Any]:
    """
    Saves an LLM interaction record simultaneously to:
    1. A formatted timestamped Markdown file in vault/generated/YYYY/MM/DD/
    2. A row in the PostgreSQL/SQLite 'generations' table
    """
    if topics is None:
        topics = ["skincare-wiki"]
    if source_files is None:
        source_files = []
    if vault_path is None:
        vault_path = settings.VAULT_PATH

    tz = pytz.timezone(tz_name)
    now = datetime.datetime.now(tz)
    
    record_id = f"rec-{uuid.uuid4().hex[:8]}"
    clean_topic = topics[0].replace(" ", "-").lower() if topics else "note"
    
    # Format: YYYYMMDDTHHMMSS+0530_topic_rec-xxxx.md
    time_str = now.strftime("%Y%m%dT%H%M%S%z")
    file_name = f"{time_str}_{clean_topic}_{record_id}.md"

    # Directory: vault/generated/YYYY/MM/DD/
    year_dir = now.strftime("%Y")
    month_dir = now.strftime("%m")
    day_dir = now.strftime("%d")
    gen_dir = os.path.join(vault_path, "generated", year_dir, month_dir, day_dir)
    os.makedirs(gen_dir, exist_ok=True)
    
    full_file_path = os.path.join(gen_dir, file_name)

    # Format YAML Frontmatter and Markdown
    topics_yaml = "\n".join([f"  - {t}" for t in topics])
    sources_yaml = "\n".join([f'  - "{s}"' for s in source_files])
    
    sources_links_md = "\n".join([f"- [[{s}]]" if not s.startswith("[[") else f"- {s}" for s in source_files])
    if not sources_links_md:
        sources_links_md = "_None referenced._"

    iso_created = now.isoformat()

    md_content = f"""---
id: {record_id}
created_at: "{iso_created}"
timezone: "{tz_name}"
type: claude_generation
topics:
{topics_yaml}
source_files:
{sources_yaml}
---

# Claude Generation Record: {clean_topic.title()}

> **Recorded at:** `{iso_created}` (`{tz_name}`)  
> **Record ID:** `{record_id}`

## 1. Prompt / Question
{prompt}

## 2. Retrieved Sources & Citations
{sources_links_md}

## 3. Claude Response
{response}
"""

    with open(full_file_path, "w", encoding="utf-8") as f:
        f.write(md_content)

    # Commit to DB if session provided
    if session:
        utc_created = now.astimezone(pytz.utc).replace(tzinfo=None)
        db_record = GenerationRecordModel(
            record_id=record_id,
            prompt=prompt,
            response=response,
            topics=topics,
            source_files=source_files,
            file_path=full_file_path,
            timezone=tz_name,
            created_at=utc_created
        )
        session.add(db_record)
        await session.commit()

    return {
        "status": "success",
        "record_id": record_id,
        "file_name": file_name,
        "file_path": full_file_path,
        "created_at": iso_created
    }


async def query_records_by_date(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    topic: Optional[str] = None,
    session: Optional[AsyncSession] = None,
    limit: int = 20
) -> List[Dict[str, Any]]:
    """
    Queries generation records by date range and topic filter.
    Handles dates in ISO format 'YYYY-MM-DD' or 'YYYY-MM-DDTHH:MM:SS'.
    """
    if not session:
        return []

    conditions = []
    
    if start_date:
        try:
            start_dt = datetime.datetime.fromisoformat(start_date.replace("Z", "+00:00")).astimezone(pytz.utc).replace(tzinfo=None)
            conditions.append(GenerationRecordModel.created_at >= start_dt)
        except Exception:
            pass

    if end_date:
        try:
            end_dt = datetime.datetime.fromisoformat(end_date.replace("Z", "+00:00")).astimezone(pytz.utc).replace(tzinfo=None)
            conditions.append(GenerationRecordModel.created_at <= end_dt)
        except Exception:
            pass

    stmt = select(GenerationRecordModel)
    if conditions:
        stmt = stmt.where(and_(*conditions))
    
    stmt = stmt.order_by(GenerationRecordModel.created_at.desc()).limit(limit)
    result = await session.execute(stmt)
    records = result.scalars().all()

    output = []
    for r in records:
        output.append({
            "record_id": r.record_id,
            "created_at": r.created_at.isoformat() if r.created_at else "",
            "timezone": r.timezone,
            "topics": r.topics,
            "prompt_preview": r.prompt[:150] + ("..." if len(r.prompt) > 150 else ""),
            "response_preview": r.response[:250] + ("..." if len(r.response) > 250 else ""),
            "file_path": r.file_path,
            "source_files": r.source_files
        })
    return output
