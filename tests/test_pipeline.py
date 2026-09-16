"""
Unit + integration tests for the deterministic half of the pipeline
(schema, validate, confidence, review_routing, run_pipeline) plus data-
integrity checks against the actual shipped final dataset.

No network calls, no third-party dependencies -- stdlib unittest only.

Run:
    python3 -m unittest discover -s tests -v
or:
    python3 -m pytest tests/  (if pytest happens to be installed)
"""
from __future__ import annotations
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from pipeline.schema import (
    ResearchRecord, Evidence,
    AUTH_METHODS, ACCESS_MODEL, API_TYPES, API_BREADTH,
    MCP_STATUS, BUILDABILITY, CONFIDENCE, REVIEW_FLAGS,
)
from pipeline.validate import validate_record
from pipeline.confidence import assess_confidence
from pipeline.review_routing import route_for_review
from pipeline import run_pipeline


REPO_ROOT = Path(__file__).resolve().parent.parent
FINAL_DATASET_JSON = REPO_ROOT / "data" / "output" / "v2" / "final_dataset.json"
APPS_CSV = REPO_ROOT / "data" / "input" / "apps.csv"


def make_official_evidence(url="https://example-vendor.com/docs", verified=True):
    return Evidence(urls=[url], source_type="OFFICIAL", verified=verified)


def make_empty_evidence():
    return Evidence(urls=[], source_type="NONE", verified=False)


def base_record(**overrides) -> ResearchRecord:
    defaults = dict(
        app="TestApp",
        category="Test Category",
        description="A test app.",
        auth_methods=["API_KEY"],
        auth_evidence=make_official_evidence(),
        access_model="SELF_SERVE_FREE",
        access_evidence=make_official_evidence(),
        api_types=["REST"],
        api_breadth="MODERATE",
        api_evidence=make_official_evidence(),
        mcp_status="NONE_FOUND",
        mcp_evidence=make_empty_evidence(),
        buildability="READY",
        confidence="HIGH",
    )
    defaults.update(overrides)
    return ResearchRecord(**defaults)


# ---------------------------------------------------------------------------
# 1. Schema / enum validation
# ---------------------------------------------------------------------------

class TestSchemaEnums(unittest.TestCase):
    def test_controlled_vocabularies_are_nonempty_and_disjoint_from_typos(self):
        self.assertIn("OAUTH2", AUTH_METHODS)
        self.assertIn("API_KEY", AUTH_METHODS)
        self.assertIn("UNCLEAR", AUTH_METHODS)
        self.assertIn("SELF_SERVE_FREE", ACCESS_MODEL)
        self.assertIn("CONTACT_SALES", ACCESS_MODEL)
        self.assertIn("REST", API_TYPES)
        self.assertIn("OFFICIAL", MCP_STATUS)
        self.assertIn("READY", BUILDABILITY)
        self.assertIn("NEEDS_REVIEW", BUILDABILITY)
        self.assertEqual(CONFIDENCE, {"HIGH", "MEDIUM", "LOW"})

    def test_record_round_trips_through_dict(self):
        r = base_record()
        d = r.to_dict()
        r2 = ResearchRecord.from_dict(d)
        self.assertEqual(r.app, r2.app)
        self.assertEqual(r.auth_methods, r2.auth_methods)
        self.assertEqual(r.auth_evidence.urls, r2.auth_evidence.urls)
        self.assertTrue(r2.auth_evidence.verified)


# ---------------------------------------------------------------------------
# 2. validate.py -- missing evidence handling
# ---------------------------------------------------------------------------

