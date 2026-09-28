"""Pure product catalog for JAP Classic market-discovery coverage.

Catalog membership means "we want this board represented in discovery coverage".
It does not grant connector registration, access permission, activation, ingestion,
or Product job authority.
"""
from __future__ import annotations

CORE_SENSOR_CATALOG = (
    {
        "source_name": "bundesagentur_fuer_arbeit",
        "label": "Bundesagentur für Arbeit",
        "access_status": "authorized",
        "next_action": "Active discovery source; continue bounded health and coverage checks.",
    },
    {
        "source_name": "stepstone",
        "label": "StepStone",
        "access_status": "authorized",
        "next_action": "Active discovery source; continue bounded health and coverage checks.",
    },
    {
        "source_name": "goodjobs",
        "label": "GoodJobs",
        "access_status": "withheld",
        "next_action": "Coverage target only. Connect through a separately qualified permitted interface before activation.",
    },
    {
        "source_name": "xing",
        "label": "XING Jobs",
        "access_status": "withheld",
        "next_action": "Coverage target only. Use an XING-authorized interface before activation.",
    },
    {
        "source_name": "meinestadt",
        "label": "meinestadt.de",
        "access_status": "withheld",
        "next_action": "Coverage target only. Connect only through a permitted interface; automated scraping is not authorized.",
    },
    {
        "source_name": "get_in_it",
        "label": "get in IT",
        "access_status": "withheld",
        "next_action": "Coverage target only. Obtain an authorized interface or permission before automated access.",
    },
    {
        "source_name": "jobvector",
        "label": "jobvector",
        "access_status": "withheld",
        "next_action": "Coverage target only. Use an explicitly permitted interface or provider agreement before activation.",
    },
)

CORE_SENSOR_CATALOG_BY_NAME = {
    item["source_name"]: item for item in CORE_SENSOR_CATALOG
}
CORE_SENSORS = tuple(item["source_name"] for item in CORE_SENSOR_CATALOG)
