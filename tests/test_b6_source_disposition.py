"""Executable proofs for the B6 candidate-disposition/declared-input-arrival
repair in scripts/step3_b7_harness.py (source_arrived, extract_tool_reads,
score_pass's disposition assignment).

Covers the exact defects recorded in scripts/step5_step6_b7_reconciliation_audit.md
Check 5 and scripts/b7_contamination_map_and_clean_subset.md: the manifest's
`sources` key is never emitted by tools/context_assembler.py, the blind
substring-over-the-whole-manifest-blob fallback is not authoritative, and a
single irrelevant declared document arriving must not force every fact in a
multi-source question to IGNORED.

Zero model calls -- all inputs below are synthetic manifests/state.db fixtures,
never a live Hermes invocation or the production state.db.

Revisit: if tools/context_assembler.py's manifest() stops emitting `provenance`
or `actual_reads`, or the Business Brain depth-tool names change. · Last touched: 2026-09-07.
"""

from __future__ import annotations

import importlib.util
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent.parent / "scripts"
spec = importlib.util.spec_from_file_location("step3_b7_harness", SCRIPT_DIR / "step3_b7_harness.py")
step3 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(step3)  # type: ignore[union-attr]

source_arrived = step3.source_arrived
extract_tool_reads = step3.extract_tool_reads
score_pass = step3.score_pass


def _raw(question_id: str, answer: str, manifest: dict, tool_reads=()) -> dict:
    return {
        "pass": "test",
        "actual_calls": 1,
        "declared_max": 25,
        "records": [
            {
                "question_id": question_id,
                "answer": answer,
                "manifest": manifest,
                "tool_reads": list(tool_reads),
            }
        ],
    }


def _question(qid: str) -> dict:
    return next(q for q in step3.QUESTIONS if q["id"] == qid)


class SourceArrivedTests(unittest.TestCase):
    """Direct unit coverage of the B6 arrival check itself."""

    def test_arrival_via_manifest_provenance(self):
        manifest = {"provenance": ["memory/offers.md#sha256=deadbeef#route=direct_canonical_fallback"]}
        result = source_arrived(["memory/offers.md"], manifest)
        self.assertTrue(result["memory/offers.md"]["arrived"])
        self.assertEqual(result["memory/offers.md"]["evidence"], "manifest_provenance")

    def test_arrival_via_manifest_actual_reads(self):
        manifest = {"provenance": [], "actual_reads": [{"identity": "memory/offers.md", "retrieval_route": "explicit_pointer"}]}
        result = source_arrived(["memory/offers.md"], manifest)
        self.assertTrue(result["memory/offers.md"]["arrived"])
        self.assertEqual(result["memory/offers.md"]["evidence"], "manifest_actual_read")

    def test_non_arrival_is_not_guessed_true(self):
        """The never-populated `sources` key and the old whole-manifest-blob
        substring fallback must not make an absent document look arrived."""
        manifest = {
            "marker": "agentic-os/context-assembly",
            "warnings": ["memory/offers.md truncated elsewhere -- unrelated mention"],
        }
        result = source_arrived(["memory/offers.md"], manifest)
        self.assertFalse(result["memory/offers.md"]["arrived"])
        self.assertEqual(result["memory/offers.md"]["evidence"], "not_found")

    def test_excluded_provenance_tag_is_not_arrival_and_records_drop_stage(self):
        manifest = {"provenance": ["memory/offers.md#route=direct_canonical_fallback#excluded=step5_map_covers_this"]}
        result = source_arrived(["memory/offers.md"], manifest)
        self.assertFalse(result["memory/offers.md"]["arrived"])
        self.assertEqual(result["memory/offers.md"]["drop_stage"], "step5_map_covers_this")

    def test_budget_omitted_tag_is_not_arrival(self):
        manifest = {"provenance": ["memory/offers.md#route=exact_search#budget=omitted"]}
        result = source_arrived(["memory/offers.md"], manifest)
        self.assertFalse(result["memory/offers.md"]["arrived"])
        self.assertEqual(result["memory/offers.md"]["drop_stage"], "budget=omitted")

    def test_two_source_separation_each_doc_scored_independently(self):
        manifest = {"provenance": ["memory/positioning.md#sha256=abc#route=explicit_pointer"]}
        result = source_arrived(["memory/offers.md", "memory/positioning.md"], manifest)
        self.assertFalse(result["memory/offers.md"]["arrived"])
        self.assertTrue(result["memory/positioning.md"]["arrived"])

    def test_depth_tool_retrieval_counts_as_arrival_even_when_manifest_is_silent(self):
        """The confirmed E5.1 case: andrea-roberts-june-26.md was opened live via
        open_call mid-session and absent from the initial manifest."""
        manifest = {"provenance": []}
        result = source_arrived(
            ["sources/historical_calls/andrea-roberts-june-26.md"],
            manifest,
            tool_reads=frozenset({"sources/historical_calls/andrea-roberts-june-26.md"}),
        )
        self.assertTrue(result["sources/historical_calls/andrea-roberts-june-26.md"]["arrived"])
        self.assertEqual(result["sources/historical_calls/andrea-roberts-june-26.md"]["evidence"], "depth_tool")

    def test_irrelevant_source_arrival_does_not_contaminate_a_different_docs_status(self):
        manifest = {"provenance": ["memory/positioning.md#sha256=abc#route=explicit_pointer"]}
        result = source_arrived(["memory/offers.md", "memory/positioning.md"], manifest)
        # positioning.md arriving must not flip offers.md's own independent status
        self.assertFalse(result["memory/offers.md"]["arrived"])

    def test_unknown_evidence_stays_unarrived_not_guessed(self):
        """An empty manifest with no provenance/actual_reads/tool_reads at all
        must read as unarrived, never as a coin-flip guess."""
        result = source_arrived(["memory/offers.md"], {})
        self.assertFalse(result["memory/offers.md"]["arrived"])


