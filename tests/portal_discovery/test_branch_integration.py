"""Offline regression checks for integrating the remote PoC and local rules."""
import unittest

from src.connectors.hannover_tech_registry_poc import Page, parse_links, related
from src.search_intelligence.hannover_profile_market import (
    PROFILE_SCHEMA, expand_hannover_market,
)


class BranchIntegration(unittest.TestCase):
    def test_personio_subdomain_is_a_tenant_even_at_root(self):
        self.assertTrue(related(
            "https://alpha.jobs.personio.de/",
            "https://alpha.jobs.personio.de/job/123",
        ))

    def test_personio_other_tenant_and_vendor_root_are_not_authority(self):
        self.assertFalse(related(
            "https://alpha.jobs.personio.de/", "https://beta.jobs.personio.de/job/123",
        ))
        self.assertFalse(related(
            "https://jobs.personio.de/", "https://alpha.jobs.personio.de/job/123",
        ))

    def test_observed_widget_link_reaches_candidate_selection(self):
        links, _ = parse_links(Page("https://employer.example/", 200,
            '<title>Employer</title><iframe src="https://alpha.jobs.personio.de/"></iframe>'))
        self.assertIn("https://alpha.jobs.personio.de/", links)

    def test_ambiguous_alias_does_not_merge_two_legal_employers(self):
        baseline = [
            {"company_key": "one", "company_name": "Alpha Services GmbH", "aliases": ["Common Brand"]},
            {"company_key": "two", "company_name": "Beta Services GmbH", "aliases": ["Common Brand"]},
        ]
        seed = {"schema_version": PROFILE_SCHEMA, "companies": [{
            "company_name": "Common Brand", "geography": "REGION_HANNOVER",
            "sector": "OTHER", "website": "https://common.example/",
            "source_name": "fixture", "source_url": "https://directory.example/entry",
        }]}
        with self.assertRaisesRegex(ValueError, "ambiguous.*identity"):
            expand_hannover_market(baseline, seed)
