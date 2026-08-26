import logging
import datetime
from typing import Dict, Any
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.database.models import FileModel, ChunkModel, FileRelationshipModel
from backend.app.ingestion.scanner import scan_vault
from backend.app.ingestion.parser import parse_markdown_note
from backend.app.ingestion.chunker import chunk_markdown_by_headings

logger = logging.getLogger(__name__)

async def run_incremental_ingestion(vault_path: str, session: AsyncSession) -> Dict[str, Any]:
    """
    Executes incremental hash-based vault ingestion.
    Only re-chunks and re-indexes files that are new or whose SHA-256 hash changed.
    """
    scanned_files = scan_vault(vault_path)
    
    # Fetch all existing files from DB
    stmt = select(FileModel)
    result = await session.execute(stmt)
    existing_db_files = {f.path: f for f in result.scalars().all()}

    scanned_paths = set()
    indexed_count = 0
    skipped_count = 0
    deleted_count = 0

    for item in scanned_files:
        full_path = item["full_path"]
        scanned_paths.add(full_path)
        current_hash = item["content_hash"]
        
        db_file = existing_db_files.get(full_path)

        # Hash check: if unchanged, skip!
        if db_file and db_file.content_hash == current_hash:
            skipped_count += 1
            continue

        # Parse markdown & frontmatter
        parsed = parse_markdown_note(item["raw_text"], full_path)
        chunks_data = chunk_markdown_by_headings(parsed["raw_content"])

        if db_file:
            # Update existing file record
            db_file.content_hash = current_hash
            db_file.category = item["category"]
            db_file.partition = parsed["partition"]
            db_file.title = parsed["title"]
            db_file.tags = parsed["tags"]
            db_file.source_refs = parsed["source_refs"]
            db_file.last_modified = item["last_modified"]
            db_file.indexed_at = datetime.datetime.utcnow()
            db_file.version += 1
            file_id = db_file.id

            # Delete old chunks and relationships
            await session.execute(delete(ChunkModel).where(ChunkModel.file_id == file_id))
            await session.execute(delete(FileRelationshipModel).where(FileRelationshipModel.source_file_id == file_id))
        else:
            # Insert new file record
            new_file = FileModel(
                path=full_path,
                file_name=item["file_name"],
                content_hash=current_hash,
                category=item["category"],
                partition=parsed["partition"],
                title=parsed["title"],
                tags=parsed["tags"],
                source_refs=parsed["source_refs"],
                last_modified=item["last_modified"],
                indexed_at=datetime.datetime.utcnow(),
                version=1
            )
            session.add(new_file)
            await session.flush()
            file_id = new_file.id

        # Insert chunks
        for c in chunks_data:
            chunk = ChunkModel(
                file_id=file_id,
                chunk_index=c["chunk_index"],
                heading=c["heading"],
                content=c["content"]
            )
            session.add(chunk)

        # Insert outgoing wikilinks / relationships
        for link_target in parsed["wikilinks"]:
            rel = FileRelationshipModel(
                source_file_id=file_id,
                target_file_name=link_target,
                relationship_type="wikilink"
            )
            session.add(rel)

        indexed_count += 1

    # Remove files deleted from vault
    for path, db_file in existing_db_files.items():
        if path not in scanned_paths:
            await session.delete(db_file)
            deleted_count += 1

    await session.commit()

    logger.info(f"Ingestion complete: {indexed_count} indexed, {skipped_count} skipped, {deleted_count} deleted.")
    return {
        "status": "success",
        "total_scanned": len(scanned_files),
        "indexed": indexed_count,
        "skipped": skipped_count,
        "deleted": deleted_count
    }