class TestMissingEvidenceHandling(unittest.TestCase):
    def test_substantive_auth_without_evidence_is_flagged(self):
        r = base_record(auth_methods=["OAUTH2"], auth_evidence=make_empty_evidence())
        result = validate_record(r)
        self.assertIn("NO_OFFICIAL_SOURCE", result.flags)
        self.assertTrue(any("AUTH_EVIDENCE is empty" in c for c in result.corrections))

    def test_unclear_auth_does_not_require_evidence(self):
        r = base_record(auth_methods=["UNCLEAR"], auth_evidence=make_empty_evidence())
        result = validate_record(r)
        self.assertNotIn("NO_OFFICIAL_SOURCE", result.flags)
        self.assertIn("AUTH_UNCLEAR", result.flags)

    def test_third_party_evidence_on_substantive_claim_is_flagged(self):
        r = base_record(
            access_model="SELF_SERVE_FREE",
            access_evidence=Evidence(urls=["https://some-blog.com/post"], source_type="THIRD_PARTY", verified=True),
        )
        result = validate_record(r)
        self.assertIn("NO_OFFICIAL_SOURCE", result.flags)

    def test_official_but_unverified_evidence_flags_source_not_verified(self):
        r = base_record(auth_evidence=make_official_evidence(verified=False))
        result = validate_record(r)
        self.assertIn("SOURCE_NOT_VERIFIED", result.flags)


# ---------------------------------------------------------------------------
# 3. validate.py -- the hard MCP rule
# ---------------------------------------------------------------------------

class TestMcpOfficialRule(unittest.TestCase):
    def test_mcp_official_without_official_evidence_is_auto_downgraded(self):
        r = base_record(
            mcp_status="OFFICIAL",
            mcp_evidence=Evidence(urls=["https://random-blog.example/post"], source_type="THIRD_PARTY"),
        )
        validate_record(r)
        self.assertEqual(r.mcp_status, "UNCLEAR", "unsupported OFFICIAL claim must be auto-corrected, not trusted")
        self.assertIn("MCP_UNVERIFIED", r.review_flags)

    def test_mcp_official_with_real_official_evidence_is_kept(self):
        r = base_record(mcp_status="OFFICIAL", mcp_evidence=make_official_evidence())
        validate_record(r)
        self.assertEqual(r.mcp_status, "OFFICIAL")

    def test_mcp_official_official_domain_but_unverified_is_flagged_not_downgraded(self):
        r = base_record(mcp_status="OFFICIAL", mcp_evidence=make_official_evidence(verified=False))
        validate_record(r)
        # Still OFFICIAL (evidence *is* official by source_type) but flagged for human eyes.
        self.assertEqual(r.mcp_status, "OFFICIAL")
        self.assertIn("MCP_UNVERIFIED", r.review_flags)


# ---------------------------------------------------------------------------
# 4. validate.py -- buildability contradiction detection
# ---------------------------------------------------------------------------

class TestBuildabilityContradictions(unittest.TestCase):
    def test_ready_without_self_serve_access_is_overridden(self):
        r = base_record(buildability="READY", access_model="CONTACT_SALES")
        validate_record(r)
        self.assertEqual(r.buildability, "NEEDS_REVIEW")
        self.assertIn("BUILDABILITY_CONTRADICTION", r.review_flags)
        self.assertIn("[auto-flag]", r.main_blocker)

    def test_ready_without_documented_auth_is_overridden(self):
        r = base_record(buildability="READY", auth_methods=["NONE_FOUND"])
        validate_record(r)
        self.assertEqual(r.buildability, "NEEDS_REVIEW")
        self.assertIn("BUILDABILITY_CONTRADICTION", r.review_flags)

    def test_ready_with_consistent_fields_is_left_alone(self):
        r = base_record(buildability="READY")
        validate_record(r)
        self.assertEqual(r.buildability, "READY")
        self.assertNotIn("BUILDABILITY_CONTRADICTION", r.review_flags)

    def test_gated_with_non_gated_access_is_overridden(self):
        r = base_record(buildability="GATED", access_model="SELF_SERVE_FREE")
        validate_record(r)
        self.assertEqual(r.buildability, "NEEDS_REVIEW")
        self.assertIn("BUILDABILITY_CONTRADICTION", r.review_flags)

    def test_blocked_with_real_api_and_no_blocker_text_is_overridden(self):
        r = base_record(buildability="BLOCKED", api_types=["REST"], api_breadth="BROAD", main_blocker="")
        validate_record(r)
        self.assertEqual(r.buildability, "NEEDS_REVIEW")

    def test_blocked_with_stated_reason_is_left_alone(self):
        r = base_record(
            buildability="BLOCKED", api_types=["NONE_FOUND"], api_breadth="NONE",
            main_blocker="No public API exists.",
        )
        validate_record(r)
        self.assertEqual(r.buildability, "BLOCKED")


