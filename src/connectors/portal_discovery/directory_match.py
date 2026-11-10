"""All-record deterministic directory retrieval; matches are NOT verified portals."""
import csv
import hashlib
import io
import json
import math
import re
import unicodedata
from collections import Counter, defaultdict
from urllib.parse import urlsplit
from .family_contracts import public_url, identify, legacy_slug_url

LEGAL = {'gmbh','ggmbh','ag','kg','co','ohg','ug','se','ev','ltd','inc','limited','mbh','llc','kgaa'}
GENERIC = {'group','gruppe','deutschland','germany','services','service','it','holding','stadt','region','hannover'}

def words(name):
    value = unicodedata.normalize('NFKD', str(name).casefold().replace('ß','ss'))
    value = ''.join(c for c in value if not unicodedata.combining(c))
    value = re.sub(r'\be\s*\.\s*v\s*\.', ' ev ', value)
    return tuple(re.findall(r'[a-z0-9]+', value))

def key(name):
    return ' '.join(words(name))

def core(name):
    return tuple(w for w in words(name) if w not in LEGAL)

def parse_directory(raw):
    if len(raw) > 16 * 1024**2:
        raise ValueError('DIRECTORY_BYTES')
    csv.field_size_limit(8192)
    reader = csv.DictReader(io.StringIO(raw.decode('utf-8-sig', errors='strict'), newline=''))
    if not reader.fieldnames or not {'ats','name','url'}.issubset(reader.fieldnames):
        raise ValueError('DIRECTORY_SCHEMA_REQUIRES_ATS_NAME_URL')
    if len(reader.fieldnames) > 16 or len(set(reader.fieldnames)) != len(reader.fieldnames):
        raise ValueError('DIRECTORY_COLUMNS')
    rows=[]; held=[]; duplicates=0; seen=set(); raw_count=0
    for number, row in enumerate(reader, 2):
        raw_count += 1
        if raw_count > 200000:
            raise ValueError('DIRECTORY_ROWS')
        if None in row or any(v is None or len(v)>4096 for v in row.values()):
            raise ValueError('DIRECTORY_ROW_SHAPE')
        family=row['ats'].strip().lower(); name=row['name'].strip(); value=row['url'].strip()
        if not re.fullmatch(r'[a-z0-9_]{1,40}', family):
            held.append(dict(row=number,reason='INVALID_FAMILY')); continue
        url=public_url(value); conversion=None
        if not url:
            slug=row.get('slug','').strip() or value
            url=legacy_slug_url(family,slug)
            conversion='DOCUMENTED_LEGACY_SLUG_DERIVATION' if url else None
        if not url or not name or len(name)>512:
            held.append(dict(row=number,reason='URL_OR_NAME_UNUSABLE',family=family)); continue
        binding=identify(url)
        if binding and binding['family'] != {'join_com':'join'}.get(family,family):
            held.append(dict(row=number,reason='ATS_FAMILY_URL_CONFLICT',family=family)); continue
        signature=(family,key(name),url)
        if signature in seen:
            duplicates += 1; continue
        seen.add(signature)
        rows.append(dict(row_number=number,family=family,name=name,url=url,
                         slug=row.get('slug',''),conversion=conversion))
    return rows, dict(raw_rows=raw_count,usable_rows=len(rows),duplicates=duplicates,
                      held_rows=len(held),held=held,
                      directory_sha256=hashlib.sha256(raw).hexdigest())


