---
thread_id: "thr-154f8c67"
user: "shubh"
title: "Technical architecture — infrastructure, code structure, tec"
created: "2026-09-01T14:57:08.796284-04:00"
last_updated: "2026-09-01T14:57:08.796284-04:00"
turn_count: 1
---

# shubh — Technical architecture — infrastructure, code structure, tec — 2026-09-01

---

## Turn 1 — 14:57:08

**User:**
Technical architecture — infrastructure, code structure, tech stack, how AskCruz systems fit together?

**AI Response:**
Based on my investigation across the knowledge base—pulling the comprehensive self-knowledge document, development scorecards, and active work tracking—here's the AskCruz architecture at 10ft depth:

## Architecture Overview

AskCruz is a multi-tenant AI-powered knowledge platform that ingests fragmented company information (emails, calls, support tickets, implementation data) and serves it back through a conversational interface with access controls. The documented pipeline is:

**Ingestion → Filtering → Sensitivity Classification → Central Store → Knowledge Synthesis → Human Approval → Retrieval → Response**

---

## Verified Tech Stack

| Layer | Technology | Owner | Status |
|---|---|---|---|
| Database | PostgreSQL 10+ | Ayan Dutta (credentials holder) | Live / Hetzner VPS |
| Server | Node.js / Python backend | Build-out team | Live |
| Frontend | Cruz (React/TS codebase) | Jaskeerat Singh | Production pilot + 3GM in-flight |
| Hosting | Hetzner (primary) + DigitalOcean staging | Ayan Dutta | Live + staging active |
| Data sources | Gmail (3x), Zoho support, Fireflies calls, Fathom calls, Odoo implementation boards | Multiple | Live |
| Version control | GitLab | Ayan Dutta | Active |

**3GM-specific infrastructure:** Digital Ocean staging server stood up as of Aug 14, 2026; cost optimization work in progress.

---

## Current Data Ingestion

The system pulls from six sources but with an important boundary:

1. **Live ingestion:** Gmail, Zoho, Fireflies, Fathom
2. **Odoo boundary:** Support tickets and invoices remain in live Odoo for EOXS; for 3GM, this is client-configurable (can ingest or pull live depending on client's ERP reliability)
3. **Six-hour synthesis cycle:** Raw data → synthesized knowledge pages → human approval → published knowledge
4. **Data completeness:** Officially 94% (as of Aug 25, 2026)

---

## Access Tier Architecture

Three-tier permission model with database-level + AI response-level checks:

| Tier | Corresponds to | Visibility | Current access holders |
|---|---|---|---|
| tier1 | Raj-Personal | Raj only | Rajat Jain |
| tier2_confidential | Company-Confidential | Internal team only (financials, legal, salaries, employee performance stripped) | EOXS HR + Rajat |
| tier2 | General | Broad internal (amounts and performance metrics stripped) | General staff, MBA interns |

---

## Active Development (Real-time as of Aug 18, 2026)

**Frontend:**
- Jaskeerat Singh: 4 open tasks, low engagement this week (0 self-authored notes on own tasks). Access rights QA in progress.
- Recent completions: Frontend feature testing, email integration automation
- Known blocker: #26 "Front End Refinements" on hold (8 days idle)

**Backend / Ops:**
- Ayan Dutta: 31 open tasks across 5 boards, 22 self-stage-moves + 15 completions this week (high velocity, thin commenting)
- Nidhi Rana: Infrastructure & QA. Completed: full Postgres schema audit (30+ tables, access tier classification), MCP connector refinements (4 distinct identities built + QA'd), data migration to DigitalOcean staging
- Recent work:
  - [Aug 14] Staging server (DigitalOcean) moved to complete status
  - [Aug 17] Architecture audit finished; documented platform choices (Hetzner vs. DigitalOcean vs. alternatives)
  - [Aug 17] Clean-up of stale Claude/Codex sessions (2GB memory reclamation)
  - [Aug 18] AskCruz Integration for EOXS: flagged a skill-file schema gap, attached all relevant skill files for integration

**Flagged blockers from recent work:**
- #156: "Project Board Management" marked high-priority; zero activity this week (4.3 days idle)
- #94: "R&D: AskCruz Voice Call-In" (flagged); 11.8 days idle
- Email server setup (#31) moved to QA as of Aug 12
- Multiple "zero log notes ever" tasks sitting >7 days (access rights QA, calendar, mobile app, CRM AI architecture)

---

## 3GM Implementation Status

3GM Steel is the only external AskCruz client currently in production onboarding (mid-implementation as of Aug 25, 2026).

**What's live for 3GM:**
- Core platform deployed
- DigitalOcean staging environment stood up
- Skill/MCP integrations being tested
- Proposal completed and sent (Ron, Aug 17)

**What's pending:**
- Cost optimization (task #158: on hold)
- Full KT (knowledge transfer) to 3GM team (task #151: on hold)
- Email integration automation (completed Aug 17)
- Data migration to production (task #146: assigned, starts this week per Nidhi)

---

## Known Gaps & Risks

**Architecture-level:**
1. **Write capability is new.** First implementation just landed (task #97, Aug 14). SOP edit function through MCP now in production but likely under-tested at scale.
2. **Ingestion gaps documented:** Legacy file-based system dependencies were recently migrated to DB-based (Aug 14, task #90), but task #63 flagged that raw data manual ingestion has historical gaps.
3. **Latency identified:** Task #152 "Find the reason behind latency in Claude responses" is on hold; no root cause or fix documented yet.
4. **Isolated tier1 data.** Raj's personal tier1 pages are not discoverable via standard search—this is intentional but means that tier is genuinely walled off (no accidental exposure vector through queries).

**Operational:**
1. **Engagement thin on own work.** High-priority tasks have 0 self-authored notes; stage moves are happening but often by teammates, not assignees. This flags unclear ownership or blocking handoffs.
2. **Knowledge transfer incomplete.** Training materials for AskCruz backend promised by end of week (Aug 17 statement); orientation video module 1 posted (Aug 14) but full curriculum still in progress.
3. **Scope confusion between EOXS internal pilot and 3GM client.** Self-knowledge doc explicitly warns against treating EOXS's 8-client roster as AskCruz's deployment base—only 3GM is live, but the docs/emails sometimes blur this line.

---

## Code Structure (Inferred)

- **Frontend:** `cruz` codebase (React/TypeScript based on naming); hosted on Hetzner or DigitalOcean
- **Backend:** Python/Node.js server handling ingestion, classification, synthesis, retrieval
- **Database:** PostgreSQL with explicit `access_tier` column on every major table
- **Pipelines:** Automated raw ingestion (every 2 hours per docs, every 6 hours per synthesis cycle) + scheduled wiki promotion
- **Testing:** QA on access rights, ingestion automation, frontend features (detailed feedback from Priyanshu Sinha on Aug 13-14)
- **Deployment:** GitLab CI/CD implied; staging DigitalOcean, production Hetzner

---

## What's Not Documented Yet

The companion technical specs referenced in the self-knowledge document—`docs/backend-server.md`, `docs/postgres-database.md`, `docs/raw-ingestion.md`, `docs/wiki-ingestion.md`, `docs/linear-integration.md`, `docs/local-dev-and-team-onboarding.md`—are not in the searchable knowledge base, so deeper infrastructure details (exact API endpoints, schema, deployment scripts, secrets management) are behind that wall.

**Bottom line:** Architecture is real and live (not blueprint), but it's currently operationally stretched across ingestion gaps, incomplete handoffs, and unresolved latency issues. 3GM is onboarded but not yet stable for production workloads.