class ExtractToolReadsTests(unittest.TestCase):
    """Depth-tool retrieval evidence extraction against a synthetic state.db
    shaped exactly like ~/.hermes/profiles/david/state.db's messages table
    (schema and tool_calls JSON confirmed live in
    scripts/step5_step6_b7_reconciliation_audit.md Check 1 and
    scripts/b7_contamination_map_and_clean_subset.md §1). Never touches the
    real production database."""

    def _build_db(self, tmpdir: Path, rows: list[tuple[str, str]]) -> Path:
        db_path = tmpdir / "state.db"
        conn = sqlite3.connect(db_path)
        conn.execute("CREATE TABLE messages (session_id TEXT, tool_calls TEXT)")
        conn.executemany("INSERT INTO messages (session_id, tool_calls) VALUES (?, ?)", rows)
        conn.commit()
        conn.close()
        return db_path

    def test_open_note_call_is_extracted(self):
        with tempfile.TemporaryDirectory() as tmp:
            tool_calls = json.dumps([
                {"function": {"name": "mcp__brain__open_note", "arguments": json.dumps({"pointer": "memory/offers.md"})}}
            ])
            db_path = self._build_db(Path(tmp), [("sess-1", tool_calls)])
            result = extract_tool_reads("sess-1", state_db_path=db_path)
            self.assertIn("memory/offers.md", result)

    def test_open_call_is_extracted_and_resolved_to_historical_calls_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            tool_calls = json.dumps([
                {"function": {"name": "mcp__brain__open_call", "arguments": json.dumps({"call_id": "mike-knapp-july-21"})}}
            ])
            db_path = self._build_db(Path(tmp), [("sess-2", tool_calls)])
            result = extract_tool_reads("sess-2", state_db_path=db_path)
            self.assertIn("sources/historical_calls/mike-knapp-july-21.md", result)

    def test_irrelevant_tool_calls_are_ignored(self):
        with tempfile.TemporaryDirectory() as tmp:
            tool_calls = json.dumps([
                {"function": {"name": "search_files", "arguments": json.dumps({"pattern": "ICP-A"})}}
            ])
            db_path = self._build_db(Path(tmp), [("sess-3", tool_calls)])
            result = extract_tool_reads("sess-3", state_db_path=db_path)
            self.assertEqual(result, frozenset())

    def test_missing_session_returns_empty_not_an_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = self._build_db(Path(tmp), [])
            result = extract_tool_reads("does-not-exist", state_db_path=db_path)
            self.assertEqual(result, frozenset())

    def test_missing_database_returns_empty_not_an_error(self):
        result = extract_tool_reads("sess-1", state_db_path=Path("/nonexistent/state.db"))
        self.assertEqual(result, frozenset())

    def test_no_session_id_returns_empty(self):
        result = extract_tool_reads(None)
        self.assertEqual(result, frozenset())


