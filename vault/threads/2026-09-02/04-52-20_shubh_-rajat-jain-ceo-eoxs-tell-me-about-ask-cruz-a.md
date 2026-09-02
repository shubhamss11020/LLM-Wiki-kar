---
thread_id: "thr-c0ca24e0"
user: "shubh"
title: "## Rajat Jain (CEO, EOXS): Tell me About ask cruz and their "
created: "2026-09-02T04:52:20.056394-04:00"
last_updated: "2026-09-02T04:52:20.056394-04:00"
turn_count: 1
---

# shubh — ## Rajat Jain (CEO, EOXS): Tell me About ask cruz and their  — 2026-09-02

---

## Turn 1 — 04:52:20

**User:**
## Rajat Jain (CEO, EOXS): Tell me About ask cruz and their project basically in detail

**AI Response:**
## Rajat Jain (CEO, EOXS): Tell me About ask cruz and their project basically in detail

I want a 10ft deep analysis — verified against underlying records, not summary fields, and cross-checked where available.

## Claude Response: AskCruz 10ft Deep Breakdown

(Performed skill reads on threads-ov and eoxs-data-general, then queried EOXS data to verify memory claims.)

### AskCruz Overview

AskCruz is EOXS's internal AI-powered company knowledge platform—a conversational "second brain" that ingests scattered business data (emails, calls, support tickets, implementation records) and surfaces synthesized, cited knowledge through a Claude-backed interface. The strategic goal is $1M ARR within 12 months. As of late August 2026, it's live in production for internal EOXS use and mid-implementation with one paying customer: 3GM Steel.

### Core Architecture & Data Status

**Pipeline:** 10-stage flow: Source Systems → Ingestion → Filtering → Sensitivity Classification → Central Store → Knowledge Generation → Citation Check → Human Approval → Retrieval → Response.

**Data Sources (verified as of Aug 25):**
- Gmail: 3 individual accounts
- Zoho: Shared support inbox
- Fireflies + Fathom: Business calls
- Odoo: 6 configured client instances (Greer Steel, Eastern States Steel, Discount Pipe & Steel, PPC Metals, 3GM Steel, Sabre Alloys) plus 2 email-only clients (RW Conklin, Brannon Steel)

**Technical Stack:**
- Backend: Node.js/Python
- Frontend: React/TypeScript (owned by Jaskeerat Singh)
- Database: PostgreSQL 10+ on Hetzner VPS (primary) + DigitalOcean staging
- Ingestion cycle: 2-hour raw ingestion + 6-hour synthesis
- Version control: GitLab (managed by Ayan Dutta)

**Data Completeness:** 94% as of Aug 25 (per existing notes; latest wiki verification shows this is tracked but no fresher number available in current queries).

### 3GM Steel Implementation (Current Deal Status)

**Proposal Timeline (Verified from Aug 28 wiki):**
- Aug 12: Rajat pitched AskCruz as upsell to Travis Lane (3GM CCO). Proposal had pricing inconsistencies.
- Aug 14-17: Pricing issues discovered and corrected. Ron sent revised proposal and addressed 5 open items Travis raised.
- Aug 19: Travis confirmed 3GM is moving forward—but at reduced scope (2-user vs. full proposal) and requesting shorter initial contract term.
- Aug 20: Rajat agreed to shorten the initial term.

**Current Blockers (as of Aug 29 task snapshot):**
- EIN for company registration: Blocked awaiting response from Logan (followed up Aug 26, no response yet)
- Bank account (SVB, or Wise/Mercury alternatives): All require EIN—no workaround available
- Kickoff logistics: Payment details and kickoff date pending finalization (flagged as "to be finalized," not confirmed done)

**Operational Gap:** Ron's task snapshot (Aug 29) shows none of the 11 open AskCruz tasks have deadlines set. Weekly board report task is waiting on Rajat to confirm KPIs and Monday scheduling for calls with Sheenam and Yashvir Singh Thakur.

### Development Team & Operational Status

