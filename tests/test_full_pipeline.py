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

        print("\n--- 8. Testing Hierarchical Tier Segregation (RBAC) ---")
        # MCP 1: Full Access (Tiers 1, 2, 3)
        mcp1_t1 = await get_file_details("Vitamin C.md", session, allowed_partitions=[1, 2, 3])
        mcp1_t2 = await get_file_details("Foundation Formulations.md", session, allowed_partitions=[1, 2, 3])
        mcp1_t3 = await get_file_details("Lipstick Formulations.md", session, allowed_partitions=[1, 2, 3])
        assert mcp1_t1 is not None, "MCP 1 MUST have access to Tier 1 notes!"
        assert mcp1_t2 is not None, "MCP 1 MUST have access to Tier 2 notes!"
        assert mcp1_t3 is not None, "MCP 1 MUST have access to Tier 3 notes!"
        print("[PASS] MCP 1 has verified full access to Tier 1, Tier 2, and Tier 3 data.")
        
        # MCP 2: Segregated Access (Tiers 2 & 3 only)
        mcp2_t1 = await get_file_details("Vitamin C.md", session, allowed_partitions=[2, 3])
        mcp2_t2 = await get_file_details("Foundation Formulations.md", session, allowed_partitions=[2, 3])
        mcp2_t3 = await get_file_details("Lipstick Formulations.md", session, allowed_partitions=[2, 3])
        assert mcp2_t1 is None, "MCP 2 MUST NOT have access to Tier 1 notes!"
        assert mcp2_t2 is not None, "MCP 2 MUST have access to Tier 2 notes!"
        assert mcp2_t3 is not None, "MCP 2 MUST have access to Tier 3 notes!"
        print("[PASS] MCP 2 has verified access to Tier 2 & 3, and is blocked from Tier 1.")

        # MCP 3: Restricted Access (Tier 3 only)
        mcp3_t1 = await get_file_details("Vitamin C.md", session, allowed_partitions=[3])
        mcp3_t2 = await get_file_details("Foundation Formulations.md", session, allowed_partitions=[3])
        mcp3_t3 = await get_file_details("Lipstick Formulations.md", session, allowed_partitions=[3])
        assert mcp3_t1 is None, "MCP 3 MUST NOT have access to Tier 1 notes!"
        assert mcp3_t2 is None, "MCP 3 MUST NOT have access to Tier 2 notes!"
        assert mcp3_t3 is not None, "MCP 3 MUST have access to Tier 3 notes!"
        print("[PASS] MCP 3 has verified access to Tier 3 only, and is blocked from Tier 1 & 2.")

    print("\n========================================================")
    print("ALL PIPELINE TESTS PASSED SUCCESSFULLY!")
    print("========================================================")

if __name__ == "__main__":
    asyncio.run(test_full_flow())
