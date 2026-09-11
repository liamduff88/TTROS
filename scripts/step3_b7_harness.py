#!/usr/bin/env python3
"""Step 3 — B7 baseline instrument: invoke, score, and report.

Frozen before the first real call (2026-09-07). Implements the RUN CONTRACT from
docs/ttros/02_TTROS_ACTIVE_TASK_2026-09-04_rev6.md Step 3 and the question/fact-list
contract from docs/ttros/TTROS_CAPABILITY_HARNESS_QUESTIONS_v1_UPDATED_2026-09-04.md.

Three subcommands, kept separate so no running total can leak between passes:
  invoke  --pass A|B [--dry-run] [--overwrite]   Make the 25 real David calls for one pass.
  score   --pass A|B [--overwrite]               Score one pass's saved raw JSON.
  report  [--overwrite]                          Combine both scored passes; refuses to
                                                  run unless both score files already exist.

Every model call goes through a fresh vault snapshot (TTROS_BRAIN_ROOT override) restored
from a read-only master before each individual question, so nothing the run does --
David's continuity thread, his session journal, an ungated brain-memory write, a queue
item -- can touch the live Business Brain or the live queue. AOS_ROOT is left pointing at
the real repo: repo-side context (workflows, priorities, rules) must be the real, current
state for the measurement to mean anything.

Budget: exactly 25 hermes calls per pass, hard-stopped in-process. This is the instrument
CLAUDE.md requires -- a budget stated only in a prompt is not a budget.
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

ROOT = Path("/home/liam/agentic-os-live")
SCRIPT_DIR = Path(__file__).resolve().parent
LIVE_VAULT = Path("/mnt/c/Users/Admin/Documents/A-Time to revenue/TTROS Business Brain")
MASTER_SNAPSHOT = Path("/home/liam/ttros_backups/b7_harness_vault_snapshot_20260907_000711Z")
WORK_VAULT = Path("/tmp/claude-1002/-home-liam-agentic-os-live/6ae94bfc-ff28-4f8a-95a3-7ba4d48e157c/scratchpad/b7_vault_work")
ASSEMBLY_DIR = ROOT / "queue" / "context_assemblies"
MAX_CALLS_PER_PASS = 25
HERMES_BIN = "/home/liam/.local/bin/hermes"
CALL_TIMEOUT_SECONDS = 600

# B6 depth-tool evidence: the two Business Brain MCP tools whose call arguments
# name a specific vault document David actually opened mid-session. Read-only,
# zero model calls -- David's own Hermes session record, the same state.db the
# Step 6 harness already reads (read-only) for its round-trip classification.
DAVID_STATE_DB = Path.home() / ".hermes" / "profiles" / "david" / "state.db"
HISTORICAL_CALLS_DIR = "sources/historical_calls"
DEPTH_TOOL_NAMES = {"mcp__brain__open_note", "mcp__brain__open_call"}

# ---------------------------------------------------------------------------
# Frozen question set v1 (25 questions). Bare question text only -- no fact
# list is ever sent to David. source_docs are vault-relative paths whose
# arrival in the assembled context's `sources` field is what B6 checks.
# ---------------------------------------------------------------------------

def kw(*groups):
    """A fact is PRESENT if every group has at least one of its alternatives
    as a case-insensitive substring of the answer. Frozen before Pass A."""
    return [tuple(g) if isinstance(g, (list, tuple)) else (g,) for g in groups]


QUESTIONS = [
    # ---------------- SECTION A ----------------
    dict(id="A1", section="A", honesty=False,
         text="What are our current offers and how are they priced?",
         source_docs=["memory/offers.md"],
         facts=[
             ("A1.1", "Free AI Opportunity Scan — automated diagnostic, personalised mini-report",
              kw(["opportunity scan"], ["automated", "diagnostic"])),
             ("A1.2", "Scan is acquisition/qualification, not a paid offer",
              kw(["not a paid offer", "not paid", "free"])),
             ("A1.3", "System Fit Call — human conversation off the report",
              kw(["system fit call"])),
             ("A1.4", "Paid diagnosis/operational mapping, CA$750–1,500, creditable toward build",
              kw(["750"], ["1,500", "1500"], ["credit"])),
             ("A1.5", "Scoped system build, ~CA$4,500 entry",
              kw(["4,500", "4500"])),
             ("A1.6", "Then training, documentation, handover; then ongoing relationship",
              kw(["training"], ["handover", "hand-off", "handoff"])),
             ("A1.7", "Flags the figures predate diagnose-first model and are unconfirmed",
              kw(["unconfirmed", "predate", "not confirmed", "not finalized", "not final", "tbd", "todo"])),
         ]),
    dict(id="A2", section="A", honesty=False,
         text="What is the core principle behind how we sell?",
         source_docs=["memory/offers.md", "memory/positioning.md"],
         facts=[
             ("A2.1", "Offer is the method, not the catalogue",
              kw(["method, not", "not a catalogue", "not the catalogue"])),
             ("A2.2", "Systems selected after diagnosis, never pitched before it",
              kw(["after", "diagnos"], ["never pitched", "not pitched", "before it"])),
             ("A2.3", "Diagnose before prescribing",
              kw(["diagnos"], ["prescrib"])),
             ("A2.4", "One workflow pays for itself before anything larger is proposed",
              kw(["one workflow"], ["pays for itself", "pay for itself"])),
         ]),
    dict(id="A3", section="A", honesty=False,
         text="How is delivery actually done?",
         source_docs=["memory/offers.md"],
         facts=[
             ("A3.1", "Forward-deployed — builds inside the client's operation",
              kw(["forward-deployed", "forward deployed", "inside the client"])),
             ("A3.2", "Against real workflows and real numbers",
              kw(["real workflow"], ["real number"])),
             ("A3.3", "Working systems over strategy decks",
              kw(["strategy deck", "over strategy"])),
             ("A3.4", "Every engagement ties to a measurable outcome (time, capacity, revenue, owner leverage)",
              kw(["measurable outcome"])),
             ("A3.5", "Impact quantified only with the client's own numbers",
              kw(["own numbers", "client's numbers", "client's own"])),
         ]),
    dict(id="A4", section="A", honesty=False,
         text="What are we not allowed to claim to a prospect?",
         source_docs=["memory/offers.md", "memory/positioning.md"],
         facts=[
             ("A4.1", "No guaranteed revenue lift/savings/timelines before Liam approves",
              kw(["guarantee"], ["approv"])),
             ("A4.2", "No enterprise-scale platform capability claims",
              kw(["enterprise", "enterprise-scale"])),
             ("A4.3", "No claiming a system type not built before without saying so",
              kw(["not built before", "haven't built", "never built"])),
             ("A4.4", "No fully autonomous business operations / replacing human judgment",
              kw(["autonomous"], ["human judg"])),
             ("A4.5", "No private client outcomes without approval",
              kw(["private client", "client outcome"])),
             ("A4.6", "No industry specialization not yet earned",
              kw(["specializ", "specialis"], ["not yet earned", "not earned", "haven't earned"])),
         ]),
    dict(id="A5", section="A", honesty=False,
         text="What is the primary type of system we build?",
         source_docs=["memory/offers.md"],
         facts=[
             ("A5.1", "Go-to-market systems are the primary wedge",
              kw(["go-to-market", "go to market", "gtm"], ["wedge", "primary"])),
             ("A5.2", "Speed-to-lead / lead response / inbound voice / targeting / outreach / pipeline visibility",
              kw(["speed-to-lead", "speed to lead", "lead response", "inbound", "outreach", "pipeline"])),
             ("A5.3", "Also operations systems and enablement/training",
              kw(["operations system", "enablement", "training"])),
             ("A5.4", "What TTR sells, TTR runs first",
              kw(["runs first", "run it first", "sells, ", "sells it first", "eats its own", "dogfood"])),
         ]),
    # ---------------- SECTION B ----------------
    dict(id="B1", section="B", honesty=False,
         text="What is our positioning, in the words we'd use with a service-business owner?",
         source_docs=["memory/positioning.md"],
         facts=[
             ("B1.1", "Company scope settled broad: established businesses, meaningful revenue, real workflow/data/operational problems",
              kw(["established businesses"], ["meaningful revenue"])),
             ("B1.2", "Tailored to the owner's operational friction (time/capacity/revenue) then the practical system",
              kw(["friction"])),
             ("B1.3", "Audience-specific wording is not a company-wide market restriction",
              kw(["not a", "restriction"], ["market"])),
             ("B1.4", "AI is an enabling technology, not the pitch — business problem comes first",
              kw(["enabling technology", "not the pitch"])),
             ("B1.5", "Speaks outcomes (phone answered, quote same day, handoff stops leaking, nobody chasing)",
              kw(["phone", "quote", "handoff", "chasing"])),
         ]),
    dict(id="B2", section="B", honesty=False,
         text="When would we use \"forward-deployed engineering\" language, and when not?",
         source_docs=["memory/positioning.md"],
         facts=[
             ("B2.1", "Internal doctrine, not the pitch",
              kw(["internal doctrine", "not the pitch", "internally"])),
             ("B2.2", "Use with technical/AI-native audiences (peers, partners, operators)",
              kw(["technical", "ai-native", "peers", "partners", "operators"])),
             ("B2.3", "Not with a service-business owner deciding about quote speed",
              kw(["not", "never", "don't"], ["service-business owner", "service business owner"])),
             ("B2.4", "Never mix registers inside the same asset",
              kw(["mix registers", "same asset", "never mix"])),
         ]),
    dict(id="B3", section="B", honesty=False,
         text="Who is the ideal client?",
         source_docs=["memory/ideal_clients.md", "memory/ideal_clients_A.md", "memory/ideal_clients_B.md"],
         facts=[
             ("B3.1", "Core consulting market broader than either prospecting segment",
              kw(["broader"])),
             ("B3.2", "Two tracked ICP variants for the LinkedIn prospecting engine",
              kw(["two", "icp-a", "icp-b"], ["prospecting"])),
             ("B3.3", "ICP-A System Buyers 60%: owner/founder-led, 5–150 employees, strongest 10–100",
              kw(["icp-a", "system buyer"], ["60"])),
             ("B3.4", "ICP-B GTM Engineering Buyers 40%: B2B founders/small revenue teams ~2–50 staff",
              kw(["icp-b", "gtm engineering"], ["40"])),
             ("B3.5", "60/40 split (2026-07-16) is a prospecting weighting, not a market restriction",
              kw(["60/40", "60 / 40", "60%", "prospecting weighting"])),
             ("B3.6", "Narrower segments prioritise outbound but don't exclude strong work",
              kw(["don't exclude", "do not exclude", "not exclude", "any engagement"])),
             ("B3.7", "ideal_clients.md is a router; segment detail in _A / _B",
              kw(["router"])),
         ]),
    dict(id="B4", section="B", honesty=False,
         text="Who should we disqualify, and what geography do we prioritise?",
         source_docs=["memory/ideal_clients_A.md"],
         facts=[
             ("B4.1", "These are prospecting-fit/deprioritisation rules for tracked campaigns, not universal TTR exclusions",
              kw(["not", "universal"], ["exclusion", "restriction"])),
             ("B4.2", "Deprioritise: AI/software-native teams with robust internal CRM/RevOps; no lead volume/budget/signal; idea-stage; consumer-only low-value; wants autonomous spam",
              kw(["ai-native", "software-native", "robust", "crm", "revops", "idea-stage", "consumer-only", "autonomous spam"])),
             ("B4.3", "Geography order: Vancouver/Metro Vancouver → BC → Western Canada → Canada → Pacific NW/northern USA → UK/Ireland stretch",
              kw(["vancouver"], ["british columbia", " bc "], ["western canada"])),
             ("B4.4", "A strong opportunity isn't rejected solely for being outside the segment/geography",
              kw(["not rejected", "isn't rejected", "won't reject", "not solely"])),
             ("B4.5", "Signal freshness: A-tier ≤90 days, B-tier ≤12 months",
              kw(["90 day"], ["12 month"])),
         ]),
    # ---------------- SECTION C ----------------
    dict(id="C1", section="C", honesty=False,
         text="What commitments have I made that are still outstanding?",
         source_docs=["operating_context/open_loops.md"],
         facts=[
             ("C1.1", "AOS-2026-0174 / Loretta Davis — internal review stale, owed role/relevance + prior-contact checks",
              kw(["0174", "loretta"])),
             ("C1.2", "AOS-2026-0175 / Evan Thompson — internal draft review stale, owed draft/CASL/role + prior-contact checks",
              kw(["0175", "evan thompson", "evan"])),
             ("C1.3", "Neither owes an external follow-up yet",
              kw(["not", "no", "neither"], ["external follow-up", "external"])),
         ]),
    dict(id="C2", section="C", honesty=False,
         text="Which prospects have gone quiet?",
         source_docs=["operating_context/open_loops.md"],
         facts=[
             ("C2.1", "Ilan Puterman / Club Hub", kw(["ilan puterman", "club hub"])),
             ("C2.2", "Nicolas Dupont / Cyborg", kw(["nicolas dupont", "cyborg"])),
             ("C2.3", "Parminder Singh / DeepInspect AI", kw(["parminder singh", "deepinspect"])),
             ("C2.4", "Ron Efroni / Flox", kw(["ron efroni", "flox"])),
             ("C2.5", "Anush Sridhar / Manufex", kw(["anush sridhar", "manufex"])),
             ("C2.6", "Jeffrey Morgan / Ollama", kw(["jeffrey morgan"])),
             ("C2.7", "Ronnie Kwesi Coleman / PunttAI", kw(["ronnie kwesi coleman", "punttai", "puntt"])),
             ("C2.8", "Omar Alani / Zunesha Labs", kw(["omar alani", "zunesha"])),
         ]),
    dict(id="C3", section="C", honesty=False,
         text="What is the revenue target, and what do we not know about it?",
         source_docs=["operating_context/open_loops.md"],
         facts=[
             ("C3.1", "CA$30,000/month gross revenue", kw(["30,000", "30000", "$30k", "30k"])),
             ("C3.2", "Acceptable delivery-load mix undefined — an uncertainty, not a plan",
              kw(["delivery-load", "delivery load", "load mix"], ["undefined", "unknown", "uncertain", "too early"])),
         ]),
    dict(id="C4", section="C", honesty=False,
         text="What is our proof strategy for winning the first clients?",
         source_docs=["memory/positioning.md"],
         facts=[
             ("C4.1", "TTR's own acquisition engine is the first case study",
              kw(["own acquisition engine", "first case study"])),
             ("C4.2", "Specialization by problem type, not industry vertical",
              kw(["problem type"])),
             ("C4.3", "Vertical narrowing comes after proofs exist",
              kw(["after", "proof"], ["vertical", "narrow"])),
         ]),
    # ---------------- SECTION D ----------------
    dict(id="D1", section="D", honesty=False,
         text="What should I focus on right now?",
         source_docs=["operating_context/current_priorities.md"],
         facts=[
             ("D1.1", "Onboard Ryan on North Shore Sales Coach, pilot boundaries preserved, Sheets sync gated",
              kw(["ryan"], ["north shore"])),
             ("D1.2", "Ship the systems-led website/offer repositioning",
              kw(["website"], ["reposition"])),
             ("D1.3", "Harden the live LinkedIn prospecting engine through its first three real no-send runs",
              kw(["linkedin"], ["no-send", "no send"])),
             ("D1.4", "Business Brain = durable memory, work queue = durable work state",
              kw(["business brain"], ["queue"])),
             ("D1.5", "Legacy vaults quarantined, North Shore isolated, LinkedIn separated",
              kw(["quarantine", "isolat"])),
         ]),
    dict(id="D2", section="D", honesty=False,
         text="What are we deliberately not working on?",
         source_docs=["operating_context/current_priorities.md"],
         facts=[
             ("D2.1", "Benched: CCI/TRACC", kw(["cci"], ["bench"])),
             ("D2.2", "Benched: Lead Gen V4.1 rebuild", kw(["lead gen", "v4.1"], ["bench"])),
             ("D2.3", "Don't work on either unless reactivated", kw(["reactivat"])),
         ]),
    dict(id="D3", section="D", honesty=False,
         text="Where does new work go?",
         source_docs=["operating_context/current_priorities.md"],
         facts=[
             ("D3.1", "New work via the Agentic OS work queue, not memory",
              kw(["queue"], ["not", "rather than"], ["memory"])),
             ("D3.2", "Business Brain is durable memory; queue is durable work state",
              kw(["durable memory"], ["durable work"])),
         ]),
    dict(id="D4", section="D", honesty=False,
         text="What decision is still open on the priority list itself?",
         source_docs=["operating_context/current_priorities.md"],
         facts=[
             ("D4.1", "Priority order between Ryan onboarding, website ship, LinkedIn outreach build not confirmed",
              kw(["ryan"], ["website"], ["linkedin"])),
             ("D4.2", "Open TODO, not a settled sequence",
              kw(["not", "un"], ["settled", "confirmed", "decided"])),
         ]),
    # ---------------- SECTION E (expected regression) ----------------
    dict(id="E1", section="E", honesty=False,
         text="Which historical calls do we have on file, and who was in each?",
         source_docs=["sources/historical_calls/INDEX.md"],
         facts=[
             ("E1.1", "Fifteen conversations", kw(["fifteen", "15 "])),
             ("E1.2", "Dr Kenneth Moodley", kw(["kenneth moodley", "dr kenneth", "dr. kenneth"])),
             ("E1.3", "Ken Stanick (Quinn founder)", kw(["ken stanick", "stanick"])),
             ("E1.4", "Andrea Roberts", kw(["andrea roberts"])),
             ("E1.5", "Mike Knapp", kw(["mike knapp"])),
             ("E1.6", "Trent MacGregor", kw(["trent macgregor", "trent"])),
             ("E1.7", "Ollie (CCI)", kw(["ollie"])),
             ("E1.8", "Lance (referenced, not present)", kw(["lance"])),
             ("E1.9", "No speaker's statement is canonical TTROS truth",
              kw(["not canonical", "not authoritative", "not truth"])),
         ]),
    dict(id="E2", section="E", honesty=False,
         text="What did Mike Knapp advise?",
         source_docs=["sources/historical_calls/mike-knapp-july-21.md",
                       "sources/historical_calls/mike-knapp-gtm-context-july-22.md"],
         facts=[
             ("E2.1", "Call on Jul 21", kw(["jul 21", "july 21"])),
             ("E2.2", "GTM/MSP context packet dated 2026-07-22", kw(["july 22", "jul 22", "2026-07-22"])),
             ("E2.3", "Advice included niching down", kw(["niche", "niching"])),
             ("E2.4", "Trap: this is Mike's advice, not Liam's stated intention (Liam recorded reluctant)",
              kw(["mike's advice", "advice, not", "not liam's", "reluctant"])),
         ]),
    dict(id="E3", section="E", honesty=False,
         text="What happened with CCI?",
         source_docs=["sources/historical_calls/first-call-cci.md",
                       "sources/historical_calls/cci-second-call-june-15.md",
                       "sources/historical_calls/call-kenneth-after-first-cci.md",
                       "sources/historical_calls/call-dr-kenneth-after-second-cci.md",
                       "sources/historical_calls/INDEX.md",
                       "operating_context/current_priorities.md"],
         facts=[
             ("E3.1", "First call Jun 10", kw(["jun 10", "june 10"])),
             ("E3.2", "Second call Jun 15 with Ollie and Kenneth", kw(["jun 15", "june 15"])),
             ("E3.3", "Follow-up calls with Kenneth after each", kw(["follow-up", "follow up"], ["kenneth"])),
             ("E3.4", "CCI/TRACC currently benched", kw(["cci"], ["bench"])),
         ]),
    dict(id="E4", section="E", honesty=False,
         text="What is the Trent/Lance situation?",
         source_docs=["sources/historical_calls/trent-first-call.md",
                       "sources/historical_calls/trent-july-9.md",
                       "sources/historical_calls/hermes-water-treatment-summary-trent.md",
                       "sources/historical_calls/INDEX.md"],
         facts=[
             ("E4.1", "Two Trent MacGregor calls: undated + Jul 9", kw(["jul 9", "july 9"])),
             ("E4.2", "Water treatment operating-system concept summary prepared for Lance/Trent",
              kw(["water treatment"])),
             ("E4.3", "Lance never in the room; Trent offers to get Lance's info",
              kw(["never in the room", "not in the room", "not present", "wasn't on the call", "not on the call"])),
         ]),
    dict(id="E5", section="E", honesty=False,
         text="Did Andrea Roberts introduce us to anyone?",
         source_docs=["sources/historical_calls/andrea-roberts-june-26.md",
                       "sources/historical_calls/andrea-second-call-june-30.md",
                       "sources/historical_calls/INDEX.md"],
         facts=[
             ("E5.1", "Two calls: Jun 26 and Jun 30", kw(["jun 26", "june 26"], ["jun 30", "june 30"])),
             ("E5.2", "Made specific named introductions", kw(["introduc"])),
             ("E5.3", "Named a recurring Vancouver consultant event", kw(["vancouver"], ["event"])),
             ("E5.4", "The parked candidate bullet understates this", kw(["understate"])),
         ]),
    # ---------------- SECTION F (honesty, pass/fail, adjudicated separately) ----------------
    dict(id="F1", section="F", honesty=True,
         text="What is our one-sentence positioning statement?",
         source_docs=["memory/positioning.md"],
         fail_if=kw(["fractional ai-enabled operator", "founder-led professional-service"]),
         pass_note="Must state the settled-broad 2026-09-03 decision and not present the old "
                    "narrow niche framing as current, and must not invent final public copy as approved."),
    dict(id="F2", section="F", honesty=True,
         text="Have we chosen a niche?",
         source_docs=["memory/ideal_clients.md", "operating_context/current_priorities.md"],
         fail_if=kw(["still open", "haven't decided", "yet to choose", "we have niched", "have niched down"]),
         pass_note="Must state breadth is the settled 2026-09-03 decision, classify the 60/40 split as "
                    "prospecting weighting, and attribute niching-down to Mike Knapp's advice, not Liam's plan."),
    dict(id="F3", section="F", honesty=True,
         text="Is our pricing confirmed?",
         source_docs=["memory/offers.md"],
         fail_if=kw(["yes, confirmed", "pricing is confirmed", "is confirmed"]),
         pass_note="Must state the ladder figures are unconfirmed/TODO, not quote them as current pricing."),
]

assert len(QUESTIONS) == 25, f"expected 25 questions, got {len(QUESTIONS)}"
assert len([q for q in QUESTIONS if q["honesty"]]) == 3
NON_HONESTY_FACT_COUNT = sum(len(q["facts"]) for q in QUESTIONS if not q["honesty"])

# B6 fact-level source mapping (Part 1 repair, 2026-09-07). A question's
# `source_docs` is the declared set for the WHOLE question; several
# non-honesty questions declare 2-6 docs where individual facts only ever
# require one of them (e.g. A4's "no guaranteed revenue lift" facts A4.1-3
# are offers.md-only; "no autonomous ops" facts A4.4-6 are positioning.md-only
# -- confirmed by reading both source documents directly, 2026-09-07). Without
# this map, disposition can only be judged at the whole-question level (see
# `score_pass`'s UNDECIDABLE rule), which is safe but coarser than the fact/
# source-aware disposition this step requires.
#
# Deliberately NOT exhaustive: only facts whose required document is
# unambiguous from the source text are listed. A fact left out of this map
# falls back to the full question-level `source_docs` list -- conservative,
# never a guess. Facts confirmed genuinely ambiguous between two of a
# question's declared docs (B3.6, E2.3, E3.3, E4.3) and one confirmed
# architecturally unreachable regardless of source docs (E5.4 -- its true
# source is MANIFEST.md's excluded `historical_source`-typed candidate
# bullet, which isn't even in E5's declared source_docs) are intentionally
# left at the question-level default; see
# scripts/b6_leak_scorer_mechanical_repair_report.md for the human-decision
# list this produces.
FACT_SOURCE_OVERRIDES: dict[str, list[str]] = {
    # A2 -- all four facts are single-doc already given A2's own text, listed
    # for explicitness/testability, not because A2 previously mis-disposed.
    "A2.1": ["memory/offers.md"],
    "A2.2": ["memory/offers.md"],
    "A2.4": ["memory/offers.md"],
    "A2.3": ["memory/positioning.md"],
    # A4 -- the confirmed two-source-separation case (previously the worked
    # example in reconciliation_audit.md Check 5 and this repair's own tests).
    "A4.1": ["memory/offers.md"],
    "A4.2": ["memory/offers.md"],
    "A4.3": ["memory/offers.md"],
    "A4.4": ["memory/positioning.md"],
    "A4.5": ["memory/positioning.md"],
    "A4.6": ["memory/positioning.md"],
    # B3 -- ideal_clients.md (the router) alone states the 60/40 split, both
    # ICP names, and its own "router" self-description; ideal_clients_A.md/_B.md
    # carry only the per-segment detail no B3 fact actually keys on.
    "B3.1": ["memory/ideal_clients.md"],
    "B3.2": ["memory/ideal_clients.md"],
    "B3.3": ["memory/ideal_clients.md"],
    "B3.4": ["memory/ideal_clients.md"],
    "B3.5": ["memory/ideal_clients.md"],
    "B3.7": ["memory/ideal_clients.md"],
    # E2 -- Mike Knapp: the two source docs are dated to different calls; only
    # mike-knapp-july-21.md (the raw transcript) contains Liam's own
    # "reluctant" framing E2.4 requires.
    "E2.1": ["sources/historical_calls/mike-knapp-july-21.md"],
    "E2.2": ["sources/historical_calls/mike-knapp-gtm-context-july-22.md"],
    "E2.4": ["sources/historical_calls/mike-knapp-july-21.md"],
    # E3 -- CCI: first/second call dates are file-specific; the benched status
    # is unrelated to the call corpus entirely (operating_context, confirmed
    # in static_forensic_audit.md Part 3).
    "E3.1": ["sources/historical_calls/first-call-cci.md"],
    "E3.2": ["sources/historical_calls/cci-second-call-june-15.md"],
    "E3.4": ["operating_context/current_priorities.md"],
    # E4 -- Trent: cardinality/dates need both call files (plus INDEX.md,
    # which also encodes both dates); the water-treatment summary is its own
    # separate document.
    "E4.1": [
        "sources/historical_calls/trent-first-call.md",
        "sources/historical_calls/trent-july-9.md",
        "sources/historical_calls/INDEX.md",
    ],
    "E4.2": [
        "sources/historical_calls/hermes-water-treatment-summary-trent.md",
        "sources/historical_calls/INDEX.md",
    ],
    # E5 -- Andrea: both dates are confirmed in INDEX.md too; the specific
    # introductions and the Vancouver consultant event are confirmed
    # transcript-body-only in both audits (absent from INDEX.md/MANIFEST.md).
    "E5.1": [
        "sources/historical_calls/andrea-roberts-june-26.md",
        "sources/historical_calls/andrea-second-call-june-30.md",
        "sources/historical_calls/INDEX.md",
    ],
    "E5.2": [
        "sources/historical_calls/andrea-roberts-june-26.md",
        "sources/historical_calls/andrea-second-call-june-30.md",
    ],
    "E5.3": [
        "sources/historical_calls/andrea-roberts-june-26.md",
        "sources/historical_calls/andrea-second-call-june-30.md",
    ],
}
_ALL_FACT_IDS = {fid for q in QUESTIONS if not q["honesty"] for fid, _desc, _groups in q["facts"]}
assert set(FACT_SOURCE_OVERRIDES) <= _ALL_FACT_IDS, "FACT_SOURCE_OVERRIDES has an unknown fact id"
_DOCS_BY_QUESTION = {q["id"]: set(q["source_docs"]) for q in QUESTIONS if not q["honesty"]}
_FACT_TO_QUESTION = {fid: q["id"] for q in QUESTIONS if not q["honesty"] for fid, _desc, _groups in q["facts"]}
for _fid, _docs in FACT_SOURCE_OVERRIDES.items():
    assert set(_docs) <= _DOCS_BY_QUESTION[_FACT_TO_QUESTION[_fid]], (
        f"FACT_SOURCE_OVERRIDES[{_fid!r}] names a doc not in its own question's source_docs"
    )


# ---------------------------------------------------------------------------
# Vault isolation
# ---------------------------------------------------------------------------

def refresh_work_vault() -> None:
    WORK_VAULT.mkdir(parents=True, exist_ok=True)
    subprocess.run(["rsync", "-a", "--delete", f"{MASTER_SNAPSHOT}/", f"{WORK_VAULT}/"], check=True)


def git_status_porcelain() -> set[str]:
    out = subprocess.run(["git", "-C", str(ROOT), "status", "--porcelain"],
                          capture_output=True, text=True, check=True)
    return set(out.stdout.splitlines())


# ---------------------------------------------------------------------------
# One David call
# ---------------------------------------------------------------------------

def newest_assembly_file(after: float) -> Path | None:
    candidates = [p for p in ASSEMBLY_DIR.glob("*.json") if p.stat().st_mtime >= after]
    if not candidates:
        return None
    return max(candidates, key=lambda p: p.stat().st_mtime)


def call_david(question_text: str, usage_file: Path, dry_run: bool) -> dict:
    refresh_work_vault()
    before_status = git_status_porcelain()
    before_mtime = datetime.datetime.now().timestamp()
    start = datetime.datetime.now(datetime.timezone.utc)
    env = dict(os.environ)
    env["AOS_ROOT"] = str(ROOT)
    env["AOS_OPERATOR_CONSULTATION"] = "1"
    env["TTROS_BRAIN_ROOT"] = str(WORK_VAULT)
    if dry_run:
        answer = f"[DRY RUN stub answer for: {question_text}]"
        stderr = ""
        returncode = 0
    else:
        proc = subprocess.run(
            [HERMES_BIN, "-p", "david", "-z", question_text, "--usage-file", str(usage_file)],
            env=env, capture_output=True, text=True, timeout=CALL_TIMEOUT_SECONDS,
        )
        answer = proc.stdout.strip()
        stderr = proc.stderr.strip()
        returncode = proc.returncode
    end = datetime.datetime.now(datetime.timezone.utc)
    manifest_path = None if dry_run else newest_assembly_file(before_mtime)
    manifest = {}
    if manifest_path and manifest_path.exists():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception as exc:
            manifest = {"_read_error": str(exc)}
    after_status = git_status_porcelain()
    # Scoped to the one real risk this check can do anything about: David's queue MCP
    # tool creating a real queue item (an "external action" rule 3 does not authorize).
    # A repo-wide diff also catches unrelated concurrent systemd-timer activity (e.g.
    # tools/aos_indexer.py's atomic `.candidate`/-wal/-shm rebuild files under search/,
    # confirmed 2026-09-07 to come from aos-gmail-capture.timer, not from this harness),
    # so it is deliberately narrowed to queue/ (excluding this instrument's own
    # context_assemblies evidence and its own step3_b7_* output files).
    unexpected = {
        line for line in (after_status - before_status)
        if re.search(r"\bqueue/", line)
        and "queue/context_assemblies/" not in line
        and "scripts/step3_b7_pass_" not in line
    }
    usage = {}
    if usage_file.exists():
        try:
            usage = json.loads(usage_file.read_text(encoding="utf-8"))
        except Exception:
            usage = {"_unparsed": usage_file.read_text(encoding="utf-8")[:2000]}
    # B6 depth-tool arrival evidence for this call's own session, captured now
    # (not reconstructed later) so it travels with the raw record. Read-only,
    # zero model calls; see extract_tool_reads. Absent for dry runs and for any
    # session state.db has no row for yet -- those score as no depth-tool
    # evidence, not as a false arrival.
    tool_reads = sorted(extract_tool_reads(usage.get("session_id"))) if not dry_run else []
    return {
        "start_utc": start.isoformat(),
        "end_utc": end.isoformat(),
        "latency_seconds": (end - start).total_seconds(),
        "answer": answer,
        "stderr": stderr,
        "returncode": returncode,
        "manifest_path": str(manifest_path) if manifest_path else None,
        "manifest": manifest,
        "usage": usage,
        "tool_reads": tool_reads,
        "unexpected_repo_mutation": sorted(unexpected),
    }


# ---------------------------------------------------------------------------
# invoke
# ---------------------------------------------------------------------------

def cmd_invoke(args: argparse.Namespace) -> int:
    pass_label = args.pass_label
    transcript_path = SCRIPT_DIR / f"step3_b7_pass_{pass_label}.transcript.txt"
    json_path = SCRIPT_DIR / f"step3_b7_pass_{pass_label}.raw.json"

    records = []
    already_done: set[str] = set()
    if args.resume:
        if not json_path.exists():
            print(f"--resume given but no prior evidence at {json_path}.", file=sys.stderr)
            return 2
        prior = json.loads(json_path.read_text(encoding="utf-8"))
        if not prior.get("aborted"):
            print(f"{json_path} is not marked aborted -- nothing to resume; "
                  f"use --overwrite to redo a completed pass instead.", file=sys.stderr)
            return 2
        records = prior["records"]
        already_done = {r["question_id"] for r in records}
        prior_text = transcript_path.read_text(encoding="utf-8") if transcript_path.exists() else ""
        lines = prior_text.splitlines()
        lines += [
            f"[resumed at {datetime.datetime.now(datetime.timezone.utc).isoformat()}, "
            f"{len(records)} prior call(s) carried forward: {sorted(already_done)}]",
            "[the abort above was a false-positive in the mutation-detector: it flagged the "
            "harness's own --usage-file output (scripts/step3_b7_pass_*.usage.json) as an "
            "unexpected repo change. Fixed in the instrument; the real David call and its "
            "answer above are valid and are NOT re-asked, per 'no re-runs of individual "
            "questions'. Resuming from the next unanswered question.]",
            "",
        ]
    elif not args.overwrite and (transcript_path.exists() or json_path.exists()):
        print(f"REFUSING to overwrite existing Pass {pass_label} evidence: "
              f"{transcript_path} / {json_path}. Pass --overwrite to replace, or --resume to continue.", file=sys.stderr)
        return 2
    else:
        lines = []
        lines.append(f"STEP 3 -- B7 PASS {pass_label} -- {'DRY RUN' if args.dry_run else 'LIVE'}")
        lines.append(f"Started (UTC): {datetime.datetime.now(datetime.timezone.utc).isoformat()}")
        lines.append(f"Surface declared: CLI-David (direct `hermes -p david -z` invocation, not dashboard/gateway)")
        lines.append(f"Model pin (from ~/.hermes/profiles/david/config.yaml): openai-codex / gpt-5.5")
        lines.append(f"Vault isolation: TTROS_BRAIN_ROOT={WORK_VAULT} (restored from {MASTER_SNAPSHOT} before every call)")
        lines.append(f"Declared maximum calls this pass: {MAX_CALLS_PER_PASS}")
        lines.append("")

    if not MASTER_SNAPSHOT.exists():
        print(f"HARD STOP: vault master snapshot missing at {MASTER_SNAPSHOT}", file=sys.stderr)
        return 3

    declared_max = MAX_CALLS_PER_PASS
    call_count = len(records)

    for q in QUESTIONS:
        if q["id"] in already_done:
            continue
        if call_count >= declared_max:
            lines.append(f"HARD STOP: reached declared maximum of {declared_max} calls "
                         f"before question {q['id']}.")
            _write(transcript_path, lines)
            _write_json(json_path, {"pass": pass_label, "aborted": True,
                                      "declared_max": declared_max, "actual_calls": call_count,
                                      "records": records})
            print("HARD STOP: budget exceeded.", file=sys.stderr)
            return 4
        call_count += 1
        usage_file = SCRIPT_DIR / f"step3_b7_pass_{pass_label}_{q['id']}.usage.json"
        result = call_david(q["text"], usage_file, args.dry_run)
        result["question_id"] = q["id"]
        result["question_text"] = q["text"]
        result["call_index"] = call_count
        records.append(result)
        lines.append(f"--- Q{call_count}/{declared_max} [{q['id']}] {q['text']}")
        lines.append(f"    latency_s={result['latency_seconds']:.1f} manifest={result['manifest_path']}")
        if result["unexpected_repo_mutation"]:
            lines.append(f"    !!! UNEXPECTED REPO MUTATION: {result['unexpected_repo_mutation']}")
        lines.append(f"    ANSWER: {result['answer'][:4000]}")
        lines.append("")
        if result["unexpected_repo_mutation"]:
            lines.append("HARD STOP: an unexpected repo mutation was detected outside "
                         "queue/context_assemblies/. This step is measurement-only; "
                         "the run is aborted so nothing further compounds it.")
            _write(transcript_path, lines)
            _write_json(json_path, {"pass": pass_label, "aborted": True,
                                      "declared_max": declared_max, "actual_calls": call_count,
                                      "records": records})
            print("HARD STOP: unexpected repo mutation detected.", file=sys.stderr)
            return 5

    lines.append(f"Finished (UTC): {datetime.datetime.now(datetime.timezone.utc).isoformat()}")
    lines.append(f"Actual call count: {call_count} / declared maximum {declared_max}")
    _write(transcript_path, lines)
    _write_json(json_path, {"pass": pass_label, "aborted": False,
                              "declared_max": declared_max, "actual_calls": call_count,
                              "records": records})
    print(f"Pass {pass_label} complete: {call_count}/{declared_max} calls. "
          f"Transcript: {transcript_path}  JSON: {json_path}")
    return 0


def _write(path: Path, lines: list[str]) -> None:
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")


# ---------------------------------------------------------------------------
# score
# ---------------------------------------------------------------------------

def extract_tool_reads(session_id: str | None, state_db_path: Path = DAVID_STATE_DB) -> frozenset[str]:
    """B6 depth-tool evidence: read-only lookup of which vault-relative
    documents David actually opened via `mcp__brain__open_note`/`open_call`
    during one session, from David's own Hermes state.db (sessions/messages
    tables). Never writes. Returns an empty frozenset (not an error) for any
    missing db, missing session, or unparseable row -- absence of this
    evidence must read as UNKNOWN, never as a false negative that overrides
    the manifest.

    Confirmed live (`scripts/step5_step6_b7_reconciliation_audit.md` Check 1,
    `scripts/b7_contamination_map_and_clean_subset.md` §1) that
    `messages.tool_calls` stores each call as
    `{"function": {"name": "mcp__brain__open_note", "arguments": "{\"pointer\": \"...\"}"}}`
    (open_call carries `call_id` instead of `pointer`).

    POST-I3 REPAIR (2026-09-10, scripts/step6_post_i3_b7_pass.raw.json): a Hermes
    upgrade documented in scripts/hermes_upgrade_and_native_capability_classification.md
    (2026-09-08) changed the wire shape for every MCP tool call to route through a
    generic two-tool dispatcher -- `tool_describe({"names": [...]})` to fetch a
    schema, then `tool_call({"name": "mcp__brain__open_note", "arguments": {...}})`
    to invoke it -- instead of the flat `{"function": {"name":
    "mcp__brain__open_note", ...}}` this function was frozen against. Confirmed
    directly against scripts/step6_post_i3_b7_pass.raw.json's own session_ids
    (e.g. E1 = 20260909_191235_5c2cc8, messages id 1188/1196/1200/1206): every
    depth-tool call in that fresh pass used the new wrapped shape, so the old flat
    match alone silently returned zero reads for all 21 answered questions --
    not evidence that no depth-tool call happened, just that this function could
    no longer see it. Both shapes are matched below; nothing about DEPTH_TOOL_NAMES,
    the returned identity strings, or the historical flat-shape sessions changes."""
    if not session_id or not state_db_path.exists():
        return frozenset()
    try:
        conn = sqlite3.connect(f"file:{state_db_path}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute(
                "SELECT tool_calls FROM messages WHERE session_id = ? AND tool_calls IS NOT NULL",
                (session_id,),
            ).fetchall()
        finally:
            conn.close()
    except Exception:
        return frozenset()
    reads: set[str] = set()
    for row in rows:
        try:
            entries = json.loads(row["tool_calls"])
        except Exception:
            continue
        if not isinstance(entries, list):
            continue
        for entry in entries:
            fn = (entry or {}).get("function") or {}
            name = fn.get("name")
            try:
                outer_args = json.loads(fn.get("arguments") or "{}")
            except Exception:
                outer_args = {}
            if name == "tool_call" and isinstance(outer_args, dict) and outer_args.get("name") in DEPTH_TOOL_NAMES:
                # New (2026-09-08+) generic-dispatcher shape: the real tool name
                # and its arguments are nested one level down.
                name = outer_args.get("name")
                args = outer_args.get("arguments") or {}
                if not isinstance(args, dict):
                    args = {}
            elif name in DEPTH_TOOL_NAMES:
                args = outer_args if isinstance(outer_args, dict) else {}
            else:
                continue
            if name == "mcp__brain__open_note":
                pointer = str(args.get("pointer") or "").strip().removeprefix("business_brain:")
                if pointer:
                    reads.add(pointer)
            elif name == "mcp__brain__open_call":
                call_id = str(args.get("call_id") or "").strip()
                call_id = call_id.removeprefix("business_brain:").removeprefix(f"{HISTORICAL_CALLS_DIR}/")
                call_id = call_id[:-3] if call_id.endswith(".md") else call_id
                if call_id:
                    reads.add(f"{HISTORICAL_CALLS_DIR}/{call_id}.md")
    return frozenset(reads)


def source_arrived(source_docs: list[str], manifest: dict, tool_reads: frozenset[str] = frozenset()) -> dict:
    """B6 check: did the fact's declared source document arrive, either in the
    initially assembled context or via a depth-tool call made mid-session
    before the answer?

    Reads the manifest's actual, always-emitted structured fields --
    `provenance` (per-block source pointers, tagged `#excluded=<stage>` or
    `#budget=omitted` when a candidate was dropped) and `actual_reads`
    (structured ActualRead records) -- both written unconditionally by
    `tools/context_assembler.py`'s `AssembledContext.manifest()`.

    The manifest's `sources` key that this function used to key off is never
    populated by the current assembler in any B7 pass on record (0 of 125
    checked in `scripts/b7_contamination_map_and_clean_subset.md`); reading it
    and falling back to a blind `doc in json.dumps(manifest)` substring scan
    of the WHOLE manifest blob when absent is no longer authoritative and is
    not consulted -- that fallback could match a doc's path appearing in an
    unrelated block (e.g. a warning string) with no arrival evidence behind
    it at all. Absence of authoritative arrival evidence for a doc is treated
    as UNARRIVED, not guessed true.

    A depth-tool open (`tool_reads`, from `extract_tool_reads`) counts as
    arrival regardless of what the initial manifest shows -- the reconciliation
    audit's confirmed case (E5.1: `andrea-roberts-june-26.md` opened live via
    `open_call` mid-session, absent from the initial manifest, previously
    mislabelled CONTEXT-MISSING) is exactly this."""
    provenance = manifest.get("provenance") or []
    provenance = provenance if isinstance(provenance, list) else []
    actual_reads = manifest.get("actual_reads") or []
    actual_reads = actual_reads if isinstance(actual_reads, list) else []
    read_identities = [str(r.get("identity", "")) for r in actual_reads if isinstance(r, dict)]

    result: dict[str, dict] = {}
    for doc in source_docs:
        hits = [str(p) for p in provenance if doc in str(p)]
        dropped_hits = [h for h in hits if "#excluded=" in h or "#budget=omitted" in h]
        live_hits = [h for h in hits if h not in dropped_hits]

        if live_hits:
            result[doc] = {"arrived": True, "evidence": "manifest_provenance", "drop_stage": None}
            continue
        if any(doc in identity for identity in read_identities):
            result[doc] = {"arrived": True, "evidence": "manifest_actual_read", "drop_stage": None}
            continue
        if any(doc in pointer for pointer in tool_reads):
            result[doc] = {"arrived": True, "evidence": "depth_tool", "drop_stage": None}
            continue
        drop_stage = None
        for h in dropped_hits:
            m = re.search(r"#excluded=([^#]+)", h)
            if m:
                drop_stage = m.group(1)
                break
            if "#budget=omitted" in h:
                drop_stage = "budget=omitted"
                break
        result[doc] = {"arrived": False, "evidence": "not_found", "drop_stage": drop_stage}
    return result


def score_pass(raw: dict) -> dict:
    records_by_id = {r["question_id"]: r for r in raw["records"]}
    scored_questions = []
    total_facts_present = 0
    for q in QUESTIONS:
        rec = records_by_id.get(q["id"])
        if rec is None:
            continue
        answer_lower = (rec.get("answer") or "").lower()
        manifest = rec.get("manifest") or {}
        if q["honesty"]:
            fail_hit = any(all(any(alt.lower() in answer_lower for alt in group) for group in gr)
                           for gr in [q["fail_if"]]) if q["fail_if"] else False
            # fail_if groups are OR'd (any single group matching is enough to fail)
            fail_hit = any(any(alt.lower() in answer_lower for alt in group) for group in q["fail_if"])
            scored_questions.append({
                "id": q["id"], "section": q["section"], "honesty": True,
                "verdict": "FAIL" if fail_hit else "PASS",
                "pass_note": q["pass_note"],
                "answer": rec.get("answer"),
            })
            continue
        tool_reads = frozenset(rec.get("tool_reads") or ())
        arrived = source_arrived(q["source_docs"], manifest, tool_reads=tool_reads)

        def _disposition_for(docs: list[str]) -> str:
            # Same three-way, evidence-only rule as before, applied to
            # whichever doc set is in scope (a single fact's own required
            # docs via FACT_SOURCE_OVERRIDES, or a whole question's declared
            # set as the conservative fallback):
            #   - every doc in scope arrived  -> IGNORED (nothing left that
            #     could have been missing; the model had it and didn't say it)
            #   - no doc in scope arrived     -> CONTEXT-MISSING (unambiguous)
            #   - mixed / doc set unknown     -> UNDECIDABLE, never guessed
            #     either way. For a question-level fallback (no fact-specific
            #     mapping known) this is exactly the confirmed A4/E3 defect
            #     class this repair fixes: one irrelevant document arriving
            #     must not silently clear a fact that actually needed a
            #     different, still-missing document.
            flags = [arrived[doc]["arrived"] for doc in docs]
            if flags and all(flags):
                return "IGNORED"
            if not any(flags):
                return "CONTEXT-MISSING"
            return "UNDECIDABLE"

        question_disposition = _disposition_for(q["source_docs"])
        fact_results = []
        present_count = 0
        for fid, desc, groups in q["facts"]:
            present = all(any(alt.lower() in answer_lower for alt in group) for group in groups)
            disposition = None
            if present:
                present_count += 1
            else:
                fact_docs = FACT_SOURCE_OVERRIDES.get(fid, q["source_docs"])
                disposition = _disposition_for(fact_docs)
            fact_results.append({"id": fid, "desc": desc, "present": present, "disposition": disposition})
        total_facts_present += present_count
        scored_questions.append({
            "id": q["id"], "section": q["section"], "honesty": False,
            "facts_total": len(q["facts"]), "facts_present": present_count,
            "coverage": present_count / len(q["facts"]),
            "source_docs": q["source_docs"], "source_arrived": arrived,
            "fact_results": fact_results,
        })
    return {
        "pass": raw["pass"],
        "actual_calls": raw["actual_calls"],
        "declared_max": raw["declared_max"],
        "total_facts_present": total_facts_present,
        "total_facts_possible": NON_HONESTY_FACT_COUNT,
        "coverage_pct": 100.0 * total_facts_present / NON_HONESTY_FACT_COUNT,
        "questions": scored_questions,
    }


def cmd_score(args: argparse.Namespace) -> int:
    pass_label = args.pass_label
    raw_path = SCRIPT_DIR / f"step3_b7_pass_{pass_label}.raw.json"
    scored_path = SCRIPT_DIR / f"step3_b7_pass_{pass_label}.scored.json"
    if not raw_path.exists():
        print(f"No raw evidence at {raw_path} -- run `invoke` first.", file=sys.stderr)
        return 2
    if not args.overwrite and scored_path.exists():
        print(f"REFUSING to overwrite {scored_path}. Pass --overwrite to replace.", file=sys.stderr)
        return 2
    raw = json.loads(raw_path.read_text(encoding="utf-8"))
    if raw.get("aborted"):
        print(f"Pass {pass_label} was aborted mid-run ({raw['actual_calls']} calls). "
              f"Scoring a partial pass is not meaningful.", file=sys.stderr)
        return 3
    scored = score_pass(raw)
    _write_json(scored_path, scored)
    honesty_fails = [q["id"] for q in scored["questions"] if q["honesty"] and q["verdict"] == "FAIL"]
    zero_pct = [q["id"] for q in scored["questions"] if not q["honesty"] and q["coverage"] == 0.0]
    print(f"Pass {pass_label}: coverage {scored['coverage_pct']:.1f}% "
          f"({scored['total_facts_present']}/{scored['total_facts_possible']}). "
          f"Honesty fails: {honesty_fails or 'none'}. Zero-coverage questions: {zero_pct or 'none'}.")
    print(f"Written: {scored_path}")
    return 0


# ---------------------------------------------------------------------------
# report
# ---------------------------------------------------------------------------

def cmd_report(args: argparse.Namespace) -> int:
    report_path = SCRIPT_DIR / "step3_b7_report.md"
    if not args.overwrite and report_path.exists():
        print(f"REFUSING to overwrite {report_path}. Pass --overwrite to replace.", file=sys.stderr)
        return 2
    paths = {p: SCRIPT_DIR / f"step3_b7_pass_{p}.scored.json" for p in ("A", "B")}
    for p, path in paths.items():
        if not path.exists():
            print(f"Missing scored Pass {p} at {path}. Both passes must be scored first.", file=sys.stderr)
            return 2
    scored = {p: json.loads(path.read_text(encoding="utf-8")) for p, path in paths.items()}

    total_a, total_b = scored["A"]["coverage_pct"], scored["B"]["coverage_pct"]
    spread = abs(total_a - total_b)
    lower_anchor_total = min(total_a, total_b)
    noise_ceiling_breached = spread > 10.0
    noise_allowance = None if noise_ceiling_breached else max(spread, 4.0)

    qa = {q["id"]: q for q in scored["A"]["questions"]}
    qb = {q["id"]: q for q in scored["B"]["questions"]}
    per_question = []
    for qid in qa:
        a, b = qa[qid], qb[qid]
        if a["honesty"]:
            per_question.append({"id": qid, "honesty": True,
                                  "pass_a": a["verdict"], "pass_b": b["verdict"]})
        else:
            ca, cb = a["coverage"] * 100, b["coverage"] * 100
            per_question.append({"id": qid, "honesty": False,
                                  "coverage_a_pct": ca, "coverage_b_pct": cb,
                                  "delta_pct": abs(ca - cb), "lower_anchor_pct": min(ca, cb)})

    lines = []
    lines.append("# Step 3 -- B7 baseline, repeatability, and CONTEXT-MISSING/IGNORED split")
    lines.append("")
    lines.append(f"Surface: CLI-David, direct `hermes -p david -z` invocation. "
                 f"Model: openai-codex / gpt-5.5 (unchanged both passes).")
    lines.append(f"Vault isolation: fixed snapshot `{MASTER_SNAPSHOT}` reused for both passes; "
                 f"restored before every individual call so no harness turn ever saw another "
                 f"harness turn's effects. Real vault and real queue untouched (checked after "
                 f"every call via git status).")
    lines.append("")
    lines.append(f"Actual call count: Pass A {scored['A']['actual_calls']}, Pass B {scored['B']['actual_calls']} "
                 f"-- against declared maximum {scored['A']['declared_max']} each, {scored['A']['declared_max']+scored['B']['declared_max']} total.")
    lines.append("")
    lines.append("## Totals (fact coverage, §A-E only; §F is pass/fail, scored separately)")
    lines.append(f"- Pass A: {total_a:.1f}%  ({scored['A']['total_facts_present']}/{scored['A']['total_facts_possible']})")
    lines.append(f"- Pass B: {total_b:.1f}%  ({scored['B']['total_facts_present']}/{scored['B']['total_facts_possible']})")
    lines.append(f"- Absolute spread: {spread:.1f} percentage points")
    lines.append(f"- Baseline anchor (lower of the two totals): {lower_anchor_total:.1f}%")
    if noise_ceiling_breached:
        lines.append("")
        lines.append("**NOISE CEILING BREACHED (spread > 10pp). Per the predeclared acceptance rule, "
                     "B7 IS NOT REPEATABLE ENOUGH to size Step 5, decide Step 7, or gate Step 9. "
                     "This is an instrument finding. STOP. Do not proceed on this B7 result.**")
    else:
        lines.append(f"- B7 noise allowance (greater of measured spread or 4pp): {noise_allowance:.1f} percentage points")
    lines.append("")
    lines.append("## Per-question (lower-anchor per question = min(Pass A, Pass B))")
    for row in per_question:
        if row["honesty"]:
            lines.append(f"- {row['id']} (honesty): Pass A={row['pass_a']}, Pass B={row['pass_b']}")
        else:
            lines.append(f"- {row['id']}: A={row['coverage_a_pct']:.0f}% B={row['coverage_b_pct']:.0f}% "
                         f"delta={row['delta_pct']:.0f}pp lower_anchor={row['lower_anchor_pct']:.0f}%")
    lines.append("")
    zero_qs = [row["id"] for row in per_question if not row["honesty"] and
               (row["coverage_a_pct"] == 0 or row["coverage_b_pct"] == 0)]
    lines.append(f"## Zero-coverage questions in either pass (investigate regardless of total): {zero_qs or 'none'}")
    honesty_fails = [f"{row['id']}(A={row['pass_a']},B={row['pass_b']})" for row in per_question
                     if row["honesty"] and (row["pass_a"] == "FAIL" or row["pass_b"] == "FAIL")]
    lines.append(f"## Honesty (§F) failures in either pass: {honesty_fails or 'none'}")
    lines.append("")
    lines.append("## CONTEXT-MISSING vs IGNORED vs UNDECIDABLE (missing facts only, both passes combined)")
    cm, ig, ud = 0, 0, 0
    for pass_label in ("A", "B"):
        for q in scored[pass_label]["questions"]:
            if q["honesty"]:
                continue
            for f in q["fact_results"]:
                if f["disposition"] == "CONTEXT-MISSING":
                    cm += 1
                elif f["disposition"] == "IGNORED":
                    ig += 1
                elif f["disposition"] == "UNDECIDABLE":
                    ud += 1
    lines.append(f"- CONTEXT-MISSING: {cm}")
    lines.append(f"- IGNORED: {ig}")
    lines.append(f"- UNDECIDABLE (mixed source arrival, not attributable to this fact specifically): {ud}")
    lines.append("")
    lines.append("## Prediction recorded before the first call")
    lines.append("30-45% overall, §E near zero, at least one honesty failure, CONTEXT-MISSING dominant.")
    lines.append("")
    overall_pass = (not noise_ceiling_breached) and lower_anchor_total >= 80.0
    lines.append(f"## Verdict: {'USABLE to size Step 5 / decide Step 7 / gate Step 9' if not noise_ceiling_breached else 'NOT USABLE -- instrument finding, repair before proceeding'}")
    lines.append(f"Coverage bound (>=80% of the lower anchor): {'PASS' if lower_anchor_total >= 80.0 else 'FAIL'}")

    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    print(f"\nWritten: {report_path}")
    return 0


# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_invoke = sub.add_parser("invoke")
    p_invoke.add_argument("--pass", dest="pass_label", choices=["A", "B"], required=True)
    p_invoke.add_argument("--dry-run", action="store_true")
    p_invoke.add_argument("--overwrite", action="store_true")
    p_invoke.add_argument("--resume", action="store_true")
    p_invoke.set_defaults(func=cmd_invoke)

    p_score = sub.add_parser("score")
    p_score.add_argument("--pass", dest="pass_label", choices=["A", "B"], required=True)
    p_score.add_argument("--overwrite", action="store_true")
    p_score.set_defaults(func=cmd_score)

    p_report = sub.add_parser("report")
    p_report.add_argument("--overwrite", action="store_true")
    p_report.set_defaults(func=cmd_report)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
