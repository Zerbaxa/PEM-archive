"""Compare a calibration scoring run against a reference scoring of the same candidates.

Usage: python -m pipeline.compare REFERENCE.json CANDIDATE.json

Prints a Markdown report (also appended to $GITHUB_STEP_SUMMARY when set):
inclusion agreement, score agreement on papers both runs included, overlap of
the Must-read and Researcher's pick selections, and the largest disagreements.
"""
import json
import os
import sys

from pipeline.select import MAX_PER_TOPIC, MUST_READ_MIN, MUST_READ_N, PICK_MIN, PICK_N, clin, pick, res


def ranks(values):
    order = sorted(range(len(values)), key=lambda i: values[i])
    r = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        for k in range(i, j + 1):
            r[order[k]] = (i + j) / 2
        i = j + 1
    return r


def spearman(a, b):
    if len(a) < 3:
        return float('nan')
    ra, rb = ranks(a), ranks(b)
    ma, mb = sum(ra) / len(ra), sum(rb) / len(rb)
    cov = sum((x - ma) * (y - mb) for x, y in zip(ra, rb))
    va = sum((x - ma) ** 2 for x in ra) ** 0.5
    vb = sum((y - mb) ** 2 for y in rb) ** 0.5
    return cov / (va * vb) if va and vb else float('nan')


def selections(papers):
    inc = [p for p in papers if p['include']]
    must = pick(inc, clin, MUST_READ_N, MUST_READ_MIN, per_topic=MAX_PER_TOPIC)
    picks = pick(inc, res, PICK_N, PICK_MIN, exclude={p['pmid'] for p in must})
    return {p['pmid'] for p in must}, {p['pmid'] for p in picks}


def main():
    ref_path, cand_path = sys.argv[1:3]
    ref = {p['pmid']: p for p in json.load(open(ref_path))['papers']}
    cand_doc = json.load(open(cand_path))
    cand = {p['pmid']: p for p in cand_doc['papers']}
    common = [k for k in ref if k in cand]
    ri = {k for k in common if ref[k]['include']}
    ci = {k for k in common if cand[k]['include']}
    both = sorted(ri & ci)
    agree = sum((k in ri) == (k in ci) for k in common)
    sens = len(both) / len(ri) if ri else float('nan')
    spec = sum(1 for k in common if k not in ri and k not in ci) / (len(common) - len(ri)) if len(common) > len(ri) else float('nan')

    lines = [f"## Calibration: {cand_doc.get('scorer', cand_path)} vs reference", '',
             f'{len(common)} candidates compared.', '',
             '### Inclusion', '',
             '| | Reference | Candidate |', '|---|---|---|',
             f'| Included | {len(ri)} | {len(ci)} |', '',
             f'- Agreement: **{agree / len(common):.1%}**',
             f'- Sensitivity (reference inclusions the candidate also kept): **{sens:.1%}**',
             f'- Specificity (reference exclusions the candidate also excluded): **{spec:.1%}**', '']

    if both:
        lines += ['### Scores on papers both included', '', '| Score | Mean abs. difference | Spearman rho |', '|---|---|---|']
        for name, fn in (('Clinical', clin), ('Research', res)):
            a, b = [fn(ref[k]) for k in both], [fn(cand[k]) for k in both]
            mad = sum(abs(x - y) for x, y in zip(a, b)) / len(both)
            lines.append(f'| {name} | {mad:.2f} | {spearman(a, b):.2f} |')
        lines.append('')

    rm, rp = selections(list(ref.values()))
    cm, cp = selections(list(cand.values()))
    lines += ['### Selections', '',
              f'- Must-read overlap: **{len(rm & cm)}/{len(rm)}**',
              f"- Researcher's pick overlap: **{len(rp & cp)}/{len(rp)}**", '']

    title = lambda k: ref[k]['title'][:90]
    missed = sorted(ri - ci, key=lambda k: -clin(ref[k]))
    extra = sorted(ci - ri, key=lambda k: -clin(cand[k]))
    if missed:
        lines += ['### Included by reference, excluded by candidate', '']
        lines += [f"- {k} (ref C{clin(ref[k])}) {title(k)} — candidate: {cand[k].get('exclude_reason', '')}" for k in missed[:15]]
        lines.append('')
    if extra:
        lines += ['### Excluded by reference, included by candidate', '']
        lines += [f"- {k} (cand C{clin(cand[k])}) {title(k)} — reference: {ref[k].get('exclude_reason', '')}" for k in extra[:15]]
        lines.append('')

    report = '\n'.join(lines)
    print(report)
    if os.environ.get('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'], 'a') as f:
            f.write(report + '\n')


if __name__ == '__main__':
    main()