# ---------------------------------------------------------------------------
# 5. validate.py -- non-standard integration model heuristic
# ---------------------------------------------------------------------------

class TestNonStandardIntegrationModel(unittest.TestCase):
    def test_cli_tool_with_no_auth_is_flagged(self):
        r = base_record(
            auth_methods=["NONE_FOUND"], auth_evidence=make_empty_evidence(),
            api_types=["CLI"], access_model="SELF_SERVE_FREE",
            buildability="NEEDS_REVIEW",
        )
        validate_record(r)
        self.assertIn("NON_STANDARD_INTEGRATION_MODEL", r.review_flags)

    def test_normal_rest_api_is_not_flagged(self):
        r = base_record()
        validate_record(r)
        self.assertNotIn("NON_STANDARD_INTEGRATION_MODEL", r.review_flags)


# ---------------------------------------------------------------------------
# 6. confidence.py -- can only hold or downgrade, never upgrade
# ---------------------------------------------------------------------------

class TestConfidenceRules(unittest.TestCase):
    def test_clean_record_keeps_agent_confidence(self):
        r = base_record(confidence="HIGH")
        validate_record(r)
        final = assess_confidence(r)
        self.assertEqual(final, "HIGH")

    def test_hard_contradiction_forces_low_even_if_agent_said_high(self):
        r = base_record(confidence="HIGH", buildability="READY", access_model="CONTACT_SALES")
        validate_record(r)  # produces BUILDABILITY_CONTRADICTION
        final = assess_confidence(r)
        self.assertEqual(final, "LOW")

    def test_two_soft_flags_force_low(self):
        r = base_record(
            confidence="HIGH",
            auth_evidence=make_official_evidence(verified=False),  # -> SOURCE_NOT_VERIFIED
            access_conditional_gate=True,                           # -> CONDITIONAL_ACCESS
        )
        validate_record(r)
        final = assess_confidence(r)
        self.assertEqual(final, "LOW")
        self.assertIn("LOW_CONFIDENCE", r.review_flags)

    def test_one_soft_flag_caps_at_medium_not_low(self):
        r = base_record(confidence="HIGH", access_conditional_gate=True)
        validate_record(r)
        final = assess_confidence(r)
        self.assertEqual(final, "MEDIUM")

    def test_confidence_never_upgrades_beyond_agent_claim(self):
        r = base_record(confidence="MEDIUM")  # clean record, agent only claimed MEDIUM
        validate_record(r)
        final = assess_confidence(r)
        self.assertEqual(final, "MEDIUM", "pipeline must never promote MEDIUM to HIGH on its own")

    def test_invalid_agent_confidence_defaults_to_low(self):
        r = base_record(confidence="VERY_SURE")  # not a real value
        final = assess_confidence(r)
        self.assertEqual(final, "LOW")


# ---------------------------------------------------------------------------
# 7. review_routing.py -- human-review routing
# ---------------------------------------------------------------------------

class TestReviewRouting(unittest.TestCase):
    def test_clean_high_confidence_record_is_not_routed(self):
        r = base_record()
        validate_record(r)
        assess_confidence(r)
        needs_review = route_for_review(r)
        self.assertFalse(needs_review)

    def test_low_confidence_always_routes(self):
        r = base_record()
        r.final_confidence = "LOW"
        needs_review = route_for_review(r)
        self.assertTrue(needs_review)

    def test_needs_review_buildability_always_routes(self):
        r = base_record(buildability="NEEDS_REVIEW")
        r.final_confidence = "HIGH"
        needs_review = route_for_review(r)
        self.assertTrue(needs_review)

    def test_hard_route_flag_routes_even_at_high_confidence(self):
        r = base_record()
        r.final_confidence = "HIGH"
        r.review_flags = ["MCP_UNVERIFIED"]
        needs_review = route_for_review(r)
        self.assertTrue(needs_review)

    def test_source_not_verified_is_a_hard_route_flag(self):
        r = base_record()
        r.final_confidence = "HIGH"
        r.review_flags = ["SOURCE_NOT_VERIFIED"]
        self.assertTrue(route_for_review(r))


