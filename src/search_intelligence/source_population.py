"""Separate company discovery coverage from actual source delivery authority."""
from collections import Counter


def reconcile_population(rows, source_count):
    """One row per stable Census company; source names are not company counts."""
    states = Counter(row.get('factory_state') or 'NOT_CHECKED' for row in rows)
    complete = bool(rows) and not any(state in states for state in ('NOT_CHECKED', 'ASSESSING'))
    return {
        'schema': 'jap.source_population.v1',
        'census_candidate_count': len(rows),
        'factory_checked_count': sum(n for state, n in states.items() if state not in ('NOT_CHECKED', 'ASSESSING')),
        'factory_qualified_count': states['QUALIFIED'],
        'factory_states': dict(states),
        'factory_complete': complete,
        'candidate_registry_linked_count': sum(bool(row.get('registered')) for row in rows),
        'candidate_registry_unlinked_count': sum(not row.get('registered') for row in rows),
        'source_overview_count': source_count,
        'same_population': False,
        'explanation': 'Census counts distinct companies in one campaign. Sources combines registered candidates, configured connectors and discovery channels. Linked counts require an exact identity or retained Classic provenance; unlinked does not prove a company is absent. Qualification does not activate a source or prove job delivery.',
    }
