import re
import yaml
from typing import Dict, Any, List, Tuple

WIKILINK_PATTERN = re.compile(r"\[\[(.*?)\]\]")
FRONTMATTER_PATTERN = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)

def extract_frontmatter_and_content(raw_text: str) -> Tuple[Dict[str, Any], str]:
    """
    Extracts YAML frontmatter dictionary and clean Markdown body.
    """
    frontmatter = {}
    content = raw_text

    match = FRONTMATTER_PATTERN.match(raw_text)
    if match:
        yaml_text = match.group(1)
        try:
            frontmatter = yaml.safe_load(yaml_text) or {}
        except Exception:
            frontmatter = {}
        content = raw_text[match.end():]

    return frontmatter, content

def extract_wikilinks(content: str) -> List[str]:
    """
    Extracts all [[wikilink]] references within text.
    Strips aliases (e.g. [[Target|Alias]] -> Target).
    """
    links = []
    matches = WIKILINK_PATTERN.findall(content)
    for m in matches:
        clean_target = m.split("|")[0].strip()
        # Remove any surrounding brackets/quotes
        clean_target = clean_target.strip("[]'\"")
        if clean_target and clean_target not in links:
            links.append(clean_target)
    return links

def parse_markdown_note(raw_text: str, file_path: str) -> Dict[str, Any]:
    """
    Comprehensive parser for atomic knowledge notes.
    """
    metadata, content = extract_frontmatter_and_content(raw_text)
    body_links = extract_wikilinks(content)
    
    # Extract related from frontmatter if available
    frontmatter_related = metadata.get("related", [])
    if isinstance(frontmatter_related, list):
        for r in frontmatter_related:
            for lk in extract_wikilinks(str(r)):
                if lk not in body_links:
                    body_links.append(lk)

    title = metadata.get("title")
    if not title:
        # Fallback to first # Heading
        for line in content.splitlines():
            if line.startswith("# "):
                title = line.replace("# ", "").strip()
                break
    
    tags = metadata.get("tags", [])
    if isinstance(tags, str):
        tags = [tags]

    return {
        "id": metadata.get("id"),
        "title": title,
        "category": metadata.get("category", "General"),
        "tags": tags,
        "source_refs": metadata.get("source_refs", []),
        "wikilinks": body_links,
        "raw_content": content,
        "frontmatter": metadata
    }