# ---------------------------------------------------------------------------
# 8. run_pipeline.py -- end-to-end integration test on a small fixture set
# ---------------------------------------------------------------------------

class TestRunPipelineIntegration(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.raw_dir = os.path.join(self.tmpdir, "raw")
        self.out_dir = os.path.join(self.tmpdir, "out")
        os.makedirs(self.raw_dir)

        clean = base_record(app="CleanApp", category="Cat A")
        contradictory = base_record(
            app="ContradictoryApp", category="Cat B",
            buildability="READY", access_model="CONTACT_SALES",
        )
        unclear = base_record(
            app="UnclearApp", category="Cat A",
            auth_methods=["UNCLEAR"], auth_evidence=make_empty_evidence(),
            access_model="UNCLEAR", access_evidence=make_empty_evidence(),
            mcp_status="UNCLEAR",
        )
        for rec, fname in [(clean, "clean.json"), (contradictory, "contradictory.json"), (unclear, "unclear.json")]:
            with open(os.path.join(self.raw_dir, fname), "w") as f:
                json.dump(rec.to_dict(), f)

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_pipeline_writes_all_three_output_files(self):
        run_pipeline.run(self.raw_dir, self.out_dir, pipeline_version="test")
        self.assertTrue(os.path.exists(os.path.join(self.out_dir, "final_dataset.csv")))
        self.assertTrue(os.path.exists(os.path.join(self.out_dir, "final_dataset.json")))
        self.assertTrue(os.path.exists(os.path.join(self.out_dir, "validation_log.json")))

    def test_pipeline_output_row_count_matches_input_count(self):
        run_pipeline.run(self.raw_dir, self.out_dir, pipeline_version="test")
        with open(os.path.join(self.out_dir, "final_dataset.json")) as f:
            data = json.load(f)
        self.assertEqual(len(data), 3)

    def test_pipeline_reruns_deterministically(self):
        run_pipeline.run(self.raw_dir, self.out_dir, pipeline_version="test")
        with open(os.path.join(self.out_dir, "final_dataset.json")) as f:
            first = json.load(f)
        run_pipeline.run(self.raw_dir, self.out_dir, pipeline_version="test")
        with open(os.path.join(self.out_dir, "final_dataset.json")) as f:
            second = json.load(f)
        self.assertEqual(first, second, "rerunning on unchanged input must produce identical output")

    def test_pipeline_corrects_the_contradictory_fixture(self):
        run_pipeline.run(self.raw_dir, self.out_dir, pipeline_version="test")
        with open(os.path.join(self.out_dir, "final_dataset.json")) as f:
            data = json.load(f)
        rec = next(r for r in data if r["app"] == "ContradictoryApp")
        self.assertEqual(rec["buildability"], "NEEDS_REVIEW")
        self.assertTrue(rec["needs_human_review"])

    def test_pipeline_leaves_clean_record_ready_and_unflagged_for_review(self):
        run_pipeline.run(self.raw_dir, self.out_dir, pipeline_version="test")
        with open(os.path.join(self.out_dir, "final_dataset.json")) as f:
            data = json.load(f)
        rec = next(r for r in data if r["app"] == "CleanApp")
        self.assertEqual(rec["buildability"], "READY")
        self.assertFalse(rec["needs_human_review"])

    def test_raises_on_empty_raw_dir(self):
        empty_dir = os.path.join(self.tmpdir, "empty")
        os.makedirs(empty_dir)
        with self.assertRaises(SystemExit):
            run_pipeline.run(empty_dir, os.path.join(self.tmpdir, "out2"), pipeline_version="test")


# ---------------------------------------------------------------------------
# 9. Data-integrity checks against the actual shipped final dataset
# ---------------------------------------------------------------------------

@unittest.skipUnless(FINAL_DATASET_JSON.exists(), "final dataset not present -- run pipeline.run_pipeline first")
class TestShippedFinalDataset(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(FINAL_DATASET_JSON) as f:
            cls.data = json.load(f)

    def test_exactly_100_apps(self):
        self.assertEqual(len(self.data), 100)

    def test_no_duplicate_app_names(self):
        names = [r["app"] for r in self.data]
        self.assertEqual(len(names), len(set(names)), "duplicate app name found in final dataset")

    def test_exactly_10_categories(self):
        cats = set(r["category"] for r in self.data)
        self.assertEqual(len(cats), 10)

    def test_categories_have_10_apps_each(self):
        from collections import Counter
        counts = Counter(r["category"] for r in self.data)
        for cat, n in counts.items():
            self.assertEqual(n, 10, f"category '{cat}' has {n} apps, expected 10")

    def test_all_enum_fields_use_controlled_vocabulary(self):
        for r in self.data:
            for a in r["auth_methods"]:
                self.assertIn(a, AUTH_METHODS, f"{r['app']}: invalid auth_method '{a}'")
            self.assertIn(r["access_model"], ACCESS_MODEL, f"{r['app']}: invalid access_model")
            for t in r["api_types"]:
                self.assertIn(t, API_TYPES, f"{r['app']}: invalid api_type '{t}'")
            self.assertIn(r["api_breadth"], API_BREADTH, f"{r['app']}: invalid api_breadth")
            self.assertIn(r["mcp_status"], MCP_STATUS, f"{r['app']}: invalid mcp_status")
            self.assertIn(r["buildability"], BUILDABILITY, f"{r['app']}: invalid buildability")
            self.assertIn(r["final_confidence"], CONFIDENCE, f"{r['app']}: invalid final_confidence")
            for fl in r["review_flags"]:
                self.assertIn(fl, REVIEW_FLAGS, f"{r['app']}: unknown review flag '{fl}'")

    def test_no_record_silently_upgraded_confidence(self):
        # Any record with 2+ CAPS_AT_MEDIUM-type flags, or a FORCES_LOW flag,
        # must not be HIGH.
        from pipeline.confidence import FORCES_LOW, CAPS_AT_MEDIUM
        for r in self.data:
            flags = set(r["review_flags"])
            if flags & FORCES_LOW:
                self.assertNotEqual(r["final_confidence"], "HIGH", f"{r['app']} has a FORCES_LOW flag but is HIGH")
            if len(flags & CAPS_AT_MEDIUM) >= 2:
                self.assertEqual(r["final_confidence"], "LOW", f"{r['app']} has 2+ soft flags but isn't LOW")

    def test_ready_records_all_use_self_serve_access(self):
        for r in self.data:
            if r["buildability"] == "READY":
                self.assertIn(
                    r["access_model"], ("SELF_SERVE_FREE", "SELF_SERVE_TRIAL"),
                    f"{r['app']} is READY but access_model={r['access_model']}",
                )

    def test_needs_human_review_matches_routing_policy(self):
        for r in self.data:
            expected = (
                r["buildability"] == "NEEDS_REVIEW"
                or r["final_confidence"] == "LOW"
                or bool(set(r["review_flags"]) & {
                    "BUILDABILITY_CONTRADICTION", "CONFLICTING_SOURCES", "MCP_UNVERIFIED",
                    "SOURCE_NOT_VERIFIED", "NON_STANDARD_INTEGRATION_MODEL",
                })
            )
            self.assertEqual(r["needs_human_review"], expected, f"{r['app']} routing mismatch")

    def test_input_apps_csv_matches_output_app_set(self):
        import csv as csv_mod
        with open(APPS_CSV) as f:
            reader = csv_mod.DictReader(f)
            input_apps = {row["app"].strip() for row in reader}
        output_apps = {r["app"].strip() for r in self.data}
        self.assertEqual(input_apps, output_apps, "final dataset app set does not match apps.csv")


if __name__ == "__main__":
    unittest.main()