def reconcile(corpus, rows, directory_sha):
    if len(corpus)>5000 or len({r['employer_id'] for r in corpus}) != len(corpus):
        raise ValueError('CORPUS_DENOMINATOR')
    exact=defaultdict(set); cores=defaultdict(set); inverted=defaultdict(set); tenants=defaultdict(set)
    for i,r in enumerate(rows):
        exact[key(r['name'])].add(i); cores[core(r['name'])].add(i)
        for t in set(core(r['name']))-GENERIC:
            inverted[t].add(i)
        b=identify(r['url'])
        if b:tenants[b['tenant_key']].add(i)
    records=[]; counts=Counter(); families=defaultdict(Counter); cohorts=Counter()
    for record in corpus:
        reasons=defaultdict(set); name=record['company_name']; ts=set(core(name))
        for i in exact[key(name)]:reasons[i].add('NORMALIZED_FULL_NAME')
        if len(''.join(ts))>=5 and ts-GENERIC:
            for i in cores[core(name)]:
                # Different explicit legal forms are not silently treated as equal.
                a=set(words(name))&LEGAL; b=set(words(rows[i]['name']))&LEGAL
                reasons[i].add('CORE_NAME_CANDIDATE' if not (a and b and a!=b) else 'LEGAL_FORM_CONFLICT_REVIEW')
        for h in record.get('hints',[]):
            b=identify(h.get('url',''))
            if b:
                for i in tenants[b['tenant_key']]:reasons[i].add('EXISTING_EXACT_ATS_TENANT')
        # Rare-token retrieval only; fuzzy proposals stay held and cannot auto-enroll.
        rare=sorted(ts-GENERIC,key=lambda t:(len(inverted[t]),t))[:3]
        possible=set().union(*(inverted[t] for t in rare)) if rare else set()
        for i in sorted(possible)[:1000]:
            other=set(core(rows[i]['name'])); shared=ts&other
            if len(shared-GENERIC)>=2 and len(shared)/max(1,len(ts))>=.75 and len(shared)/max(1,len(other))>=.75:
                reasons[i].add('PARTIAL_NAME_REVIEW')
        candidates=[]
        for i,why in reasons.items():
            row=rows[i]
            strong=bool(why&{'NORMALIZED_FULL_NAME','EXISTING_EXACT_ATS_TENANT','CORE_NAME_CANDIDATE'})
            candidate=dict(row,match_reasons=sorted(why),retrieval_tier='EXACT_CANDIDATE' if strong else 'REVIEW_ONLY',
                origin='external_ats_directory',original_provider='ats-scrapers',
                discovery_method='deterministic_directory_lookup',directory_sha256=directory_sha,
                authority_verified=False,portal_verified=False,production_admitted=False)
            candidates.append(candidate)
        candidates.sort(key=lambda x:(x['retrieval_tier']!='EXACT_CANDIDATE',x['family'],x['url'],x['row_number']))
        all_exact=[c for c in candidates if c['retrieval_tier']=='EXACT_CANDIDATE']
        unique_targets={(c['family'],c['url']) for c in all_exact}
        state='NO_DIRECTORY_MATCH' if not candidates else 'REVIEW_ONLY'
        if all_exact:state='EXACT_CANDIDATE_UNVERIFIED' if len(unique_targets)==1 else 'MULTIPLE_CANDIDATES_UNVERIFIED'
        counts[state]+=1
        for f in {c['family'] for c in candidates}:
            families[f]['matched_source_records']+=1
        for f in {c['family'] for c in all_exact}:
            families[f]['exact_candidate_records']+=1
            if 'SOCIAL' in record.get('source_cohorts',[]):families[f]['social_exact_candidate_records']+=1
        if all_exact and not record.get('hints'):counts['previously_no_hint_with_candidate']+=1
        cohorts.update(record.get('source_cohorts',[]) or ['UNCLASSIFIED'])
        records.append(dict(employer_id=record['employer_id'],company_name=name,
            source_cohorts=record.get('source_cohorts',[]),status=state,
            candidates=candidates[:20],candidate_count=len(candidates),truncated=len(candidates)>20,
            identity_merge_authorized=False,portal_verified=False,production_admitted=False))
    return dict(status='FULL_FROZEN_CORPUS_MATCHED_NO_PORTAL_ADMISSION',denominator=len(corpus),
        source_record_denominator_not_legal_entities=True,cohorts=dict(cohorts),counts=dict(counts),
        family_priority=sorted([dict(family=f,**v) for f,v in families.items()],
                              key=lambda x:(-x.get('exact_candidate_records',0),-x.get('social_exact_candidate_records',0),x['family'])),
        records=records,verified_new_portals=0,live_success_rate=None,target_90_met=False,
        user_acceptance='PENDING',production_admitted=False)