**Team Ownership (as of Aug 25, flagged as unverified but sourced from internal architecture doc):**
- Ayan Dutta: Backend, ops, infrastructure, GitLab
- Jaskeerat Singh: Frontend (Cruz codebase)
- Nidhi Rana: Infrastructure & QA
- Ron: Sales/business development (11 open tasks as of Aug 29)

**Known Active Issues (from Aug 1 snapshot—current status unverified):**
- Task #156 "Project Board Management" flagged high-priority, zero activity
- Task #94 "AskCruz Voice Call-In" flagged, 11.8 days idle
- Task #152 "Latency in Claude responses" on hold, no root cause documented
- Write capability (deployed Aug 14) under-tested at scale
- Knowledge transfer to team incomplete (promised end of week as of Aug 17)

### Product Positioning & Market

**Capability Framing (Client-facing):**
- Email information (Gmail, Zoho)
- Call & meeting data (Fireflies, Fathom)
- Client/implementation data (Odoo)
- Employee information (directory)
- Internal knowledge & documents (SOPs, policies, reference docs)
- Cross-source knowledge synthesis

**Positioning Contradiction (Flagged in Aug 25 wiki):**
The product feature file frames AskCruz as "a company-specific AI product for steel businesses," but the product-market-fit guide explicitly positions it as "industry-agnostic—designed for any industry." The client-facing capability catalog uses industry-neutral language. These cannot all be the current canonical positioning simultaneously—needs confirmation on which is authoritative before external-facing use.

**Other Clients/Prospects (from wiki mentions):**
- Sabre Alloys: Joint proposal call scheduled (mid-Aug)
- Three D Metals: Cold outreach underway
- Legal firm (Sarah, virtualilegal.com): Being explored for legal-services segment (distinct from steel focus)

### Red Flags & Risks

1. **Company formation stalled:** AskCruz can't open a bank account or process payments without an EIN. Logan hasn't responded since Aug 26. This blocks final kickoff with 3GM and any cash flow.

2. **3GM deal unfinalized:** Despite Travis's "confirmed" statement, core logistics (payment method, exact kickoff date) remain pending. "Shorter initial term" was agreed to by Rajat but actual terms not visible in the data.

3. **No task deadlines:** 11 open AskCruz tasks have no deadline dates set. This suggests loose execution rigor and makes it hard to track critical-path items.

4. **Task ownership unclear:** Ron's snapshot shows most activity is chatter (conversations) rather than clear stage-change ownership. The weekly board report task is awaiting Rajat's input on KPIs—a leadership input gap.

5. **Positioning confusion:** Steel vs. industry-agnostic framing creates risk of misaligned sales messaging, especially as you expand beyond 3GM to legal/other verticals.

6. **Infrastructure credentials:** Ayan holds database/GitLab credentials, Nidhi holds Linear credentials. Single-person dependencies create operational risk if either is unavailable.

7. **Latency issue unresolved:** Task #152 "Latency in Claude responses" has been on hold with no documented root cause. This could be a user-facing performance problem.

### Key Unknowns & Data Limits

- **Development velocity:** Task counts from Aug 18 snapshot (31 open tasks, 22 self-stage-moves, 15 completions that week). Current status as of Sept 2 is unverified.
- **3GM payment terms:** Deal confirmed, scope narrowed to 2-user, term shortened—but exact pricing, payment schedule, and contract start date not visible.
- **Write capability scale testing:** Deployed Aug 14 but marked "new/under-tested at scale." No post-deployment incident data available.
- **Ingestion gaps:** Legacy file-based system recently migrated to DB; manual gaps flagged but not quantified.
- **Latency root cause:** No diagnostic work documented.

All data sourced from EOXS second brain (emails, calls, wiki synthesis) as of Aug 25–29. No direct confirmation of status changes between Aug 29 and Sept 2.

### Closing

What's your most urgent priority here—getting 3GM fully launched, unblocking the EIN/banking issue, or tightening execution rigor (deadlines, task clarity, ownership)?

