import time
import logging
from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy import select, or_, func
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.database.models import FileModel, ChunkModel, FileRelationshipModel

logger = logging.getLogger(__name__)

# Fast in-memory query cache: key -> (timestamp, results)
_QUERY_CACHE: Dict[str, Tuple[float, List[Dict[str, Any]]]] = {}
_CACHE_TTL_SECONDS = 60.0 # 1 minute cache for hot queries

# Domain-specific boost terms per partition
PARTITION_BOOST_TERMS = {
    1: [
        "active", "actives", "science", "clinical", "dermatology", "ph", "formulation", 
        "concentration", "stability", "l-ascorbic", "ascorbic", "niacinamide", "retinol", 
        "retinoid", "ceramide", "acid", "antioxidant", "barrier", "serum", "dermatological"
    ],
    2: [
        "complexion", "base", "foundation", "concealer", "primer", "undertone", 
        "shade", "coverage", "silicone", "dimethicone", "pigment", "emulsion", "matte", "dewy"
    ],
    3: [
        "lip", "lips", "eye", "eyes", "mascara", "eyeliner", "lipstick", "tint", 
        "gloss", "climate", "monsoon", "humidity", "sweat", "culture", "bridal", "indian"
    ]
}

async def search_knowledge_base(
    query: str,
    session: AsyncSession,
    category: Optional[str] = None,
    allowed_partitions: Optional[List[int]] = None,
    limit: int = 5
) -> List[Dict[str, Any]]:
    """
    High-performance multi-layered search matching query against:
    1. Chunk content & breadcrumb headings
    2. File titles & file names
    3. Category and tags
    With Partition-specific Scientific Relevance Boosting and Graph Cross-Referencing.
    """
    clean_query = query.strip().lower()
    cache_key = f"{clean_query}|{category}|{str(allowed_partitions)}|{limit}"
    
    # Check in-memory cache
    now = time.time()
    if cache_key in _QUERY_CACHE:
        cached_time, cached_results = _QUERY_CACHE[cache_key]
        if now - cached_time < _CACHE_TTL_SECONDS:
            return cached_results

    terms = [term for term in clean_query.split() if len(term) > 1]
    if not terms:
        terms = [clean_query]

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

    if allowed_partitions is not None:
        effective_partitions = list(set(allowed_partitions + [0]))
        stmt = stmt.where(FileModel.partition.in_(effective_partitions))

    if category:
        stmt = stmt.where(FileModel.category.ilike(f"%{category}%"))

    stmt = stmt.limit(limit * 4) # Over-fetch for accurate ranking & graph scoring
    result = await session.execute(stmt)
    rows = result.all()

    # Determine domain boost terms
    active_boost_terms = []
    if allowed_partitions:
        for p in allowed_partitions:
            active_boost_terms.extend(PARTITION_BOOST_TERMS.get(p, []))
    else:
        for terms_list in PARTITION_BOOST_TERMS.values():
            active_boost_terms.extend(terms_list)

    # Score and aggregate results
    seen_files = {}

    for chunk, file in rows:
        score = 0
        f_title_low = (file.title or "").lower()
        f_name_low = (file.file_name or "").lower()
        c_heading_low = (chunk.heading or "").lower()
        c_content_low = (chunk.content or "").lower()
        tags_low = [t.lower() for t in (file.tags or [])]
        cat_low = (file.category or "").lower()

        # 1. Exact matches
        if clean_query in f_title_low:
            score += 15
        elif any(t in f_title_low for t in terms):
            score += 8

        if clean_query in f_name_low:
            score += 12
            
        if clean_query in c_heading_low:
            score += 10
        elif any(t in c_heading_low for t in terms):
            score += 5

        if clean_query in c_content_low:
            score += 6
        
        # 2. Term frequency overlap
        for t in terms:
            if t in c_content_low:
                score += 1
            if t in tags_low:
                score += 4
            if t in cat_low:
                score += 3

        # 3. Partition Domain Specific Boost (e.g. Tier 1 Science/Active boost)
        for boost_word in active_boost_terms:
            if boost_word in f_title_low or boost_word in tags_low:
                score += 3
            if boost_word in c_heading_low:
                score += 2

        entry = {
            "file_id": file.id,
            "file_name": file.file_name,
            "title": file.title or file.file_name,
            "category": file.category,
            "partition": file.partition,
            "tags": file.tags,
            "heading": chunk.heading,
            "chunk_index": chunk.chunk_index,
            "snippet": chunk.content[:450] + ("..." if len(chunk.content) > 450 else ""),
            "score": score
        }

        # Keep best chunk per file
        if file.id not in seen_files or seen_files[file.id]["score"] < score:
            seen_files[file.id] = entry

    sorted_list = sorted(seen_files.values(), key=lambda x: x["score"], reverse=True)
    final_results = sorted_list[:limit]

    # Save to memory cache
    _QUERY_CACHE[cache_key] = (now, final_results)
    
    # Prune cache if it grows too large
    if len(_QUERY_CACHE) > 500:
        oldest_keys = sorted(_QUERY_CACHE.keys(), key=lambda k: _QUERY_CACHE[k][0])[:100]
        for k in oldest_keys:
            _QUERY_CACHE.pop(k, None)

    return final_results


async def get_file_details(
    file_identifier: str, 
    session: AsyncSession,
    allowed_partitions: Optional[List[int]] = None
) -> Optional[Dict[str, Any]]:
    """
    Retrieves full content, chunks, and relationships for a specific file by ID or filename.
    Enforces partition access rights.
    """
    stmt = select(FileModel).where(
        or_(
            FileModel.file_name == file_identifier,
            FileModel.file_name == f"{file_identifier}.md",
            FileModel.id == (int(file_identifier) if file_identifier.isdigit() else -1)
        )
    )
    if allowed_partitions is not None:
        effective_partitions = list(set(allowed_partitions + [0]))
        stmt = stmt.where(FileModel.partition.in_(effective_partitions))

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
        "partition": file.partition,
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
