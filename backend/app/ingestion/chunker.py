import re
from typing import List, Dict, Any

HEADING_REGEX = re.compile(r"^(#{1,4})\s+(.+)$")

def chunk_markdown_by_headings(content: str, max_chunk_chars: int = 1500) -> List[Dict[str, Any]]:
    """
    Splits markdown content into semantic chunks bounded by headings,
    injecting the hierarchical breadcrumb path (e.g. Overview > pH Stability).
    """
    chunks = []
    lines = content.splitlines()
    
    current_heading = "Overview"
    heading_hierarchy = {} # level -> title
    current_lines = []
    chunk_index = 0

    def get_breadcrumb() -> str:
        if not heading_hierarchy:
            return current_heading
        sorted_levels = sorted(heading_hierarchy.keys())
        return " > ".join(heading_hierarchy[lvl] for lvl in sorted_levels)

    for line in lines:
        match = HEADING_REGEX.match(line)
        if match:
            level = len(match.group(1))
            heading_text = match.group(2).strip()

            # If we already have accumulated lines, save them as a chunk
            if current_lines:
                text_block = "\n".join(current_lines).strip()
                if text_block:
                    breadcrumb = get_breadcrumb()
                    chunks.append({
                        "chunk_index": chunk_index,
                        "heading": breadcrumb if breadcrumb != current_heading else current_heading,
                        "content": text_block
                    })
                    chunk_index += 1
                current_lines = []
            
            # Update heading hierarchy stack
            # Remove any deeper levels from the stack
            heading_hierarchy = {lvl: txt for lvl, txt in heading_hierarchy.items() if lvl < level}
            heading_hierarchy[level] = heading_text
            current_heading = heading_text
            current_lines.append(line)
        else:
            current_lines.append(line)

    # Save remaining chunk
    if current_lines:
        text_block = "\n".join(current_lines).strip()
        if text_block:
            breadcrumb = get_breadcrumb()
            chunks.append({
                "chunk_index": chunk_index,
                "heading": breadcrumb if breadcrumb != current_heading else current_heading,
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
