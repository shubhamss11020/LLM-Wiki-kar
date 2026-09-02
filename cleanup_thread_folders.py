import os
import re
import filecmp
import datetime

VAULT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "vault"))
THREADS_DIR = os.path.join(VAULT_DIR, "threads")

def cleanup():
    # 1. Clean up duplicate copies _1.md, _2.md inside date folders
    for root, dirs, files in os.walk(THREADS_DIR):
        dir_name = os.path.basename(root)
        if not re.match(r'^\d{4}-\d{2}-\d{2}$', dir_name):
            continue
        
        # Look for _1.md, _2.md
        for f in files:
            m = re.match(r'^(.*)_(\d+)\.md$', f)
            if m:
                base_name = f"{m.group(1)}.md"
                base_path = os.path.join(root, base_name)
                dup_path = os.path.join(root, f)
                if os.path.exists(base_path):
                    # Base exists, remove duplicate
                    try:
                        os.remove(dup_path)
                        print(f"Removed duplicate: {dir_name}/{f}")
                    except Exception as e:
                        print(f"Error removing {f}: {e}")

    # 2. For remaining root files in THREADS_DIR:
    for f in os.listdir(THREADS_DIR):
        fp = os.path.join(THREADS_DIR, f)
        if os.path.isfile(fp) and f.endswith(".md") and f not in ["Timeline.md", "index.md"]:
            # Find date
            with open(fp, "r", encoding="utf-8", errors="ignore") as file:
                content = file.read()
            
            created_m = re.search(r'created:\s*"([^"]+)"', content)
            date_str = ""
            time_str = ""
            if created_m:
                try:
                    dt = datetime.datetime.fromisoformat(created_m.group(1).replace("Z", "+00:00"))
                    date_str = dt.strftime("%Y-%m-%d")
                    time_str = dt.strftime("%H-%M-%S")
                except Exception:
                    pass
            
            if not date_str:
                fn_date = re.search(r'(\d{4}-\d{2}-\d{2})', f)
                date_str = fn_date.group(1) if fn_date else "2026-09-01"

            if not time_str:
                t_m = re.search(r'## Turn 1 —\s*([\d:]+)', content)
                if t_m:
                    time_str = t_m.group(1).replace(":", "-")
                else:
                    time_str = "12-00-00"

            title_m = re.search(r'title:\s*"([^"]+)"', content)
            title = title_m.group(1) if title_m else f[:-3]
            slug = re.sub(r"[^\w\s-]", "", title.lower().strip())
            slug = re.sub(r"[\s_]+", "-", slug)[:45].rstrip("-") or "thread"

            user_m = re.search(r'user:\s*"([^"]+)"', content)
            user = user_m.group(1) if user_m else "shubh"

            target_dir = os.path.join(THREADS_DIR, date_str)
            os.makedirs(target_dir, exist_ok=True)
            target_fn = f"{time_str}_{user}_{slug}.md"
            target_fp = os.path.join(target_dir, target_fn)

            if os.path.exists(target_fp):
                # Target already exists, remove root copy
                try:
                    os.remove(fp)
                    print(f"Removed root duplicate: {f} (already exists in {date_str})")
                except Exception as e:
                    print(f"Error removing {f}: {e}")
            else:
                try:
                    os.rename(fp, target_fp)
                    print(f"Moved root file: {f} -> {date_str}/{target_fn}")
                except Exception as e:
                    print(f"Error moving {f}: {e}")

if __name__ == "__main__":
    cleanup()
