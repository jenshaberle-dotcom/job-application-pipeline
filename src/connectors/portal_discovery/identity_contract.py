"""Employer identity must survive legal-form normalization, not word overlap."""
import re, unicodedata

LEGAL={'gmbh','ggmbh','ag','kg','co','mbh','ev','inc','ltd','limited'}

def tokens(value):
    text=unicodedata.normalize('NFKD',str(value).casefold().replace('ß','ss'))
    parts=re.findall(r'[a-z0-9]+',''.join(c for c in text if not unicodedata.combining(c) and c!='\u00ad'))
    # German registered association punctuation: e.V., e. V. and ev are equivalent.
    out=[];i=0
    while i<len(parts):
        if parts[i:i+2]==['e','v']:out.append('ev');i+=2
        else:out.append(parts[i]);i+=1
    return out

def core(value):
    parts=tokens(value)
    parts=[p for i,p in enumerate(parts) if p not in LEGAL and not (p in ('e','v') and ('e' in parts and 'v' in parts))]
    return ' '.join(parts)

def matches_name(expected,observed):
    """Keep legal suffixes when matching publisher prose; never erase Energy etc.

    Full-block normalized equality handles spelling and legal-form punctuation.
    Inside prose require the complete supplied legal name, including its suffix.
    A bare brand is not sufficient to attest the publisher of a different company.
    """
    left,right=tokens(expected),tokens(observed)
    if len(core(expected))<5:
        # Short names need the complete supplied legal name as a whole block.
        # This fixes gGiS mbH without permitting substring or bare-brand matches.
        return len(core(expected))>=3 and bool(set(left)&LEGAL) and left==right
    if left==right:return True
    if any(t in LEGAL for t in left):
        # Publisher lines may start with a role label and end with an address.
        # A mention of the company somewhere in prose is not publisher evidence.
        for prefix in ([],['herausgeber'],['anbieter'],['diensteanbieter'],['firma'],['publisher'],['company']):
            if right[:len(prefix)]==prefix and right[len(prefix):len(prefix)+len(left)]==left:
                tail=right[len(prefix)+len(left):]
                return not tail or tail[0] not in LEGAL
        return False
    return False

def structured_match(expected,observed):
    left,right=tokens(expected),tokens(observed)
    if left==right:return len(core(expected))>=5
    # An abbreviated organization name without a legal suffix may match the
    # entire distinctive name. Conflicting legal suffixes do not silently merge.
    return (len(core(expected))>=5 and core(expected)==core(observed)
            and not (set(left)&LEGAL and set(right)&LEGAL))

def identity_evidence(employer,page):
    expected=employer['company_name']
    blocks=page.identity_blocks+[' '.join(page.identity_current)]
    found=any(matches_name(expected,block) for block in blocks)
    organizations=[];stack=list(page.jsonld);count=0
    while stack and count<10000:
        value=stack.pop();count+=1
        if isinstance(value,dict):
            kind=value.get('@type',[]);kind=[kind] if isinstance(kind,str) else kind
            if isinstance(kind,list) and any(k in ('Organization','Corporation','GovernmentOrganization','LocalBusiness') for k in kind):
                organizations.extend(v for k in ('legalName','name') if isinstance((v:=value.get(k)),str))
            # A JobPosting's hiringOrganization is another explicit employer claim.
            org=value.get('hiringOrganization')
            if isinstance(org,dict) and isinstance(org.get('name'),str):organizations.append(org['name'])
            stack.extend(value.values())
        elif isinstance(value,list):stack.extend(value)
    structured=any(structured_match(expected,n) for n in organizations)
    return {'verified':found or structured,'method':'EXACT_NAME_AFTER_LEGAL_FORM_NORMALIZATION' if found else
            'STRUCTURED_EMPLOYER_NAME' if structured else 'EMPLOYER_NAME_NOT_PROVEN',
            'visible_name_match':found,'structured_name_match':structured}
