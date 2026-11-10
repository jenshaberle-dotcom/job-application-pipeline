"""Factory 0.9.6 capabilities plus generic inline HTML 0.11.7; no admission."""
from src.connectors.connector_factory import ConnectorFactoryCapability as Capability, ConnectorCapabilityRole as Role, ReuseTier
SOURCE_SHA256='8e1aae761ce8ca077ac52e71d0b01f26135568f8b9e021861460ae8db6ea376b'
CATALOG=(
    Capability('social.inline-heading-application',1,(Role.JOB_DETAIL,),ReuseTier.GENERIC_ORIGIN,
               ('observed_inline_heading_application',),runtime_strategy='HTML_DETAIL'),
    Capability('social.same-origin-html-inventory',1,(Role.ORIGIN_INVENTORY,),ReuseTier.GENERIC_ORIGIN,
               ('observed_same_origin_inventory',),runtime_strategy='HTML_DETAIL'),
    Capability('social.schema-jobposting',1,(Role.JOB_DETAIL,),ReuseTier.GENERIC_ORIGIN,
               ('observed_complete_jobposting',),runtime_strategy='JSONLD'),
    Capability('social.reviewed-employer-html',1,(Role.JOB_DETAIL,),ReuseTier.GENERIC_ORIGIN,
               ('observed_reviewed_html_detail',),runtime_strategy='HTML_DETAIL'),
)
