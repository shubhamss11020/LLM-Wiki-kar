import os
import sys
import asyncio
import datetime
import pytz

# Ensure repository root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app.config import settings
from backend.app.services.threads import save_thread_turn, _write_thread_file, _slugify

async def test_thread_markdown_lifecycle():
    print("\n--- 1. Testing Thread File Creation & Multi-Turn Append ---")
    user = "shubh"
    title = "Best Skincare Product for Acne and Oily Skin"
    prompt_1 = "Give best skincare product for acne / oily skin"
    response_1 = "No dedicated treatment SKU exists in the wiki for acne/oily skin. Salicylic Acid (2% BHA) dissolves sebum plugs."

    tz = pytz.timezone("Asia/Kolkata")
    now = datetime.datetime.now(tz)
    date_str = now.strftime("%Y-%m-%d")
    slug = _slugify(title)
    test_file_path = os.path.join(settings.VAULT_PATH, "threads", f"{user}_{slug}_{date_str}.md")
    if os.path.exists(test_file_path):
        os.remove(test_file_path)

    # Turn 1
    res1 = await save_thread_turn(
        user=user,
        title=title,
        user_prompt=prompt_1,
        ai_response=response_1,
        vault_path=settings.VAULT_PATH,
        tz_name="Asia/Kolkata"
    )
    print(f"[PASS] Turn 1 Saved: Status='{res1['status']}', Thread ID='{res1['thread_id']}', File='{res1['file_path']}'")
    assert os.path.exists(res1["file_path"]), f"Thread file {res1['file_path']} must exist on disk!"

    tz = pytz.timezone("Asia/Kolkata")
    now = datetime.datetime.now(tz)
    date_str = now.strftime("%Y-%m-%d")
    slug = _slugify(title)
    expected_filename = f"{user}_{slug}_{date_str}.md"
    actual_filename = os.path.basename(res1["file_path"])
    assert actual_filename == expected_filename, f"Expected filename '{expected_filename}', got '{actual_filename}'"
    print(f"[PASS] File naming verified: {expected_filename}")

    # Turn 2 - Follow-up prompt in same thread
    prompt_2 = "What about SUGAR Niacinamide Blush for oily skin?"
    response_2 = "SUGAR Niacinamide Blush & Cheek Tints contains 2% Niacinamide + Vitamin E, 12-hour sweat-proof, useful for cosmetic wear without clogging pores."

    res2 = await save_thread_turn(
        user=user,
        title=title,
        user_prompt=prompt_2,
        ai_response=response_2,
        thread_id=res1["thread_id"],
        vault_path=settings.VAULT_PATH,
        tz_name="Asia/Kolkata"
    )
    print(f"[PASS] Turn 2 Appended: Status='{res2['status']}', Turn Number={res2['turn_number']}, File='{res2['file_path']}'")

    # Verify content in the single file
    with open(res1["file_path"], "r", encoding="utf-8") as f:
        content = f.read()

    assert "Turn 1" in content, "Thread MD must contain Turn 1"
    assert "Turn 2" in content, "Thread MD must contain Turn 2"
    assert "turn_count: 2" in content, "Frontmatter must reflect turn_count: 2"
    assert prompt_1 in content, "Turn 1 prompt must be present"
    assert response_1 in content, "Turn 1 response must be present"
    assert prompt_2 in content, "Turn 2 prompt must be present"
    assert response_2 in content, "Turn 2 response must be present"

    print("\n--- 2. Thread Markdown File Content Preview ---")
    print(content)
    print("========================================================")
    print("THREAD PERSISTENCE TEST PASSED 100% SUCCESSFULLY!")
    print("========================================================")

if __name__ == "__main__":
    asyncio.run(test_thread_markdown_lifecycle())
