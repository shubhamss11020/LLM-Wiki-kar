---
thread_id: "thr-local"
user: "shubh"
title: "["
created: "2026-09-01T13:15:22.225563-04:00"
last_updated: "2026-09-01T13:15:22.225563-04:00"
turn_count: 1
---

# shubh — [ — 2026-09-01

---

## Turn 1 — 13:15:22

**User:**
Tell me About ask cruz and their project basically in detail

[Rigor/scope picks]
Q: How deep should I go? A: 10ft â€” verified
Q: What do you mean by "their project"? A: AskCruz the product itself

**AI Response:**
Routing note: this query maps to eoxs-data-general (AskCruz data lives in the EOXS connectors). threads-ov applies only for transcript saving. No ambiguity beyond that.

Two things before I dig in.
[ask_user_input_v0 â€” Q1: How deep should I go? Options: 5ft quick pass / 10ft verified / 50ft deep + blind spots / 100ft staged sections. Q2: What do you mean by "their project"? Options: AskCruz the product itself / A specific client project on AskCruz / AskCruz as an internal EOXS build / Everything â€” you decide scope]

---

AskCruz â€” product overview (verified against source assets, not just wiki summaries)

What it is

AskCruz is EOXS's AI company knowledge platform â€” a "second brain" that ingests scattered business data, structures it into a cited knowledge layer, and exposes it through a conversational interface. Product family codename Cruz (internal only; canonical name is AskCruz). Self-knowledge doc v1.2, product baseline v1.0, last updated 25 Aug 2026.

One-line definition from the canonical PMF doc: an industry-agnostic AI agent that connects a company's scattered business data, structures it into usable organizational knowledge, and lets employees access it through a single conversational interface.

Two framings of the same product

| Audience | Model |
|---|---|
| Pitch / non-technical | Four pillars: Company Brain, Company Hands, Digital Workforce, Company Personalization |
| Technical / onboarding | Capability categories: Email, Calls & Meetings, Client/Implementation Data, Employee Info, Internal Knowledge, Operational Records |

Company Brain = ask the business a question. Company Hands = draft a quote, flag at-risk orders, summarize a call. Digital Workforce = standing watch on a condition. Company Personalization = the company's own vocabulary, pricing logic, tolerances.

Architecture

Ten-stage pipeline: Source Systems â†’ Ingestion â†’ Filtering â†’ Sensitivity Classification â†’ Central Knowledge Store â†’ Knowledge Generation â†’ Citation Check â†’ Human Approval â†’ Retrieval â†’ Response.

Sources currently wired: 3 Gmail accounts, 1 shared Zoho support inbox, Fireflies, Fathom, and client Odoo implementation boards for six EOXS clients. Synthesis cycle runs every 6 hours. Support tickets and invoices sit outside the vault for EOXS and are pulled live from Odoo â€” that's a per-client configurable choice, not a product limit.

Access model: tier1 (Raj-personal), tier2_confidential (company-confidential), tier2 (general). Two layers â€” DB-level authorization plus an independent AI response-level check.

Commercial state

- One external client: 3GM Steel, mid-implementation. Deal confirmed 19 Aug at reduced 2-user scope; Rajat agreed to a shorter initial term on 20 Aug.
- Six-week implementation timeline is 3GM-specific, not a productized standard.
- Pipeline touched but not verified as staged: Sabre Alloys (joint proposal call), Three D Metals, a legal-services prospect (virtualilegal.com), plus a recruit pitch to Steve Leebow tied to a 100-client goal.
- Not established anywhere in the docs: pricing, ACV, sales-cycle length, CAC, retention, ROI, usage metrics. The PMF doc lists these explicitly as evidence gaps.

Three things worth your attention

1. The 3GM deal decided to run Company Brain on Claude, not the AskCruz front end, as the client-facing interface (Ron's 17 Aug reply). If that holds, your first paying customer isn't validating your product surface â€” it's validating your ingestion layer plus someone else's UI. That changes what you're actually selling and what a second customer inherits.

2. Positioning contradiction is resolved on paper, stale in the wiki. The feature file v1.1 corrected steel-specific â†’ industry-agnostic. The wiki overview page still carries a contradiction flag from before that correction. Sales material built off the older framing will misprice your market.

3. Revenue infrastructure is blocked. Delaware C-Corp registered but no EIN; SVB account blocked on the same EIN; Wise and Mercury also require it. Gated entirely on Logan, no response as of 26 Aug. Against a $1M ARR target, not being able to bank money is not a back-office item.

Sources: eoxs-db assets askcruz-self-knowledge, askcruz-product-feature-file, askcruz-product-market-fit (raw source docs, not wiki summaries); wiki pages "AskCruz â€” System Architecture, Ingestion & Access Control", "AskCruz â€” Product Capabilitiesâ€¦", "AskCruz â€” Market Positioning, ICP & PMF Status", "3GM Steel â€” AskCruz Proposal Call (Aug 2026)", "AskCruz Internal Task Board â€” Ron's Open-Task Snapshot (Aug 29, 2026)". Product docs are frozen at 25 Aug; deal and board pages run to 28â€“29 Aug. Monetary figures are not visible on this connection.
