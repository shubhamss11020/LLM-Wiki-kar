# 🧠 Knowledge Base & LLM Wiki

A persistent, local-first LLM-maintained knowledge wiki and retrieval engine. It follows the three-layer operating pattern:

- **Raw Sources (`raw/`)**: Immutable source material and article clippings stored in `raw/Clippings/`.
- **Obsidian Wiki (`vault/`)**: Fully connected, agent-maintained Markdown notes in `vault/` with rich YAML frontmatter and bidirectional `[[wikilinks]]`.
- **Operating Schema (`AGENTS.md`)**: Strict provenance, ingest workflow, reciprocal linking, and lint maintenance rules.

The backend indexes existing wiki Markdown and persists metadata, semantic chunking, and relational graph links into **PostgreSQL** or local **SQLite**. The **Model Context Protocol (MCP)** server connects Claude Desktop directly to your local wiki with automated timestamped conversation logging in `vault/generated/`.

---

## 📁 Repository Layout

```text
llm-wiki/
├── AGENTS.md                           # Wiki operating schema & provenance rules
├── README.md                           # Repository documentation
├── docker-compose.yml                  # PostgreSQL (pgvector/pg16) container
│
├── raw/                                # 📂 Immutable Source Documents
│   ├── README.md                       # Source collection guidelines
│   └── Clippings/                      # 210+ Markdown source articles & web clippings
│
├── vault/                              # 💎 Obsidian Vault (Source of Truth)
│   ├── index.md                        # Master navigation catalog & index
│   ├── log.md                          # Append-only operational history & ingest log
│   ├── Actives/                        # 12 core actives & mechanisms (Vitamin C, Niacinamide, Kojic Acid, etc.)
│   ├── Formulations/                   # 6 formulation notes (Foundations, Lipsticks, Kajal, Powders, etc.)
│   ├── Guides/                         # 4 technique & cultural guides (Monsoon, Starter Kits, Undertones, Festive)
│   ├── Comparisons/                    # 5 comparative analyses (Vitamin C vs Niacinamide, Retinol vs Bakuchiol, etc.)
│   ├── Entities/                       # Brand profiles & formulation ethos (SUGAR Cosmetics)
│   ├── Authors/                        # 18 contributor & editor profile hubs (Jasmin Gohil, Shreya Nambiar, etc.)
│   ├── Sources/                        # 210+ dedicated source manifests with provenance links
│   └── generated/                      # 🕒 Timestamped Claude interaction logs (YYYY/MM/DD)
│
├── backend/                            # 🚀 FastAPI Backend & Ingestion Engine
│   ├── app/
│   │   ├── main.py                     # API router & endpoints
│   │   ├── config.py                   # App configuration & environment settings
│   │   ├── database/                   # SQLAlchemy async engine, connection & models
│   │   ├── ingestion/                  # Vault scanner, YAML parser, heading chunker & indexer
│   │   └── services/                   # Multi-layer search, graph relationships & generation records
│   └── requirements.txt
│
├── mcp-server/                         # 🔌 Model Context Protocol (MCP) Server
│   ├── server.py                       # Python stdio JSON-RPC MCP server
│   ├── requirements.txt
│   └── claude_desktop_config.json.example
│
└── tests/
    └── test_full_pipeline.py           # End-to-end pipeline test suite
```

---

## 🗄️ Database Setup: Choose Your Approach

This project supports two database backends out of the box:

### Approach A: PostgreSQL with pgvector via Docker (Full Setup)
Use this approach if you want containerized PostgreSQL with vector extensions enabled:
1. Start the container:
   ```bash
   docker compose up -d
   ```
2. The database runs on `localhost:5432` with user `wiki_user`, password `wiki_password`, and database `llm_wiki`.
3. The FastAPI backend connects to PostgreSQL automatically via `DATABASE_URL`.

### Approach B: Local SQLite (Zero-Setup / No Docker Required)
Use this approach for lightweight, instant local development without installing or running Docker:
1. Simply do **not** run Docker.
2. The backend detects when PostgreSQL is unavailable and **automatically falls back to local SQLite** (`./llm_wiki.db`).
3. (Optional) Force SQLite explicitly via environment variable:
   ```bash
   # Windows PowerShell:
   $env:DATABASE_URL="sqlite+aiosqlite:///./llm_wiki.db"

   # Linux / macOS:
   export DATABASE_URL="sqlite+aiosqlite:///./llm_wiki.db"
   ```

---

## ⚡ Quickstart Guide

### 1. Install Dependencies & Start the Backend

1. Install backend requirements:
   ```bash
   pip install -r backend/requirements.txt
   ```
2. Start the FastAPI server:
   ```bash
   python -m uvicorn backend.app.main:app --reload --port 8000
   ```
3. Trigger initial vault ingestion to index all notes:
   ```bash
   # Windows PowerShell:
   Invoke-RestMethod -Method Post -Uri http://localhost:8000/api/ingest

   # Linux / macOS:
   curl -X POST http://localhost:8000/api/ingest
   ```

- **Interactive API Docs (Swagger UI)**: `http://localhost:8000/docs`
- **Health Check**: `http://localhost:8000/health`
- **Search Endpoint**: `POST http://localhost:8000/api/search`

---

### 2. Connect Claude Desktop via MCP

1. Install MCP dependencies:
   ```bash
   pip install -r mcp-server/requirements.txt
   ```
2. Open your Claude Desktop configuration file:
   - **Windows:** `%APPDATA%\Claude\claude_desktop_config.json`
   - **macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`
   - **Linux:** `~/.config/Claude/claude_desktop_config.json`
3. Add the `knowledge-wiki` server entry, replacing `<ABSOLUTE_PATH_TO_REPO>` with the absolute path to where you cloned this repository:

```json
{
  "mcpServers": {
    "knowledge-wiki": {
      "command": "python",
      "args": [
        "<ABSOLUTE_PATH_TO_REPO>/mcp-server/server.py"
      ],
      "env": {
        "BACKEND_API_URL": "http://localhost:8000"
      }
    }
  }
}
```

> **Path Formatting Examples:**
> - **Windows:** `"C:\\Projects\\llm-wiki\\mcp-server\\server.py"` (use double backslashes `\\` or forward slashes `/`)
> - **macOS / Linux:** `"/Users/username/Projects/llm-wiki/mcp-server/server.py"`

4. **Restart Claude Desktop**.

Claude Desktop will display the tool icon with 5 available tools:
- `search_wiki(query, category, limit)`: Semantic concept and keyword search across 250+ notes.
- `get_file(file_name)`: Retrieve full Markdown content, headings, and backlinks for any note.
- `save_generation(prompt, response, topics, source_files)`: Persist interaction into `vault/generated/` and database.
- `get_records_by_date(start_date, end_date, topic)`: Query historical conversation logs.
- `refresh_vault()`: Trigger incremental scan and re-indexing of the vault.

---

### 3. Explore in Obsidian

1. Open **Obsidian**.
2. Click **"Open folder as vault"**.
3. Select the `vault/` directory from this repository.
4. Press `Ctrl + G` (or `Cmd + G` on Mac) to open the **Graph View** to explore the fully connected knowledge graph.

---

## 🧪 Running Tests

Run the full end-to-end pipeline test suite:
```bash
python tests/test_full_pipeline.py
```
*(Tests database initialization with SQLite fallback, 250+ note indexing, search, note detail retrieval, and generation record persistence).*
