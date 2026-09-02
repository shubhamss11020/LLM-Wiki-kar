---
thread_id: "thr-134b00d8"
user: "shubh"
title: "User: How do the Odoo implementation tasks for 3GM"
created: "2026-09-02T06:17:25.259319-04:00"
last_updated: "2026-09-02T06:17:25.259319-04:00"
turn_count: 1
---

# shubh — User: How do the Odoo implementation tasks for 3GM — 2026-09-02

---

## Turn 1 — 06:17:25

**User:**
User: How do the Odoo implementation tasks for 3GM Steel differ from traditional EOXS clients like Discount Pipe & Steel and Eastern States Steel? Why isn't AskCruz tracked as a standard client board in Odoo?

**AI Response:**
User: How do the Odoo implementation tasks for 3GM Steel differ from traditional EOXS clients like Discount Pipe & Steel and Eastern States Steel? Why isn't AskCruz tracked as a standard client board in Odoo?

Claude: I need to gather full context before responding. Let me read the relevant skills first, then ask clarifying questions.

[Skills read: eoxs-data-general, threads-ov]

[Clarifying questions asked about scope]

User: Scope: Are you evaluating whether AskCruz should have a standard client board in Odoo, or just understanding why it doesn't now?

Claude: You repeated my question back — let me clarify what I'm asking.

When you ask "Why isn't AskCruz tracked as a standard client board in Odoo?" — are you:

A) Just wanting to understand the current reason/rationale (this is how it's set up, here's why)
B) Evaluating whether it should be set up as a standard board (is the current approach a constraint we should fix, or intentional?)
C) Both — understand the current state AND whether it makes sense to change it

Which one?

User: A

Claude: The core structural difference:

3GM's implementation tasks are nearly 4 years stale. The board has 34 tasks created in April-May 2022 for the initial Odoo onboarding (discovery calls, kickoff sessions, product master setup). Most remain in "Sub Tasks," "Tasks," or "Completed" stages from that cycle. Recent 2026 activity appears only as ad-hoc bug fixes and feature requests, not tracked on the implementation board.

Discount Pipe & Steel and Eastern States Steel, by contrast, have active ongoing implementation tasks from 2025-2026. Discount Pipe shows continuous work (Requirement, Assigned, Completed stages with recent dates), while Eastern States has minimal activity (3 tasks total, mostly Completed from 2025-26).

Why the 3GM board looks different:

3GM was onboarded in 2022 using a now-outdated workflow. The implementation board captured the discovery and initial setup, then wasn't repurposed for ongoing client work. Current AskCruz development for 3GM isn't tracked here—it shows up in recent Fireflies calls ("3GM - AskCruz Proposal," Aug 12) and email threads, but the Odoo board remains frozen from 2022.

Why AskCruz has no standard client board:

AskCruz is not registered as a client in Odoo at all. It's EOXS's own product line, not a customer account. The 8 registered clients are all steel/metals customers (Sabre Alloys, Discount Pipe, Eastern States, PPC Metals, Greer Steel, Brannon, RW Conklin, and 3GM). AskCruz's development is tracked separately—in Ayan's Linear board, the Cruz codebase repository, and internal MCP connectors. 3GM is the first external pilot, but that's still managed through AskCruz's own infrastructure, not through 3GM's client implementation board.

The implementation boards in Odoo are designed for customer ERP onboarding (data migration, module setup, staff training). AskCruz is a standalone platform with its own deployment, access control, and data ingestion pipeline, so it doesn't fit that structure.

---

Source: eoxs-db — list_implementation_tasks for each client, get_client_profile for 3GM, list_contacts to confirm AskCruz absence from client registry.

