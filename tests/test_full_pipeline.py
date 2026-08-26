import os
import sys
import asyncio
import pytest

# Ensure repository root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app.config import settings
from backend.app.database.connection import init_db, AsyncSessionLocal
from backend.app.ingestion.indexer import run_incremental_ingestion
from backend.app.services.search import search_knowledge_base, get_file_details
from backend.app.services.records import save_generation_record, query_records_by_date

async def test_full_flow():
    print("\n--- 1. Initializing Database ---")
    await init_db()
    print("[PASS] DB initialized.")

    async with AsyncSessionLocal() as session:
        print("\n--- 2. Running Initial Ingestion ---")
        res1 = await run_incremental_ingestion(settings.VAULT_PATH, session)
        print(f"[PASS] Ingestion run 1: Scanned={res1['total_scanned']}, Indexed={res1['indexed']}, Skipped={res1['skipped']}")
        assert res1["total_scanned"] >= 200, f"Expected >= 200 files scanned, got {res1['total_scanned']}"

        print("\n--- 3. Testing Incremental Skip (Zero Re-indexing) ---")
        res2 = await run_incremental_ingestion(settings.VAULT_PATH, session)
        print(f"[PASS] Ingestion run 2: Scanned={res2['total_scanned']}, Indexed={res2['indexed']}, Skipped={res2['skipped']}")
        assert res2["indexed"] == 0, "Unchanged files should not be re-indexed!"
        assert res2["skipped"] == res1["total_scanned"], "All files should be skipped via SHA-256 matching!"

        print("\n--- 4. Testing Multi-Layered Search ---")
        search_results = await search_knowledge_base("niacinamide", session, limit=3)
        print(f"[PASS] Search for 'niacinamide' returned {len(search_results)} result(s):")
        for r in search_results:
            print(f"  - [{r['score']}] {r['file_name']} -> {r['title']}")
        assert len(search_results) > 0, "Search should return matching notes"

        print("\n--- 5. Testing Note Details and Outgoing Wikilinks ---")
        note_details = await get_file_details("Vitamin C.md", session)
        assert note_details is not None, "Note details should be found"
        print(f"[PASS] Retrieved '{note_details['title']}' with {len(note_details['chunks'])} chunk(s) and links: {note_details['outgoing_wikilinks']}")

        print("\n--- 6. Testing Claude Generation Record (.md + DB) ---")
        gen_res = await save_generation_record(
            prompt="Explain how to layer Vitamin C and Niacinamide in monsoon humidity.",
            response="Apply Vitamin C first in the morning under SPF for antioxidant defense, followed by Niacinamide to balance sebum and support the lipid barrier.",
            topics=["skincare", "layering", "monsoon"],
            source_files=["Vitamin C vs Niacinamide", "Vitamin C", "Niacinamide"],
            vault_path=settings.VAULT_PATH,
            session=session
        )
        print(f"[PASS] Generation saved: Record ID='{gen_res['record_id']}', File='{gen_res['file_name']}'")
        assert os.path.exists(gen_res["file_path"]), "Generated Markdown file must exist on disk!"

        print("\n--- 7. Querying Historical Records by Date ---")
        records = await query_records_by_date(topic="skincare", session=session)
        print(f"[PASS] Query records returned {len(records)} record(s). Latest ID: {records[0]['record_id']}")
        assert len(records) > 0, "Saved generation record must be queryable!"

        print("\n--- 8. Testing 3-Tier Partition Access Rights (RBAC) ---")
        # Partition 1 (Skincare) querying Foundation Formulations
        p1_leak = await get_file_details("Foundation Formulations.md", session, allowed_partitions=[1])
        assert p1_leak is None, "Partition 1 MUST NOT have access to Partition 2 Foundation Formulations!"
        
        # Partition 2 (Complexion) querying Foundation Formulations
        p2_access = await get_file_details("Foundation Formulations.md", session, allowed_partitions=[2])
        assert p2_access is not None, "Partition 2 MUST have access to Foundation Formulations!"

        # Partition 3 (Eyes/Lips) querying Lipstick
        p3_access = await get_file_details("Lipstick Formulations.md", session, allowed_partitions=[3])
        assert p3_access is not None, "Partition 3 MUST have access to Lipstick Formulations!"

        print("[PASS] Strict 3-Partition isolation verified successfully.")

    print("\n========================================================")
    print("ALL PIPELINE TESTS PASSED SUCCESSFULLY!")
    print("========================================================")

if __name__ == "__main__":
    asyncio.run(test_full_flow())
