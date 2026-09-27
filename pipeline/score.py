"""Screen and score one issue's candidates with an LLM, using config/rubric.md.

Usage:
  python -m pipeline.score --issue 2026-09-26                 # call the configured LLM
  python -m pipeline.score --issue 2026-09-26 --import work/results   # merge JSONL results produced elsewhere

Output: data/scored/<issue>.json  (candidate metadata + screening/scoring fields)
"""
import argparse
import glob
import json
import os
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BATCH = int(os.environ.get('SCORE_BATCH', '8'))
WORKERS = int(os.environ.get('SCORE_WORKERS', '4'))

TOPICS = ['resuscitation_critical', 'trauma_injury', 'infection_fever', 'respiratory',
          'sedation_analgesia_procedures', 'mental_behavioral', 'toxicology', 'neurology',
          'surgical_abdomen_gu', 'cardiology', 'imaging', 'ed_operations_quality', 'equity_access',
          'prehospital_ems', 'education_workforce', 'child_protection', 'other']
DESIGNS = ['rct', 'sr_ma', 'guideline', 'prospective_cohort', 'retrospective_cohort', 'case_control',
           'cross_sectional', 'diagnostic_accuracy', 'qi', 'qualitative', 'survey', 'simulation',
           'modeling', 'narrative_review', 'other']
CLIN_MAX = {'impact': 4, 'evidence': 3, 'relevance': 2, 'novelty': 1}
RES_MAX = {'method_novelty': 4, 'question_novelty': 3, 'rigor': 2, 'generativity': 1}


def _nullable(s):
    return {'anyOf': [s, {'type': 'null'}]}


def _scores(keys):
    props = {k: {'type': 'integer'} for k in keys}
    props['rationale'] = {'type': 'string'}
    return _nullable({'type': 'object', 'properties': props, 'required': list(props), 'additionalProperties': False})


STR = {'type': 'string'}
SUMMARY = {'type': 'object', 'additionalProperties': False,
           'properties': {k: STR for k in ('why_it_matters', 'design', 'key_findings', 'bottom_line')},
           'required': ['why_it_matters', 'design', 'key_findings', 'bottom_line']}
RECORD = {
    'type': 'object', 'additionalProperties': False,
    'properties': {
        'pmid': STR, 'include': {'type': 'boolean'}, 'ed_link': _nullable(STR), 'exclude_reason': STR,
        'topics': _nullable({'type': 'array', 'items': {'type': 'string', 'enum': TOPICS}}),
        'design': _nullable({'type': 'string', 'enum': DESIGNS}),
        'multicenter': _nullable({'type': 'boolean'}),
        'pocus': _nullable({'type': 'boolean'}), 'ai': _nullable({'type': 'boolean'}),
        'clinical': _scores(CLIN_MAX), 'research': _scores(RES_MAX),
        'one_line': _nullable(STR), 'summary': _nullable(SUMMARY), 'methods_note': _nullable(STR),
    },
}
RECORD['required'] = list(RECORD['properties'])
SCHEMA = {'type': 'object', 'additionalProperties': False,
          'properties': {'results': {'type': 'array', 'items': RECORD}}, 'required': ['results']}


def record_text(p):
    return (f"=== PMID {p['pmid']}\nTITLE: {p['title']}\nJOURNAL: {p['journal']}\n"
            f"TYPES: {', '.join(p['pub_types'])}\nABSTRACT: {p.get('abstract') or '(no abstract)'}\n")


def normalize(r):
    """Clamp subscores to their ranges and add totals, so downstream code can trust the numbers."""
    r = dict(r)
    r['include'] = bool(r.get('include'))
    if r['include'] and 'ed_link' in r and not (r['ed_link'] or '').strip():
        # rubric v0.2 requires an explicit ED link for inclusion (older results have no such field)
        r['include'], r['exclude_reason'] = False, 'no ED link given'
    for key, mx in (('clinical', CLIN_MAX), ('research', RES_MAX)):
        s = r.get(key) if r['include'] else None
        if s:
            for k, m in mx.items():
                s[k] = max(0, min(m, int(s.get(k) or 0)))
            s['total'] = sum(s[k] for k in mx)
        r[key] = s
    r['topics'] = [t for t in (r.get('topics') or []) if t in TOPICS] or (['other'] if r['include'] else [])
    return r


