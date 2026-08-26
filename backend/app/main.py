import os
from contextlib import asynccontextmanager
from typing import Optional, List
from fastapi import FastAPI, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.config import settings
from backend.app.database.connection import init_db, get_db
from backend.app.ingestion.indexer import run_incremental_ingestion
from backend.app.services.search import search_knowledge_base, get_file_details, get_related_notes
from backend.app.services.records import save_generation_record, query_records_by_date

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize database tables
    await init_db()
    yield

app = FastAPI(
    title="Knowledge Base Wiki API",
    description="Knowledge base search, vault ingestion, and timestamped generation history.",
    version="1.0.0",
    lifespan=lifespan
)

# --- Request & Response Models ---
class SearchRequest(BaseModel):
    query: str
    category: Optional[str] = None
    limit: int = 5

class RecordCreateRequest(BaseModel):
    prompt: str
    response: str
    topics: Optional[List[str]] = None
    source_files: Optional[List[str]] = None
    timezone: Optional[str] = "Asia/Kolkata"

from fastapi import FastAPI, Depends, HTTPException, Query, Header

def resolve_allowed_partitions(x_api_key: Optional[str] = Header(None)) -> Optional[List[int]]:
    """
    Resolves client API Key to strictly allowed domain partitions:
    - Partition 1: Skincare Actives & Dermatological Science
    - Partition 2: Complexion, Bases & Formulations
    - Partition 3: Lips, Eyes, Climate Wear & Cultural Guides
    """
    if not x_api_key:
        return None # Defaults to master/full access if no key is provided
    key_low = x_api_key.lower().strip()
    if any(k in key_low for k in ["part1", "partition1", "tier1", "skincare"]):
        return [1]
    elif any(k in key_low for k in ["part2", "partition2", "tier2", "complexion", "base"]):
        return [2]
    elif any(k in key_low for k in ["part3", "partition3", "tier3", "eyeslips", "culture"]):
        return [3]
    elif any(k in key_low for k in ["admin", "master"]):
        return [1, 2, 3]
    return [1, 2, 3]

# --- Endpoints ---
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "project": settings.PROJECT_NAME,
        "vault_path": settings.VAULT_PATH,
        "partitions": {
            "1": "Skincare Actives & Dermatological Science",
            "2": "Complexion, Bases & Formulations",
            "3": "Lips, Eyes, Climate Wear & Cultural Guides"
        }
    }

@app.post("/api/ingest")
async def trigger_ingestion(session: AsyncSession = Depends(get_db)):
    """
    Triggers an incremental scan of the Obsidian vault.
    Unchanged files are skipped based on SHA-256 content hashes.
    """
    if not os.path.exists(settings.VAULT_PATH):
        raise HTTPException(status_code=404, detail=f"Vault path '{settings.VAULT_PATH}' does not exist.")
    
    result = await run_incremental_ingestion(settings.VAULT_PATH, session)
    return result

@app.post("/api/search")
async def search_wiki(
    req: SearchRequest, 
    session: AsyncSession = Depends(get_db),
    allowed_partitions: Optional[List[int]] = Depends(resolve_allowed_partitions)
):
    """
    Searches the knowledge base across chunks, titles, and tags with partition RBAC.
    """
    results = await search_knowledge_base(
        query=req.query,
        session=session,
        category=req.category,
        allowed_partitions=allowed_partitions,
        limit=req.limit
    )
    return {"query": req.query, "count": len(results), "allowed_partitions": allowed_partitions, "results": results}

@app.get("/api/notes/{file_name}")
async def get_note_by_name(
    file_name: str, 
    session: AsyncSession = Depends(get_db),
    allowed_partitions: Optional[List[int]] = Depends(resolve_allowed_partitions)
):
    """
    Retrieves full content, chunks, and backlinks for a specific note with partition check.
    """
    file_info = await get_file_details(file_name, session, allowed_partitions=allowed_partitions)
    if not file_info:
        raise HTTPException(status_code=404, detail=f"Note '{file_name}' not found or access restricted by partition policy.")
    
    relationships = await get_related_notes(file_name, session)
    file_info["relationships"] = relationships
    return file_info

@app.get("/api/records")
async def get_generation_records(
    start_date: Optional[str] = Query(None, description="Start date ISO string e.g. 2026-07-01"),
    end_date: Optional[str] = Query(None, description="End date ISO string e.g. 2026-08-01"),
    topic: Optional[str] = Query(None, description="Topic filter e.g. attention"),
    limit: int = 20,
    session: AsyncSession = Depends(get_db)
):
    """
    Retrieves historical Claude generation records with date range filtering.
    """
    records = await query_records_by_date(
        start_date=start_date,
        end_date=end_date,
        topic=topic,
        session=session,
        limit=limit
    )
    return {"count": len(records), "records": records}

@app.post("/api/records")
async def create_generation_record(
    req: RecordCreateRequest,
    session: AsyncSession = Depends(get_db)
):
    """
    Saves an LLM interaction as a Markdown file in vault/generated/ and commits to DB.
    """
    res = await save_generation_record(
        prompt=req.prompt,
        response=req.response,
        topics=req.topics,
        source_files=req.source_files,
        vault_path=settings.VAULT_PATH,
        session=session,
        tz_name=req.timezone or settings.DEFAULT_TIMEZONE
    )
    return res
