from typing import List, Dict, Any, Optional
from sqlalchemy import select, or_, func
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.database.models import FileModel, ChunkModel, FileRelationshipModel

async def search_knowledge_base(
    query: str,
    session: AsyncSession,
    category: Optional[str] = None,
    limit: int = 5
) -> List[Dict[str, Any]]:
    """
    Hybrid multi-layered search matching query against:
    1. Chunk content & headings
    2. File titles & file names
    3. Category and tags
    """
    terms = [term.strip().lower() for term in query.split() if len(term.strip()) > 1]
    if not terms:
        terms = [query.strip().lower()]

    # Construct search filters
    conditions = []
    for term in terms:
        pattern = f"%{term}%"
        conditions.append(
            or_(
                ChunkModel.content.ilike(pattern),
                ChunkModel.heading.ilike(pattern),
                FileModel.title.ilike(pattern),
                FileModel.file_name.ilike(pattern),
                FileModel.category.ilike(pattern)
            )
        )

    stmt = (
        select(ChunkModel, FileModel)
        .join(FileModel, ChunkModel.file_id == FileModel.id)
        .where(or_(*conditions))
    )

    if category:
        stmt = stmt.where(FileModel.category.ilike(f"%{category}%"))

    stmt = stmt.limit(limit * 3) # Over-fetch for deduplication & ranking
    result = await session.execute(stmt)
    rows = result.all()

    # Score and aggregate results
    ranked_results = []
    seen_files = {}

    for chunk, file in rows:
        score = 0
        q_lower = query.lower()
        
        if file.title and q_lower in file.title.lower():
            score += 10
        if file.file_name and q_lower in file.file_name.lower():
            score += 8
        if chunk.heading and q_lower in chunk.heading.lower():
            score += 6
        if chunk.content and q_lower in chunk.content.lower():
            score += 4
        
        # Keyword term overlap
        for t in terms:
            if t in chunk.content.lower():
                score += 1

        entry = {
            "file_id": file.id,
            "file_name": file.file_name,
            "title": file.title or file.file_name,
            "category": file.category,
            "tags": file.tags,
            "heading": chunk.heading,
            "chunk_index": chunk.chunk_index,
            "snippet": chunk.content[:400] + ("..." if len(chunk.content) > 400 else ""),
            "score": score
        }

        # Keep best chunk per file or allow top chunks
        if file.id not in seen_files or seen_files[file.id]["score"] < score:
            seen_files[file.id] = entry

    sorted_list = sorted(seen_files.values(), key=lambda x: x["score"], reverse=True)
    return sorted_list[:limit]


async def get_file_details(file_identifier: str, session: AsyncSession) -> Optional[Dict[str, Any]]:
    """
    Retrieves full content, chunks, and relationships for a specific file by ID or filename.
    """
    stmt = select(FileModel).where(
        or_(
            FileModel.file_name == file_identifier,
            FileModel.file_name == f"{file_identifier}.md",
            FileModel.id == (int(file_identifier) if file_identifier.isdigit() else -1)
        )
    )
    result = await session.execute(stmt)
    file = result.scalar_one_or_none()
    if not file:
        return None

    # Get chunks
    chunk_stmt = select(ChunkModel).where(ChunkModel.file_id == file.id).order_by(ChunkModel.chunk_index)
    chunk_res = await session.execute(chunk_stmt)
    chunks = chunk_res.scalars().all()

    # Get relationships
    rel_stmt = select(FileRelationshipModel).where(FileRelationshipModel.source_file_id == file.id)
    rel_res = await session.execute(rel_stmt)
    rels = rel_res.scalars().all()

    return {
        "id": file.id,
        "file_name": file.file_name,
        "title": file.title,
        "category": file.category,
        "tags": file.tags,
        "source_refs": file.source_refs,
        "path": file.path,
        "version": file.version,
        "chunks": [{"heading": c.heading, "content": c.content} for c in chunks],
        "outgoing_wikilinks": [r.target_file_name for r in rels]
    }


async def get_related_notes(file_name: str, session: AsyncSession) -> List[Dict[str, Any]]:
    """
    Finds all forward and backward linked notes for a given concept.
    """
    clean_name = file_name.replace(".md", "")
    
    # 1. Forward links
    stmt = (
        select(FileRelationshipModel, FileModel)
        .join(FileModel, FileRelationshipModel.source_file_id == FileModel.id)
        .where(FileModel.file_name.ilike(f"{clean_name}%"))
    )
    res = await session.execute(stmt)
    forward = [{"type": "outgoing", "target": r.target_file_name} for r, f in res.all()]

    # 2. Backlinks (files that link TO clean_name)
    back_stmt = (
        select(FileModel)
        .join(FileRelationshipModel, FileRelationshipModel.source_file_id == FileModel.id)
        .where(FileRelationshipModel.target_file_name.ilike(f"%{clean_name}%"))
    )
    back_res = await session.execute(back_stmt)
    backlinks = [{"type": "incoming_backlink", "file_name": f.file_name, "title": f.title} for f in back_res.scalars().all()]

    return forward + backlinks
