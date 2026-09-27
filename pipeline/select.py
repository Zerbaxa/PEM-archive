"""Assemble a weekly issue from scored papers and summarize the featured ones.

Usage:
  python -m pipeline.select --issue 2026-09-26                    # summarize picks with the configured LLM
  python -m pipeline.select --issue 2026-09-26 --summaries FILE   # take summaries from a JSONL file instead

Output: data/issues/<issue>.json
"""
import argparse
import collections
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

MUST_READ_N, MUST_READ_MIN, MAX_PER_TOPIC = 5, 5, 2
PICK_N, PICK_MIN = 3, 5
TRACK_N = 3

SUMMARY_PROMPT = """You write the featured entries of a weekly pediatric emergency medicine digest.
For each record, using only its title and abstract, return JSON {"results": [{"pmid", "summary": {"why_it_matters",
"design", "key_findings", "bottom_line"}, "methods_note"}]}. The summary is about 80-120 words in total, in plain
clinical English, written in your own words: do not copy sentences or long phrases from the abstract. Quote numbers
exactly as in the abstract and never add facts that are not there. methods_note is
one line naming the data source and design (e.g. "National registry + interrupted time series")."""


def clin(p):
    return (p.get('clinical') or {}).get('total', 0)


def res(p):
    return (p.get('research') or {}).get('total', 0)


def pick(papers, key, n, minimum, exclude=(), per_topic=None):
    chosen, per = [], collections.Counter()
    for p in sorted(papers, key=lambda p: (-key(p), -(clin(p) + res(p)), p['pmid'])):
        if len(chosen) == n or key(p) < minimum:
            break
        if p['pmid'] in exclude:
            continue
        topic = p['topics'][0]
        if per_topic and per[topic] >= per_topic:
            continue
        per[topic] += 1
        chosen.append(p)
    return chosen


def summarize(papers):
    from pipeline import llm
    from pipeline.fetch import ensure_abstracts
    from pipeline.score import SUMMARY, record_text
    ensure_abstracts(papers)
    schema = {'type': 'object', 'additionalProperties': False, 'required': ['results'], 'properties': {
        'results': {'type': 'array', 'items': {
            'type': 'object', 'additionalProperties': False, 'required': ['pmid', 'summary', 'methods_note'],
            'properties': {'pmid': {'type': 'string'}, 'summary': SUMMARY, 'methods_note': {'type': 'string'}}}}}}
    out = llm.complete_json(SUMMARY_PROMPT, '\n'.join(record_text(p) for p in papers), schema)
    return {str(r['pmid']): r for r in out['results']}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--issue', required=True)
    ap.add_argument('--summaries', help='JSONL with pmid/summary/methods_note, instead of calling an LLM')
    args = ap.parse_args()
    scored = json.load(open(os.path.join(ROOT, 'data', 'scored', args.issue + '.json')))
    inc = [p for p in scored['papers'] if p['include']]

    must = pick(inc, clin, MUST_READ_N, MUST_READ_MIN, per_topic=MAX_PER_TOPIC)
    featured = {p['pmid'] for p in must}
    picks = pick(inc, res, PICK_N, PICK_MIN, exclude=featured)
    featured |= {p['pmid'] for p in picks}
    both = lambda p: max(clin(p), res(p))
    pocus = pick([p for p in inc if p.get('pocus')], both, TRACK_N, 0)
    ai = pick([p for p in inc if p.get('ai')], both, TRACK_N, 0)

    need = [p for p in must + picks if not p.get('summary')]
    if need:
        if args.summaries:
            sums = {}
            for line in open(args.summaries):
                if line.strip():
                    r = json.loads(line)
                    sums[str(r['pmid'])] = r
        else:
            sums = summarize(need)
        for p in need:
            s = sums.get(p['pmid'])
            if s:
                p['summary'] = s['summary']
                p['methods_note'] = p.get('methods_note') or s.get('methods_note')

    issue = {
        'issue': args.issue, 'window': scored['window'], 'n_candidates': len(scored['papers']), 'n_included': len(inc),
        'must_read': [p['pmid'] for p in must], 'researchers_pick': [p['pmid'] for p in picks],
        'pocus': [p['pmid'] for p in pocus], 'ai': [p['pmid'] for p in ai],
        'papers': sorted(inc, key=lambda p: (-clin(p), -res(p))),
    }
    path = os.path.join(ROOT, 'data', 'issues', args.issue + '.json')
    json.dump(issue, open(path, 'w'), ensure_ascii=False, indent=1)
    print(f"must-read {len(must)}, researcher's pick {len(picks)}, pocus {len(pocus)}, ai {len(ai)}, "
          f"{len(inc)} included -> {path}")


if __name__ == '__main__':
    main()
