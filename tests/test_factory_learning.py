import unittest
from argparse import Namespace
from unittest.mock import patch
from src.search_intelligence.factory_learning import discovery_plan, evaluate, coverage_state, public_url


class FactoryLearningTests(unittest.TestCase):
    def observation(self, key="a", urls=()):
        return dict(company_key=key, company_name=key, websites=list(urls),
                    observations=[dict(source="census")])

    def test_multiple_roles_do_not_authorize_or_block_identity(self):
        plan = discovery_plan(self.observation(urls=["https://example.com/", "https://example.com/jobs",
            "https://wrong.personio.de/job/123"]))
        self.assertEqual(3, len(plan["nodes"]))
        self.assertEqual("https://example.com/", plan["ordered_urls"][0])
        self.assertFalse(plan["automatic_identity_approval"])
        self.assertTrue(all(not n["employer_verified"] for n in plan["nodes"]))

    def test_private_and_credential_urls_not_discovery_seeds(self):
        for url in ["https://127.0.0.1/", "https://10.0.0.2/", "https://user:pass@example.com/",
                    "file:///tmp/a", "https://service.local/", "https://[::1]/"]:
            self.assertIsNone(public_url(url))

    def test_semantic_rank_cannot_authorize(self):
        plan = discovery_plan(self.observation(urls=["https://wrong.example/jobs"]),
                              semantic_scores={"https://wrong.example/jobs": 1})
        self.assertFalse(plan["automatic_identity_approval"])

    def test_empty_and_partial_are_different(self):
        self.assertEqual("VERIFIED_EMPTY", coverage_state(fetched=True, exhausted=True, jobs=0))
        self.assertEqual("PARTIAL_INVENTORY", coverage_state(fetched=True, exhausted=False, jobs=0))
        self.assertEqual("FETCH_FAILED", coverage_state(fetched=False, exhausted=False, jobs=0))

    def test_comparison_and_samples_are_stable(self):
        old = [(self.observation("a"), "QUALIFIED", {}), (self.observation("b"), "TECHNICAL_GAP", {})]
        new = [(self.observation("a"), "TECHNICAL_GAP", {}), (self.observation("b"), "QUALIFIED", {})]
        report = evaluate(new, old)
        self.assertEqual(["a"], report["comparison"]["regressions"])
        self.assertEqual(["b"], report["comparison"]["new_qualifications"])
        self.assertEqual(report, evaluate(list(reversed(new)), old))

    def test_duplicate_identity_is_rejected(self):
        row = (self.observation(), "QUALIFIED", {})
        with self.assertRaises(ValueError):
            evaluate([row, row])

    def test_family_is_detected_in_nested_evidence(self):
        row = (self.observation(), "TECHNICAL_GAP", dict(first_failure_layer="inventory",
            layers=[dict(evidence=dict(final_url="https://acme.jobs.personio.de/"))]))
        report = evaluate([row])
        self.assertEqual("personio", report["cohorts"][0]["family"])
        self.assertFalse(report["qualification_is_activation"])

    def test_census_urls_reach_bounded_discovery_with_identity(self):
        from scripts import run_origin_source_discovery_agent_v4 as discovery
        args = Namespace(candidate_identity=dict(id=42, company_key="a", company_name="Example",
            observed_urls=["https://example.com/", "https://example.com/careers"]),
            max_candidates=12, no_probe=True, target_location="", search_provider=["none"])
        with patch.object(discovery, "collect_search_results", return_value=[]), \
             patch.object(discovery, "generate_company_url_candidates_v2", return_value=()), \
             patch.object(discovery, "discover_origin_source") as run, \
             patch.object(discovery, "result_to_json", return_value={}):
            result = discovery.run_for_company(args, "a")
        seeds = run.call_args.kwargs["search_result_candidates"]
        self.assertEqual(2, len(seeds))
        self.assertEqual("a", run.call_args.kwargs["company_key"])
        self.assertEqual("hint", seeds[0].evidence["authority"])
        self.assertEqual(2, result["observed_census_url_count"])


if __name__ == "__main__":
    unittest.main()
