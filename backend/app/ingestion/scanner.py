import os
import hashlib
import datetime
from typing import List, Dict, Any

IGNORE_DIRS = {".obsidian", ".git", ".trash", "generated"}

def compute_sha256(content_bytes: bytes) -> str:
    """Computes SHA-256 hash string for raw bytes."""
    return hashlib.sha256(content_bytes).hexdigest()

def scan_vault(vault_path: str) -> List[Dict[str, Any]]:
    """
    Recursively scans the vault for Markdown (.md) files.
    Returns metadata list containing file path, name, category, mtime, and content hash.
    """
    scanned_files = []

    for root, dirs, files in os.walk(vault_path):
        # Filter out ignored directories
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]

        for file in files:
            if file.endswith(".md"):
                full_path = os.path.abspath(os.path.join(root, file))
                rel_path = os.path.relpath(full_path, vault_path)
                
                # Derive category from folder name
                path_parts = rel_path.split(os.sep)
                category = path_parts[0] if len(path_parts) > 1 else "Root"

                try:
                    with open(full_path, "rb") as f:
                        raw_bytes = f.read()
                    
                    content_hash = compute_sha256(raw_bytes)
                    stat_info = os.stat(full_path)
                    last_modified = datetime.datetime.utcfromtimestamp(stat_info.st_mtime)

                    scanned_files.append({
                        "full_path": full_path,
                        "rel_path": rel_path,
                        "file_name": file,
                        "category": category,
                        "content_hash": content_hash,
                        "last_modified": last_modified,
                        "raw_text": raw_bytes.decode("utf-8", errors="ignore")
                    })
                except Exception as e:
                    print(f"Error scanning file {full_path}: {e}")

    return scanned_files