def _ask(llm, system, chunk):
    user = ('Screen and score these records. Return {"results": [...]} with exactly one '
            'object per record, in the same order.\n\n' + '\n'.join(record_text(p) for p in chunk))
    res = llm.complete_json(system, user, SCHEMA)
    rows = res.get('results', []) if isinstance(res, dict) else res
    wanted = {p['pmid'] for p in chunk}
    return {str(r['pmid']): r for r in rows if isinstance(r, dict) and str(r.get('pmid')) in wanted}


def _score_chunk(llm, system, chunk, label):
    """One batch: retry once as a whole, then score any skipped records one by one."""
    got = {}
    for attempt in (1, 2):
        try:
            got.update(_ask(llm, system, chunk))
            break
        except Exception as e:  # malformed JSON or API failure
            print(f'{label} attempt {attempt} failed: {type(e).__name__}: {str(e)[:200]}', flush=True)
    for p in chunk:
        if p['pmid'] not in got:
            try:
                got.update(_ask(llm, system, [p]))
            except Exception as e:
                print(f'record {p["pmid"]} failed: {type(e).__name__}: {str(e)[:200]}', flush=True)
    return got


def score_llm(papers):
    """Score in batches, WORKERS requests at a time. Records that still fail are treated as excluded."""
    from concurrent.futures import ThreadPoolExecutor, as_completed
    from pipeline import llm
    from pipeline.fetch import ensure_abstracts
    ensure_abstracts(papers)
    system = open(os.path.join(ROOT, 'config', 'rubric.md')).read()
    chunks = [papers[i:i + BATCH] for i in range(0, len(papers), BATCH)]
    out, done, started = {}, 0, time.time()
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        futs = [pool.submit(_score_chunk, llm, system, c, f'batch {n + 1}') for n, c in enumerate(chunks)]
        for f in as_completed(futs):
            out.update(f.result())
            done += 1
            print(f'{done}/{len(chunks)} batches, {len(out)} records, {time.time() - started:.0f}s', flush=True)
    failed = [p['pmid'] for p in papers if p['pmid'] not in out]
    if failed:
        print(f'warning: {len(failed)} records could not be scored and are treated as excluded: {failed}')
        out.update({pm: {'pmid': pm, 'include': False, 'exclude_reason': 'scoring failed'} for pm in failed})
    return out


def load_imported(folder):
    out = {}
    for f in sorted(glob.glob(os.path.join(folder, '*.jsonl'))):
        for line in open(f):
            if line.strip():
                r = json.loads(line)
                out[str(r['pmid'])] = r
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--issue', required=True)
    ap.add_argument('--import', dest='import_dir', help='folder of JSONL results to merge instead of calling an LLM')
    ap.add_argument('--out', help='write here instead of data/scored/<issue>.json (for calibration runs)')
    args = ap.parse_args()
    cand = json.load(open(os.path.join(ROOT, 'data', 'candidates', args.issue + '.json')))
    papers = cand['papers']
    results = load_imported(args.import_dir) if args.import_dir else score_llm(papers)
    missing = [p['pmid'] for p in papers if p['pmid'] not in results]
    if missing:
        raise SystemExit(f'{len(missing)} candidates have no result, e.g. {missing[:5]}')
    scored = []
    for p in papers:
        r = normalize(results[p['pmid']])
        r.pop('pmid', None)
        scored.append({**p, **r})
    out = {k: v for k, v in cand.items() if k != 'papers'}
    if args.import_dir:
        out['scorer'] = 'import:' + args.import_dir
    else:
        from pipeline import llm
        out['scorer'] = f'{llm.PROVIDER}:{llm.model_name()}'
    out['papers'] = scored
    path = args.out or os.path.join(ROOT, 'data', 'scored', args.issue + '.json')
    json.dump(out, open(path, 'w'), ensure_ascii=False, indent=1)
    inc = [p for p in scored if p['include']]
    print(f'{len(inc)}/{len(scored)} included -> {path}')


if __name__ == '__main__':
    main()
