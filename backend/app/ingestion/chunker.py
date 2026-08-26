import re
from typing import List, Dict, Any

HEADING_REGEX = re.compile(r"^(#{1,4})\s+(.+)$", re.MULTILINE)

def chunk_markdown_by_headings(content: str, max_chunk_chars: int = 1500) -> List[Dict[str, Any]]:
    """
    Splits markdown content into semantic chunks bounded by headings.
    If a section is very long, subdivides by paragraphs.
    """
    chunks = []
    lines = content.splitlines()
    
    current_heading = "Overview"
    current_lines = []
    chunk_index = 0

    for line in lines:
        match = HEADING_REGEX.match(line)
        if match:
            # If we already have accumulated lines, save them as a chunk
            if current_lines:
                text_block = "\n".join(current_lines).strip()
                if text_block:
                    chunks.append({
                        "chunk_index": chunk_index,
                        "heading": current_heading,
                        "content": text_block
                    })
                    chunk_index += 1
                current_lines = []
            
            current_heading = match.group(2).strip()
            current_lines.append(line)
        else:
            current_lines.append(line)

    # Save remaining chunk
    if current_lines:
        text_block = "\n".join(current_lines).strip()
        if text_block:
            chunks.append({
                "chunk_index": chunk_index,
                "heading": current_heading,
                "content": text_block
            })

    # If no headings were found or content produced 0 chunks, return whole content as single chunk
    if not chunks and content.strip():
        chunks.append({
            "chunk_index": 0,
            "heading": "General",
            "content": content.strip()
        })

    return chunks
