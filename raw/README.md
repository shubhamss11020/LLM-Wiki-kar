# Raw Sources Collection

This directory holds the immutable source inputs from which the Obsidian wiki (`vault/`) is maintained.

## Structure
- `raw/Clippings/`: Contains 210+ Markdown source articles, editorial clippings, and primary web exports.

## Ingest Rules (per AGENTS.md)
1. Store original, unmodified source files and article exports in `raw/Clippings/`.
2. Never edit or overwrite an existing source after adding it. If an updated or corrected version emerges, add it as a distinct file.
3. Every page created in `vault/` derived from a source must cite that source's relative path (e.g. `raw/Clippings/<filename>.md`) in its `source_refs` frontmatter.
4. Run `POST /api/ingest` only after the wiki Markdown files and navigation index in `vault/` have been generated and cross-linked.