class ScorePassDispositionTests(unittest.TestCase):
    """End-to-end proofs through the real, frozen score_pass -- the exact
    consumer B7 depends on -- using synthetic raw records only."""

    def test_context_missing_when_no_declared_doc_arrived(self):
        q = _question("A1")
        raw = _raw("A1", "an answer that matches none of the facts", {"provenance": []})
        scored = score_pass(raw)
        row = next(r for r in scored["questions"] if r["id"] == "A1")
        self.assertTrue(all(f["disposition"] == "CONTEXT-MISSING" for f in row["fact_results"] if not f["present"]))

    def test_ignored_when_every_declared_doc_arrived(self):
        q = _question("A1")
        manifest = {"provenance": [f"{doc}#sha256=x#route=explicit_pointer" for doc in q["source_docs"]]}
        raw = _raw("A1", "an answer that matches none of the facts", manifest)
        scored = score_pass(raw)
        row = next(r for r in scored["questions"] if r["id"] == "A1")
        self.assertTrue(all(f["disposition"] == "IGNORED" for f in row["fact_results"] if not f["present"]))

    def test_mixed_arrival_is_fact_aware_not_forced_ignored_by_an_irrelevant_doc(self):
        """The confirmed A4 defect: positioning.md arriving must not flip
        EVERY A4 fact to IGNORED while offers.md (what A4.1-3 actually need)
        never arrived. The repaired, fact-aware mechanism separates them:
        A4.1-3 (offers.md-only, via FACT_SOURCE_OVERRIDES) read CONTEXT-MISSING;
        A4.4-6 (positioning.md-only) read IGNORED, since their own declared
        source did arrive. Neither guesses from the other's evidence."""
        q = _question("A4")
        self.assertEqual(q["source_docs"], ["memory/offers.md", "memory/positioning.md"])
        manifest = {"provenance": ["memory/positioning.md#sha256=x#route=explicit_pointer"]}
        raw = _raw("A4", "an answer that matches none of the facts", manifest)
        scored = score_pass(raw)
        row = next(r for r in scored["questions"] if r["id"] == "A4")
        by_id = {f["id"]: f["disposition"] for f in row["fact_results"]}
        for fid in ("A4.1", "A4.2", "A4.3"):
            self.assertEqual(by_id[fid], "CONTEXT-MISSING", fid)
        for fid in ("A4.4", "A4.5", "A4.6"):
            self.assertEqual(by_id[fid], "IGNORED", fid)

    def test_question_level_fallback_is_still_undecidable_for_unmapped_facts(self):
        """A question with no fact-level override at all (e.g. B4, single
        declared doc, or a question whose facts are intentionally left at the
        conservative question-level default) still gets the safe three-way
        question-level read when evidence is genuinely mixed."""
        q = _question("B3")
        # B3.6 has no FACT_SOURCE_OVERRIDES entry (confirmed ambiguous) and
        # falls back to B3's full 3-doc declared list.
        manifest = {"provenance": ["memory/ideal_clients_A.md#sha256=x#route=explicit_pointer"]}
        raw = _raw("B3", "an answer that matches none of the facts", manifest)
        scored = score_pass(raw)
        row = next(r for r in scored["questions"] if r["id"] == "B3")
        by_id = {f["id"]: f["disposition"] for f in row["fact_results"]}
        self.assertEqual(by_id["B3.6"], "UNDECIDABLE")
        # But B3.7, which IS mapped to ideal_clients.md only, is confidently
        # CONTEXT-MISSING here since only ideal_clients_A.md arrived.
        self.assertEqual(by_id["B3.7"], "CONTEXT-MISSING")

    def test_depth_tool_arrival_flows_through_score_pass(self):
        """A source absent from the initial manifest but opened via open_call
        mid-session (tool_reads) must not be scored CONTEXT-MISSING."""
        q = _question("E5")
        manifest = {"provenance": []}
        tool_reads = q["source_docs"]  # every declared doc opened via depth tool
        raw = _raw("E5", "an answer that matches none of the facts", manifest, tool_reads=tool_reads)
        scored = score_pass(raw)
        row = next(r for r in scored["questions"] if r["id"] == "E5")
        self.assertTrue(all(f["disposition"] == "IGNORED" for f in row["fact_results"] if not f["present"]))

    def test_present_facts_carry_no_disposition(self):
        q = _question("D2")
        # D2.1 requires "cci" AND "bench"; satisfy it directly.
        raw = _raw("D2", "CCI/TRACC is currently benched; Lead Gen V4.1 rebuild is benched too; don't reactivate either.", {"provenance": []})
        scored = score_pass(raw)
        row = next(r for r in scored["questions"] if r["id"] == "D2")
        d21 = next(f for f in row["fact_results"] if f["id"] == "D2.1")
        self.assertTrue(d21["present"])
        self.assertIsNone(d21["disposition"])


if __name__ == "__main__":
    unittest.main()
