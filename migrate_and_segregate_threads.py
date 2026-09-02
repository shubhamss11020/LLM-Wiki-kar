"""
Migrate existing vault/threads/ files into date-partitioned subfolders
(e.g., vault/threads/YYYY-MM-DD/HH-MM-SS_<user>_<slug>.md) and generate
vault/threads/Timeline.md in ascending chronological order.
"""

import os
import re
import shutil
import datetime

VAULT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "vault"))
THREADS_DIR = os.path.join(VAULT_DIR, "threads")

def parse_thread_metadata(file_path):
    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()

    # 1. Parse YAML frontmatter
    thread_id_m = re.search(r'thread_id:\s*"([^"]+)"', content)
    user_m = re.search(r'user:\s*"([^"]+)"', content)
    title_m = re.search(r'title:\s*"([^"]+)"', content)
    created_m = re.search(r'created:\s*"([^"]+)"', content)
    turn_count_m = re.search(r'turn_count:\s*(\d+)', content)

    thread_id = thread_id_m.group(1) if thread_id_m else "thr-unknown"
    user = user_m.group(1) if user_m else "shubh"
    title = title_m.group(1) if title_m else "Conversation"
    created_raw = created_m.group(1) if created_m else ""
    turns = int(turn_count_m.group(1)) if turn_count_m else 1

    # 2. Parse First Turn Time & Prompt
    first_turn_time_m = re.search(r'## Turn 1 —\s*([\d:]+)', content)
    turn_time_str = first_turn_time_m.group(1) if first_turn_time_m else "00:00:00"

    prompt_m = re.search(r'\*\*User:\*\*\s*\n(.*?)(?=\n\n\*\*AI Response:\*\*|\Z)', content, re.DOTALL)
    first_prompt = prompt_m.group(1).strip() if prompt_m else title

    # Clean first prompt for preview
    first_prompt_preview = first_prompt.replace("\n", " ").strip()
    if len(first_prompt_preview) > 80:
        first_prompt_preview = first_prompt_preview[:77] + "..."

    # Determine Date and Time
    date_str = ""
    time_str = ""
    dt_obj = None

    if created_raw:
        try:
            clean_iso = created_raw.replace("Z", "+00:00")
            dt_obj = datetime.datetime.fromisoformat(clean_iso)
            date_str = dt_obj.strftime("%Y-%m-%d")
            time_str = dt_obj.strftime("%H-%M-%S")
        except Exception:
            pass

    if not date_str:
        fn_date = re.search(r'(\d{4}-\d{2}-\d{2})', os.path.basename(file_path))
        if fn_date:
            date_str = fn_date.group(1)
        else:
            date_str = datetime.date.today().strftime("%Y-%m-%d")

    if not time_str or time_str == "00-00-00":
        clean_time = turn_time_str.replace(":", "-")
        parts = clean_time.split("-")
        if len(parts) == 3:
            time_str = f"{int(parts[0]):02d}-{int(parts[1]):02d}-{int(parts[2]):02d}"
        elif len(parts) == 2:
            time_str = f"{int(parts[0]):02d}-{int(parts[1]):02d}-00"
        else:
            time_str = "12-00-00"

    if dt_obj is None:
        try:
            dt_obj = datetime.datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H-%M-%S")
        except Exception:
            dt_obj = datetime.datetime(2026, 9, 1, 0, 0, 0)

    slug = re.sub(r"[^\w\s-]", "", title.lower().strip())
    slug = re.sub(r"[\s_]+", "-", slug)[:45].rstrip("-") or "thread"

    return {
        "file_path": file_path,
        "thread_id": thread_id,
        "user": user,
        "title": title,
        "slug": slug,
        "date_str": date_str,
        "time_str": time_str,
        "dt_obj": dt_obj,
        "turns": turns,
        "prompt_preview": first_prompt_preview,
        "content": content
    }

def main():
    if not os.path.exists(THREADS_DIR):
        print(f"Threads directory not found: {THREADS_DIR}")
        return

    entries = []
    for item in os.listdir(THREADS_DIR):
        full_path = os.path.join(THREADS_DIR, item)
        if os.path.isfile(full_path) and item.endswith(".md") and item != "Timeline.md" and item != "index.md":
            meta = parse_thread_metadata(full_path)
            entries.append(meta)

    print(f"Found {len(entries)} thread files to migrate.")

    entries.sort(key=lambda x: x["dt_obj"])

    migrated_entries = []

    for meta in entries:
        date_folder = os.path.join(THREADS_DIR, meta["date_str"])
        os.makedirs(date_folder, exist_ok=True)

        new_filename = f"{meta['time_str']}_{meta['user']}_{meta['slug']}.md"
        new_path = os.path.join(date_folder, new_filename)

        counter = 1
        while os.path.exists(new_path) and new_path != meta["file_path"]:
            new_filename = f"{meta['time_str']}_{meta['user']}_{meta['slug']}_{counter}.md"
            new_path = os.path.join(date_folder, new_filename)
            counter += 1

        if meta["file_path"] != new_path:
            shutil.move(meta["file_path"], new_path)

        rel_link = f"{meta['date_str']}/{new_filename}"
        meta["new_path"] = new_path
        meta["rel_link"] = rel_link
        meta["filename_clean"] = new_filename[:-3]
        migrated_entries.append(meta)

    timeline_path = os.path.join(THREADS_DIR, "Timeline.md")
    
    lines = [
        "---",
        "id: threads-timeline",
        "title: Chronological Conversation Threads Timeline",
        "category: Index",
        "tags:",
        "  - timeline",
        "  - threads",
        "  - index",
        f"last_updated: \"{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\"",
        f"total_threads: {len(migrated_entries)}",
        "---",
        "",
        "# 🕒 Chronological Conversation Threads Timeline",
        "",
        "> Master catalogue of all conversational interactions with AskCruz & LLM Wiki, sorted in **ascending chronological order** (oldest to newest).",
        "",
        f"**Total Segregated Threads:** `{len(migrated_entries)}` across `{len(set(m['date_str'] for m in migrated_entries))}` dates.",
        "",
        "---",
        ""
    ]

    current_date = None
    for entry in migrated_entries:
        if entry["date_str"] != current_date:
            current_date = entry["date_str"]
            lines.append(f"\n## 📅 {current_date}\n")
            lines.append("| Time | Thread Title | Turns | First Prompt Preview |")
            lines.append("| :--- | :--- | :---: | :--- |")

        display_time = entry["time_str"].replace("-", ":")
        link_target = f"{entry['date_str']}/{entry['filename_clean']}"
        title_escaped = entry['title'].replace("|", "\\|")
        prompt_escaped = entry['prompt_preview'].replace("|", "\\|")
        
        lines.append(f"| `{display_time}` | [[{link_target}\\|{title_escaped}]] | **{entry['turns']}** | {prompt_escaped} |")

    with open(timeline_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    print(f"[+] Successfully migrated {len(migrated_entries)} threads into date folders.")
    print(f"[+] Generated chronological index: {timeline_path}")

if __name__ == "__main__":
    main()
