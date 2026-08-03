from src.search_intelligence.stepstone_filter_failure_similarity import (
    directed_pair_signature,
    extract_alias_features,
    rank_alias_candidates,
    structural_similarity,
)


def test_extracts_parser_relevant_alias_features() -> None:
    features = extract_alias_features("Technische Informationsbibliothek (TIB)")

    assert features.word_count == 3
    assert features.parenthesis_count == 2
    assert features.acronym_in_parentheses is True
    assert features.single_token is False
    assert features.encoded_length > features.char_length


def test_parenthetical_long_alias_ranks_above_short_plain_alias() -> None:
    candidates = [
        {
            "company_key": "continental",
            "company_name": "Continental",
            "filter_alias": "Continental",
        },
        {
            "company_key": "leibniz_universitaet_hannover_luh",
            "company_name": "Leibniz Universität Hannover (LUH)",
            "filter_alias": "Leibniz Universität Hannover (LUH)",
        },
    ]

    ranked = rank_alias_candidates(
        seed_alias="Technische Informationsbibliothek (TIB)",
        candidates=candidates,
    )

    assert ranked[0]["company_key"] == "leibniz_universitaet_hannover_luh"
    assert ranked[0]["similarity_score"] > ranked[1]["similarity_score"]


def test_similarity_is_structural_not_semantic() -> None:
    comparison = structural_similarity(
        "Technische Informationsbibliothek (TIB)",
        "Leibniz Universität Hannover (LUH)",
    )

    assert comparison["score"] >= 0.7
    assert comparison["component_scores"]["acronym_in_parentheses"] == 1.0


def test_directed_pair_signature_changes_with_order() -> None:
    forward = directed_pair_signature(
        "Technische Informationsbibliothek (TIB)",
        "HDI",
    )
    reverse = directed_pair_signature(
        "HDI",
        "Technische Informationsbibliothek (TIB)",
    )

    assert forward["joined_encoded_length"] == reverse["joined_encoded_length"]
    assert forward["left_to_right_char_delta"] > 0
    assert reverse["left_to_right_char_delta"] < 0
