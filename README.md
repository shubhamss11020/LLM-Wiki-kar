# 🧠 Knowledge Base & LLM Wiki

A persistent, local-first LLM-maintained knowledge wiki and retrieval engine. It follows the three-layer operating pattern:

- **Raw Sources (`raw/`)**: Immutable source material and article clippings stored in `raw/Clippings/`.
- **Obsidian Wiki (`vault/`)**: Fully connected, agent-maintained Markdown notes in `vault/` with rich YAML frontmatter and bidirectional `[[wikilinks]]`.
- **Operating Schema (`AGENTS.md`)**: Strict provenance, ingest workflow, reciprocal linking, and lint maintenance rules.

The backend indexes existing wiki Markdown and persists metadata, semantic chunking, and relational graph links into **PostgreSQL** or local **SQLite**. The **Model Context Protocol (MCP)** server connects Claude Desktop directly to your local or cloud wiki with automated timestamped conversation logging in `vault/generated/`.

---

## 🌐 Live Deployed Endpoints

- **Live Backend API**: `https://llm-wiki-kar.onrender.com`
- **Interactive Swagger Documentation**: `https://llm-wiki-kar.onrender.com/docs`
- **Live Health & Partitions Status**: `https://llm-wiki-kar.onrender.com/health`

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

### ⚡ 1-Click Claude Desktop MCP Setup (Automated)

Anyone who clones this repository can configure Claude Desktop in **1 second with a single command** (works on Windows, macOS, and Linux):

```bash
python install_mcp.py
```

*This script automatically detects your OS, finds your `claude_desktop_config.json`, and installs all 3 live cloud-connected MCP partitions without any manual file editing.*

---

### 🛠️ Manual Configuration (Alternative)

If you prefer to configure Claude Desktop manually, open your `claude_desktop_config.json` and add:

```json
{
  "mcpServers": {
    "wiki-skincare-science": {
      "command": "python",
      "args": [
        "<PATH_TO_CLONED_REPO>/mcp-server/server.py"
      ],
      "env": {
        "BACKEND_API_URL": "https://llm-wiki-kar.onrender.com",
        "WIKI_API_KEY": "partition-1-skincare-key"
      }
    },
    "wiki-complexion-bases": {
      "command": "python",
      "args": [
        "<PATH_TO_CLONED_REPO>/mcp-server/server.py"
      ],
      "env": {
        "BACKEND_API_URL": "https://llm-wiki-kar.onrender.com",
        "WIKI_API_KEY": "partition-2-complexion-key"
      }
    },
    "wiki-eyes-lips-culture": {
      "command": "python",
      "args": [
        "<PATH_TO_CLONED_REPO>/mcp-server/server.py"
      ],
      "env": {
        "BACKEND_API_URL": "https://llm-wiki-kar.onrender.com",
        "WIKI_API_KEY": "partition-3-eyeslips-key"
      }
    }
  }
}
```

#### 🔒 Partition Access Policies:
- **`wiki-skincare-science` (Partition 1)**: Strictly restricted to 76 notes on chemical actives, dermatology science, and skin health. Cannot read foundations, lipsticks, or festive makeup.
- **`wiki-complexion-bases` (Partition 2)**: Strictly restricted to 89 notes on foundations, powders, highlighters, and shade matching. Cannot read pure skincare actives or eye/lip products.
- **`wiki-eyes-lips-culture` (Partition 3)**: Strictly restricted to 92 notes on lipsticks, kajal, waterproof climate survival kits, and festive looks.

4. **Restart Claude Desktop**. Claude Desktop will display the tool icon for each connector with strict data boundary enforcement!

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
