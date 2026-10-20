"""Whole observed population, independent of personal location and relevance."""
import hashlib
import json
from urllib.parse import urlsplit

BATCH_SIZE = 100
MAX_CANDIDATES = 10000  # Campaign safety budget, not a pool resource limit.


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def population(snapshots):
    groups = {}
    rejected = []
    for source, payload in sorted(snapshots.items()):
        for index, row in enumerate(payload.get("companies", [])):
            name = row.get("company_name")
            if not isinstance(name, str) or not name.strip():
                rejected.append({"source": source, "index": index, "observation": row,
                                 "reason": "COMPANY_NAME_MISSING"})
                continue
            name = " ".join(name.split())
            # Do not invent domains, strip legal forms or merge different subsidiary names.
            identity = name.casefold()
            key = digest(identity)
            item = groups.setdefault(key, {"company_key": "census-" + key, "company_name": name,
                                          "websites": [], "observations": []})
            item["observations"].append({"source": source, "row": row})
            website = row.get("website")
            try:
                url = urlsplit(website) if isinstance(website, str) else None
                if url and url.scheme == "https" and url.hostname and not url.username and not url.password:
                    if website not in item["websites"]:
                        item["websites"].append(website)
            except ValueError:
                pass  # Original value remains in the raw observation.
    candidates = sorted(groups.values(), key=lambda r: r["company_key"])
    return {"candidates": candidates, "rejected": rejected,
            "candidate_count": len(candidates),
            "factory_batch_count": (len(candidates) + BATCH_SIZE - 1) // BATCH_SIZE,
            "factory_budget_exceeded": len(candidates) > MAX_CANDIDATES,
            "personal_relevance_filter_applied": False}
