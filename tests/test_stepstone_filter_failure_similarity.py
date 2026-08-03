from src.search_intelligence.stepstone_filter_failure_similarity import (
    HYPOTHESIS_ACRONYM_NAME,
    HYPOTHESIS_LENGTH_TOKEN,
    HYPOTHESIS_SYNTAX_ENCODING,
    critical_signature_match,
    directed_pair_signature,
    extract_alias_features,
    rank_alias_candidates,
    rank_candidates_by_hypothesis,
    structural_similarity,
)


def test_extracts_parser_relevant_alias_features() -> None:
    features = extract_alias_features("Technische Informationsbibliothek (TIB)")

    assert features.word_count == 3
    assert features.parenthesis_count == 2
    assert features.acronym_in_parentheses is True
    assert features.contains_acronym_token is True
    assert features.uppercase_token_count == 1
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
        hypothesis=HYPOTHESIS_SYNTAX_ENCODING,
    )

    assert ranked[0]["company_key"] == "leibniz_universitaet_hannover_luh"
    assert ranked[0]["similarity_score"] > ranked[1]["similarity_score"]
    assert ranked[0]["critical_signature"]["all_match"] is True


def test_similarity_is_structural_not_semantic() -> None:
    comparison = structural_similarity(
        "Technische Informationsbibliothek (TIB)",
        "Leibniz Universität Hannover (LUH)",
        hypothesis=HYPOTHESIS_LENGTH_TOKEN,
    )

    assert comparison["score"] >= 0.8
    assert comparison["component_scores"]["acronym_in_parentheses"] == 1.0


def test_hypothesis_rankings_do_not_collapse_distinct_failure_theories() -> None:
    candidates = [
        {
            "company_key": "adesso_business_consulting",
            "company_name": "adesso business consulting",
            "filter_alias": "adesso business consulting",
        },
        {
            "company_key": "sva",
            "company_name": "SVA System Vertrieb Alexander",
            "filter_alias": "SVA System Vertrieb Alexander",
        },
        {
            "company_key": "compugroup",
            "company_name": "CompuGroup Medical SE & Co. KGaA",
            "filter_alias": "CompuGroup Medical SE & Co. KGaA",
        },
    ]

    rankings = rank_candidates_by_hypothesis(
        seed_alias="Technische Informationsbibliothek (TIB)",
        candidates=candidates,
    )

    assert rankings[HYPOTHESIS_ACRONYM_NAME][0]["company_key"] == "sva"
    assert rankings[HYPOTHESIS_SYNTAX_ENCODING][0]["company_key"] == "compugroup"
    assert rankings[HYPOTHESIS_LENGTH_TOKEN][0]["company_key"] == "compugroup"


def test_missing_parenthetical_acronym_is_not_a_critical_signature_match() -> None:
    result = critical_signature_match(
        "Technische Informationsbibliothek (TIB)",
        "SVA System Vertrieb Alexander",
    )

    assert result["observed"]["contains_acronym_token"] is True
    assert result["observed"]["has_parentheses"] is False
    assert result["all_match"] is False


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
