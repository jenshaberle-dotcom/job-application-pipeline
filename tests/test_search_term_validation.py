from decimal import Decimal

from src.search_intelligence.search_term_validation import SearchTermValidationRun, build_confidence


def run(term='analytics', outcome='tested_found_relevant', source_family='hdi'):
    return SearchTermValidationRun(
        suggestion_id=1,
        candidate_id=2,
        company_key='hdi',
        source_name_candidate='hdi:hannover',
        source_family_candidate=source_family,
        suggested_term=term,
        validation_scope='source_candidate',
        outcome=outcome,
        result_count=3,
        relevant_count=2,
        noise_count=0,
        evidence_url=None,
        notes=None,
        validated_by='jens',
    )


def test_confidence_counts_success_failure_and_noise() -> None:
    items = build_confidence([
        run(outcome='tested_found_relevant'),
        run(outcome='accepted'),
        run(outcome='tested_no_result'),
        run(outcome='tested_found_noise'),
    ])

    assert len(items) == 1
    assert items[0].sample_size == 4
    assert items[0].success_count == 2
    assert items[0].failure_count == 1
    assert items[0].noise_count == 1
    assert items[0].confidence_score == Decimal('50.00')
    assert items[0].confidence_level == 'medium'


def test_pending_outcomes_do_not_affect_confidence() -> None:
    items = build_confidence([run(outcome='pending')])
    assert items == []
