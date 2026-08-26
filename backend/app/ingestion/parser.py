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

def determine_partition(file_path: str, category: str, title: str, tags: List[str], raw_text: str) -> int:
    """
    Classifies a note into one of 3 strict, mutually exclusive partitions:
    1: Skincare Actives & Dermatological Science
    2: Complexion, Bases & Formulations
    3: Lips, Eyes, Climate Wear & Cultural Guides
    """
    path_low = file_path.lower().replace("\\", "/")
    text_low = (category + " " + title + " " + " ".join(tags) + " " + raw_text[:600]).lower()

    if "/actives/" in path_low or category == "Actives":
        return 1
    if "/comparisons/" in path_low:
        if any(k in path_low for k in ["vitamin-c", "kojic", "bakuchiol"]):
            return 1
        elif "foundation" in path_low or "cc-cream" in path_low:
            return 2
        return 1

    if "/formulations/" in path_low:
        if any(k in path_low for k in ["foundation", "powder", "highlighter", "hybrid"]):
            return 2
        elif any(k in path_low for k in ["lipstick", "kajal", "kohl"]):
            return 3
        return 2

    if "/guides/" in path_low:
        if "undertone" in path_low:
            return 2
        return 3

    # For Source notes and general clippings, classify by keywords
    p1_keywords = ["vitamin c", "niacinamide", "kojic", "salicylic", "bha", "arbutin", "bakuchiol", "retinol", "hyaluronic", "caffeine", "peptide", "ceramide", "barrier", "spf", "sunscreen", "cica", "dark circle", "pigmentation", "squalane", "cleansing", "panthenol", "allantoin", "fungal acne"]
    p2_keywords = ["foundation", "stick vs cream", "cream to powder", "bb cream", "cc cream", "compact powder", "banana powder", "translucent powder", "setting powder", "highlighter", "glass skin", "color correct", "concealer", "blush", "bronzer", "primer", "baking technique", "undertone", "shade match"]
    p3_keywords = ["lipstick", "matte as hell", "smudge-me-not", "crayon", "lip gloss", "lip oil", "lip liner", "lip tint", "kajal", "kohl", "eyeliner", "mascara", "eyeshadow", "monsoon-proof", "sweat-proof", "humidity", "beginner", "starter kit", "under 500", "under 1500", "under 2000", "festive", "onam", "durga puja", "karwa", "janmashtami", "teej", "aadi", "eid", "navratri", "wedding", "raksha"]

    s1 = sum(1 for k in p1_keywords if k in text_low)
    s2 = sum(1 for k in p2_keywords if k in text_low)
    s3 = sum(1 for k in p3_keywords if k in text_low)

    if s1 >= s2 and s1 >= s3 and s1 > 0:
        return 1
    elif s2 >= s1 and s2 >= s3 and s2 > 0:
        return 2
    elif s3 > 0:
        return 3

    # Global hubs
    if "/authors/" in path_low or category == "Authors" or category == "Index" or category == "Entities":
        return 0

    return 1

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

    category = metadata.get("category", "General")
    partition = determine_partition(file_path, category, title or "", tags, raw_text)

    return {
        "id": metadata.get("id"),
        "title": title,
        "category": category,
        "partition": partition,
        "tags": tags,
        "source_refs": metadata.get("source_refs", []),
        "wikilinks": body_links,
        "raw_content": content,
        "frontmatter": metadata
    }
