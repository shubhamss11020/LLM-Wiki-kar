# LLM Wiki Operating Schema

This repository is a local-first LLM-maintained knowledge base about Andrej
Karpathy's LLM material and the primary sources it references.

## Directory roles

- `raw/` is the immutable source collection. Store transcripts, notebooks,
  papers, article exports, and source manifests here. Never rewrite a source;
  add a corrected or newer source as a separate file.
- `vault/` is the maintained Obsidian wiki. The agent may create and revise
  pages here, but must preserve provenance.
- `vault/index.md` is the content-oriented navigation catalogue.
- `vault/log.md` is the append-only record of ingests, material edits, and
  lint passes.
- `vault/generated/` contains conversation-derived notes. It is not an input
  source and is excluded from the search index by design.

## Source ingest workflow

When asked to ingest a source:

1. Put the original file, export, or a source manifest in `raw/`. Do not alter
   its contents after it is added.
2. Read the source and identify the claims, entities, techniques, evidence,
   and disagreements with existing wiki pages.
3. Create or update the relevant pages in `vault/`. Every claim derived from a
   source must include that source's repository-relative path in
   `source_refs` frontmatter.
4. Update `vault/index.md` for new or materially changed pages and append one
   dated entry to `vault/log.md` using `## [YYYY-MM-DD] ingest | <title>`.
5. Run the backend's `/api/ingest` only after the wiki files are correct. That
   endpoint indexes wiki Markdown; it does not synthesize raw sources.

## Wiki conventions

- Use one durable concept, entity, comparison, or source summary per page.
- Keep YAML frontmatter with `id`, `title`, `category`, `tags`, `source_refs`,
  and `related`.
- Use `[[wikilinks]]` for relationships. Add reciprocal links where useful.
- Mark uncertainty and contradictions explicitly; never overwrite a disputed
  claim without retaining the provenance of both positions.
- Do not add a source reference that was not actually consulted.

## Maintenance workflow

Periodically lint the vault for broken links, orphan pages, stale statements,
missing provenance, duplicate concepts, and contradictions. Record material
lint findings and fixes in `vault/log.md`.
