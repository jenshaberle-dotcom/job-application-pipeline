"""Reuse the JAP compiler with finite family parsers, never register production jobs."""
from dataclasses import asdict
from src.connectors.connector_factory import (CandidateConnectorEvidence, ConnectorFactoryCapability as Capability,
    ConnectorCapabilityRole as Role, ReuseTier, compile_connector_recipe, qualify_connector_recipe)
from .ats_payloads import PARSERS, parse_inventory
from .factory_catalog_baseline import CATALOG as BASELINE_CATALOG

CATALOG=BASELINE_CATALOG+tuple(Capability('ats.'+family+'.public-inventory',1,(Role.ORIGIN_INVENTORY,Role.JOB_DETAIL),
    ReuseTier.PROVIDER_FAMILY,('observed_'+family+'_inventory',),
    runtime_strategy='XML_FEED' if family=='personio' else 'JSON_API') for family in sorted(PARSERS))

def qualify_content(employer, observed_portal, response_url, content_type, body):
    parsed=parse_inventory(observed_portal,response_url,content_type,body)
    # This is a definition/fixture qualification, not compile_verified's live handoff.
    complete=parsed['inventory_complete'] and all(j['details_complete'] for j in parsed['jobs'])
    if not complete:
        return dict(status='DETAIL_OR_PAGINATION_INCOMPLETE',parsed=parsed,production_admitted=False,
                    live_job_proof=False,definition_qualified=False)
    evidence=CandidateConnectorEvidence(candidate_key=employer['employer_id'],
        company_key=employer['company_key'],origin_url=observed_portal,
        source_type='employer_origin_ats_backed_career_site',
        required_roles=(Role.ORIGIN_INVENTORY,Role.JOB_DETAIL),
        fingerprint_tags=tuple(parsed['fingerprint_tags']),evidence_ids=(parsed['body_sha256'],),
        market_sensor_only=False)
    compiled=compile_connector_recipe(evidence,CATALOG)
    proof=qualify_connector_recipe(compiled.recipe,CATALOG) if compiled.recipe else None
    return dict(status='ATS_FAMILY_DEFINITION_QUALIFIED_NOT_ADMITTED' if proof and proof.status=='PASS' else 'CAPABILITY_GAP',
        definition_qualified=bool(proof and proof.status=='PASS'),
        definition_proof=asdict(proof) if proof else None,recipe=asdict(compiled.recipe) if compiled.recipe else None,
        parsed=parsed,production_admitted=False,live_job_proof=False,
        employer_authority_required=True,profile_matching_performed=False)
