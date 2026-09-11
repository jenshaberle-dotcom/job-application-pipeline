from pathlib import Path


path = Path("src/connectors/employer_origin_acquisition_v4.py")
text = path.read_text(encoding="utf-8")

old_signature = '''def _dynamic_route_candidates(
    page: PageSnapshot,
    *,
    effective_allowed_hosts: tuple[str, ...],
    fetched: set[str],
    depth: int,
) -> list[tuple[NavigationCandidate, int]]:
    """Turn bounded dynamic evidence into candidates without granting job proof."""

    details: list[tuple[NavigationCandidate, int]] = []
'''
new_signature = '''def _dynamic_route_candidates(
    page: PageSnapshot,
    *,
    effective_allowed_hosts: tuple[str, ...],
    fetched: set[str],
    depth: int,
    shadowed_urls: set[str] | None = None,
) -> list[tuple[NavigationCandidate, int]]:
    """Turn bounded dynamic evidence into candidates without displacing stronger navigation."""

    shadowed = {canonical_url(url) for url in (shadowed_urls or ())}
    details: list[tuple[NavigationCandidate, int]] = []
'''
assert text.count(old_signature) == 1
text = text.replace(old_signature, new_signature, 1)

start = text.index("def _dynamic_route_candidates(")
end = text.index("\ndef _greenhouse_root_items(", start)
dynamic_block = text[start:end]
old_guard = "if not clean or clean in fetched:\n            continue"
assert dynamic_block.count(old_guard) == 2
dynamic_block = dynamic_block.replace(
    old_guard,
    "if not clean or clean in fetched or clean in shadowed:\n            continue",
)
text = text[:start] + dynamic_block + text[end:]

old_root = '''    queue: list[tuple[NavigationCandidate, int]] = [
        (candidate, 0)
        for candidate in discover_navigation_candidates(
            root,
            allowed_hosts=effective_allowed_hosts,
            known_detail_urls=known_detail_urls,
        )
    ]
    root_dynamic_items = _dynamic_route_candidates(
        root,
        effective_allowed_hosts=effective_allowed_hosts,
        fetched=fetched,
        depth=-1,
    )
'''
new_root = '''    root_discovered = discover_navigation_candidates(
        root,
        allowed_hosts=effective_allowed_hosts,
        known_detail_urls=known_detail_urls,
    )
    queue: list[tuple[NavigationCandidate, int]] = [
        (candidate, 0) for candidate in root_discovered
    ]
    root_dynamic_items = _dynamic_route_candidates(
        root,
        effective_allowed_hosts=effective_allowed_hosts,
        fetched=fetched,
        depth=-1,
        shadowed_urls={
            candidate.url
            for candidate in root_discovered
            if candidate.discovery_source != "embedded_detail"
        },
    )
'''
assert text.count(old_root) == 1
text = text.replace(old_root, new_root, 1)

old_inner = '''        dynamic_items = _dynamic_route_candidates(
            page,
            effective_allowed_hosts=effective_allowed_hosts,
            fetched=fetched,
            depth=depth,
        )
'''
new_inner = '''        dynamic_items = _dynamic_route_candidates(
            page,
            effective_allowed_hosts=effective_allowed_hosts,
            fetched=fetched,
            depth=depth,
            shadowed_urls={
                item.url
                for item in discovered
                if item.discovery_source != "embedded_detail"
            },
        )
'''
assert text.count(old_inner) == 1
text = text.replace(old_inner, new_inner, 1)

path.write_text(text, encoding="utf-8")
print("F2_STATIC_FIRST_DYNAMIC_PATCH=READY")
