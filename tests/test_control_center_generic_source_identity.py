from scripts import product_v1_control_center_base as base


def test_source_candidate_loader_rebinds_proof_active_candidate_to_generic_identity(
    monkeypatch,
) -> None:
    queries: list[str] = []

    monkeypatch.setattr(
        base,
        "_relation_exists",
        lambda _conn, relation: relation
        in {
            "employer_origin_source_candidates",
            "generic_employer_origin_active_sources",
        },
    )
    monkeypatch.setattr(
        base,
        "_fetch_all",
        lambda _conn, query: queries.append(query) or [],
    )

    assert base._load_source_candidates(object()) == []
    assert len(queries) == 1
    sql = queries[0]
    assert "LEFT JOIN generic_employer_origin_active_sources generic_active" in sql
    assert "generic_active.candidate_id = candidate.id" in sql
    assert (
        "coalesce(generic_active.source_name, candidate.source_name_candidate) AS source_name"
        in sql
    )
    assert "THEN 'employer_origin_career_site'" in sql


def test_source_candidate_loader_keeps_legacy_identity_without_projection(
    monkeypatch,
) -> None:
    queries: list[str] = []

    monkeypatch.setattr(
        base,
        "_relation_exists",
        lambda _conn, relation: relation == "employer_origin_source_candidates",
    )
    monkeypatch.setattr(
        base,
        "_fetch_all",
        lambda _conn, query: queries.append(query) or [],
    )

    assert base._load_source_candidates(object()) == []
    sql = queries[0]
    assert "generic_employer_origin_active_sources" not in sql
    assert "candidate.source_name_candidate AS source_name" in sql
