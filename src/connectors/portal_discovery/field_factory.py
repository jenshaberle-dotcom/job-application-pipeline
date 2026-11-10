from dataclasses import asdict
from src.connectors.connector_factory import (CandidateConnectorEvidence,ConnectorFactoryCapability as Capability,
    ConnectorCapabilityRole as Role,ReuseTier,compile_connector_recipe,qualify_connector_recipe)
from .factory_candidate import CATALOG as BASELINE

CATALOG=BASELINE+tuple(Capability('ats.'+f+'.observed-inventory-detail',1,(Role.ORIGIN_INVENTORY,Role.JOB_DETAIL),
    ReuseTier.PROVIDER_FAMILY,('observed_'+f+'_full_detail',),runtime_strategy='JSONLD' if f=='join' else 'JSON_API') for f in ('join','smartrecruiters'))

def handoff(employer,portal,family,jobs,authority,receipt_hashes):
    if not authority or not jobs:return dict(status='AUTHORITY_AND_NONEMPTY_JOB_PROOF_REQUIRED',active=False,product_jobs_admitted=0)
    tag='observed_'+family+('_full_detail' if family in ('join','smartrecruiters') else '_inventory')
    evidence=CandidateConnectorEvidence(candidate_key=employer['employer_id'],company_key=employer['company_key'],
        origin_url=portal,source_type='employer_origin_ats_backed_career_site',required_roles=(Role.ORIGIN_INVENTORY,Role.JOB_DETAIL),
        fingerprint_tags=(tag,),evidence_ids=tuple(receipt_hashes),market_sensor_only=False)
    compiled=compile_connector_recipe(evidence,CATALOG)
    proof=qualify_connector_recipe(compiled.recipe,CATALOG) if compiled.recipe else None
    return dict(status='LIVE_CONTENT_FACTORY_CANDIDATE' if proof and proof.status=='PASS' else 'CAPABILITY_GAP',
        definition_proof=asdict(proof) if proof else None,recipe=asdict(compiled.recipe) if compiled.recipe else None,
        sample_jobs=len(jobs),active=False,product_jobs_admitted=0,rcc_registration=False,
        independent_root_admission_required=True,personal_acceptance='PENDING')
