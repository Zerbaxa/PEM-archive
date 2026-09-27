"""Build the static site into docs/ from data/issues/*.json.

Usage: python -m pipeline.build
"""
import collections
import datetime as dt
import glob
import html
import json
import os
import shutil

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'docs')
SITE_NAME = 'PEM Archive'
TAGLINE = 'Weekly must-reads in pediatric emergency medicine'

TOPIC_LABEL = {
    'resuscitation_critical': 'Resuscitation & critical care', 'trauma_injury': 'Trauma & injury',
    'infection_fever': 'Infection & fever', 'respiratory': 'Respiratory',
    'sedation_analgesia_procedures': 'Sedation, analgesia & procedures', 'mental_behavioral': 'Mental & behavioral health',
    'toxicology': 'Toxicology', 'neurology': 'Neurology', 'surgical_abdomen_gu': 'Surgical abdomen & GU',
    'cardiology': 'Cardiology', 'imaging': 'Imaging', 'ed_operations_quality': 'ED operations & quality',
    'equity_access': 'Equity & access', 'prehospital_ems': 'Prehospital & EMS',
    'education_workforce': 'Education & workforce', 'child_protection': 'Child protection', 'other': 'Other',
}
DESIGN_LABEL = {
    'rct': 'RCT', 'sr_ma': 'Systematic review / MA', 'guideline': 'Guideline', 'prospective_cohort': 'Prospective cohort',
    'retrospective_cohort': 'Retrospective cohort', 'case_control': 'Case-control', 'cross_sectional': 'Cross-sectional',
    'diagnostic_accuracy': 'Diagnostic accuracy', 'qi': 'Quality improvement', 'qualitative': 'Qualitative',
    'survey': 'Survey', 'simulation': 'Simulation', 'modeling': 'Modeling', 'narrative_review': 'Narrative review',
    'other': 'Other design',
}
STRONG_DESIGNS = {'rct', 'sr_ma', 'guideline'}
NAV = [('index.html', 'This week'), ('archive.html', 'Archive'), ('dashboard.html', 'Dashboard'), ('about.html', 'Methods')]
AI_NOTE = 'Summary and scores are AI-generated from the abstract only. Check the original article before changing practice.'

e = html.escape


def fmt_date(s):
    d = dt.date.fromisoformat(s)
    return d.strftime('%B %-d, %Y')


def page(title, body, current, prefix='', description=TAGLINE):
    cur = ' aria-current="page"'
    nav = ''.join(f'<a href="{prefix}{href}"{cur if href == current else ""}>{label}</a>' for href, label in NAV)
    return f'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(title)}</title>
<meta name="description" content="{e(description)}">
<link rel="stylesheet" href="{prefix}assets/style.css">
<script src="{prefix}assets/app.js" defer></script>
</head>
<body>
<header class="site-header"><div class="wrap">
<a class="brand" href="{prefix}index.html">{SITE_NAME} <span>· PEM literature, weekly</span></a>
<nav class="nav" aria-label="Main">{nav}</nav>
<button class="theme-btn" type="button" aria-label="Toggle dark mode">◐</button>
</div></header>
<main class="wrap">
{body}
</main>
<footer><div class="wrap">
{SITE_NAME} screens newly indexed PubMed records every week. Selections, scores and summaries are AI-assisted and
based on abstracts; they are not medical advice. Links go to PubMed. · <a href="{prefix}about.html">How it works</a>
</div></footer>
</body>
</html>
'''


def pubmed(p):
    return f"https://pubmed.ncbi.nlm.nih.gov/{p['pmid']}/"


def badges(p):
    out = []
    if p.get('design') in STRONG_DESIGNS:
        out.append(('strong', DESIGN_LABEL[p['design']]))
    elif p.get('design'):
        out.append(('', DESIGN_LABEL.get(p['design'], p['design'])))
    if p.get('multicenter'):
        out.append(('', 'Multicenter'))
    if p.get('pocus'):
        out.append(('strong', 'POCUS'))
    if p.get('ai'):
        out.append(('strong', 'AI / LLM'))
    if is_preprint(p):
        out.append(('', 'Preprint · not peer reviewed'))
    for t in p.get('topics', []):
        out.append(('', TOPIC_LABEL.get(t, t)))
    return '<div class="badges">' + ''.join(f'<span class="badge {c}">{e(t)}</span>' for c, t in out) + '</div>'


def is_preprint(p):
    return 'Preprint' in p.get('pub_types', []) or p.get('journal', '').lower().endswith('rxiv')


def score_row(p):
    c, r = p['clinical']['total'], p['research']['total']
    return (f'<div class="scores">'
            f'<span class="score">Clinical <b>{c}</b>/10 <span class="meter c" aria-hidden="true"><i style="width:{c * 10}%"></i></span></span>'
            f'<span class="score">Research <b>{r}</b>/10 <span class="meter r" aria-hidden="true"><i style="width:{r * 10}%"></i></span></span>'
            f'</div>')


def meta_line(p):
    first = p['authors'][0]['name'] if p.get('authors') else ''
    etal = ' et al.' if len(p.get('authors', [])) > 1 else ''
    doi = f' · <a href="https://doi.org/{e(p["doi"])}">DOI</a>' if p.get('doi') else ''
    return f'<p class="meta">{e(p["journal"])} · {e(first + etal)}{doi}</p>'


def card(p, rank=None, featured=False):
    head = f'<span class="rank">#{rank}</span>' if rank else ''
    parts = [f'<article class="card{" featured" if featured else ""}">', head,
             f'<h3><a href="{pubmed(p)}">{e(p["title"])}</a></h3>', meta_line(p), badges(p), score_row(p)]
    s = p.get('summary') if featured else None
    if s:
        parts.append('<dl class="summary">' + ''.join(
            f'<dt>{label}</dt><dd>{e(s.get(k, ""))}</dd>' for k, label in
            (('why_it_matters', 'Why it matters'), ('design', 'Design'), ('key_findings', 'Key findings'),
             ('bottom_line', 'Bottom line'))) + '</dl>')
    else:
        parts.append(f'<p class="one-line">{e(p.get("one_line") or "")}</p>')
    if featured and p.get('methods_note'):
        parts.append(f'<p class="methods"><b>Methods:</b> {e(p["methods_note"])}</p>')
    cr, rr = p['clinical'].get('rationale', ''), p['research'].get('rationale', '')
    parts.append(f'<details class="why"><summary>Why these scores</summary>'
                 f'<p><b>Clinical:</b> {e(cr)}</p><p><b>Research:</b> {e(rr)}</p></details>')
    if featured:
        parts.append(f'<p class="ai-note">{AI_NOTE}</p>')
    parts.append('</article>')
    return '\n'.join(parts)


def section(title, note, papers, featured=True, numbered=False, empty='Nothing met the bar this week.'):
    body = ''.join(card(p, i + 1 if numbered else None, featured) for i, p in enumerate(papers)) or f'<p class="empty">{empty}</p>'
    return f'<section><h2>{title}</h2><p class="section-note">{note}</p>{body}</section>'


def issue_body(iss):
    P = {p['pmid']: p for p in iss['papers']}
    get = lambda key: [P[i] for i in iss[key]]
    featured = set(iss['must_read']) | set(iss['researchers_pick'])
    start, end = (fmt_date(x) for x in iss['window'])
    head = f'''<div class="issue-head">
<p class="eyebrow">Issue of {fmt_date(iss["issue"])}</p>
<h1>This week in pediatric emergency medicine</h1>
<p class="lede">Papers added to PubMed {start} – {end}, screened and scored for pediatric emergency care.</p>
<ul class="stats"><li><b>{iss["n_candidates"]}</b>records screened</li><li><b>{iss["n_included"]}</b>relevant to PEM</li>
<li><b>{len(iss["must_read"])}</b>must-reads</li></ul></div>'''
    rest = [p for p in iss['papers'] if p['pmid'] not in featured]
    groups = collections.defaultdict(list)
    for p in rest:
        groups[p['topics'][0]].append(p)
    order = sorted(groups, key=lambda t: (-len(groups[t]), TOPIC_LABEL.get(t, t)))
    by_topic = ''.join(
        f'<div class="topic-group"><h3>{e(TOPIC_LABEL.get(t, t))} ({len(groups[t])})</h3><ul class="compact">' +
        ''.join(f'<li><a class="t" href="{pubmed(p)}">{e(p["title"])}</a><br><span class="m">{e(p["journal"])} · '
                f'{e(DESIGN_LABEL.get(p.get("design"), ""))} · Clinical {p["clinical"]["total"]} · Research {p["research"]["total"]}'
                f'{" · Preprint" if is_preprint(p) else ""}</span>'
                f'<p>{e(p.get("one_line") or "")}</p></li>' for p in groups[t]) + '</ul></div>' for t in order)
    return (head +
            section('★ Must-read', 'Highest Clinical Score this week: likely to affect what you do on your next shift. '
                    'At most two per topic.', get('must_read'), numbered=True) +
            section("◆ Researcher's pick", 'Highest Research Score among the rest: novel methods or questions worth '
                    'learning from.', get('researchers_pick')) +
            section('▣ POCUS in the PED', 'Point-of-care ultrasound performed by clinicians caring for children in the '
                    'ED or prehospital setting.', get('pocus'), featured=False,
                    empty='No pediatric emergency POCUS papers this week.') +
            section('▣ AI & LLMs in the PED', 'Artificial intelligence, machine learning and language models applied to '
                    'pediatric emergency care.', get('ai'), featured=False,
                    empty='No pediatric emergency AI papers this week.') +
            f'<section><h2>○ Everything else, by topic</h2><p class="section-note">{len(rest)} more papers relevant to '
            f'pediatric emergency care, ranked by Clinical Score within each topic.</p>{by_topic}</section>')


def archive_body(issues):
    rows, topics, designs = [], collections.Counter(), collections.Counter()
    for iss in issues:
        for p in iss['papers']:
            topics.update(p['topics'])
            designs[p.get('design')] += 1
            text = ' '.join([p['title'], p['journal'], p.get('one_line') or '']).lower()
            rows.append(
                f'<tr data-text="{e(text)}" data-topics="{" ".join(p["topics"])}" data-design="{e(p.get("design") or "")}">'
                f'<td><a href="issues/{iss["issue"]}.html">{iss["issue"]}</a></td>'
                f'<td><a href="{pubmed(p)}">{e(p["title"])}</a><br><span class="m">{e(p.get("one_line") or "")}</span></td>'
                f'<td>{e(p["journal"])}</td><td>{e(DESIGN_LABEL.get(p.get("design"), ""))}</td>'
                f'<td class="num">{p["clinical"]["total"]}</td><td class="num">{p["research"]["total"]}</td></tr>')
    issue_list = ''.join(
        f'<li><a class="t" href="issues/{i["issue"]}.html">Issue of {fmt_date(i["issue"])}</a><br>'
        f'<span class="m">{i["n_included"]} papers · must-read: {e(next((p["title"] for p in i["papers"] if i["must_read"] and p["pmid"] == i["must_read"][0]), "—"))}</span></li>'
        for i in issues)
    topt = ''.join(f'<option value="{t}">{e(TOPIC_LABEL.get(t, t))} ({n})</option>' for t, n in topics.most_common())
    dopt = ''.join(f'<option value="{d}">{e(DESIGN_LABEL.get(d, d))} ({n})</option>' for d, n in designs.most_common() if d)
    return f'''<div class="issue-head"><h1>Archive</h1><p class="lede">Every weekly issue and every paper that passed screening.</p></div>
<section><h2>Issues</h2><ul class="compact">{issue_list}</ul></section>
<section><h2>All papers</h2>
<div class="filters"><input id="q" type="search" placeholder="Search titles, journals, findings" aria-label="Search">
<select id="f-topic" aria-label="Topic"><option value="">All topics</option>{topt}</select>
<select id="f-design" aria-label="Design"><option value="">All designs</option>{dopt}</select></div>
<p class="section-note" id="count" aria-live="polite"></p>
<div class="table-wrap"><table id="papers"><thead><tr><th>Issue</th><th>Paper</th><th>Journal</th><th>Design</th>
<th class="num">Clin.</th><th class="num">Res.</th></tr></thead><tbody>{"".join(rows)}</tbody></table></div></section>'''


def chart_card(cid, title, sub, spec, table_head, table_rows, legend=''):
    spec['title'] = title
    rows = ''.join('<tr>' + ''.join(f'<td class="{"num" if isinstance(c, (int, float)) else ""}">{e(str(c))}</td>' for c in r) + '</tr>'
                   for r in table_rows)
    head = ''.join(f'<th class="{"num" if i else ""}">{e(h)}</th>' for i, h in enumerate(table_head))
    return f'''<div class="chart-card"><h3>{e(title)}</h3><p class="sub">{e(sub)}</p>{legend}
<div class="chart" data-chart="{cid}"></div>
<script type="application/json" id="{cid}">{json.dumps(spec)}</script>
<button class="toggle-table" type="button">Show table</button>
<div class="table-wrap" hidden><table><thead><tr>{head}</tr></thead><tbody>{rows}</tbody></table></div></div>'''


def dashboard_body(issues):
    papers = [p for i in issues for p in i['papers']]
    n = len(papers)
    jr = collections.Counter(p['journal'] for p in papers).most_common(15)
    tp = collections.Counter(p['topics'][0] for p in papers).most_common()
    cd = [sum(1 for p in papers if p['clinical']['total'] == s) for s in range(11)]
    rd = [sum(1 for p in papers if p['research']['total'] == s) for s in range(11)]
    ref = json.load(open(os.path.join(ROOT, 'data', 'reference', 'pemdatabase_journals.json')))
    legend = ('<div class="legend"><span><i style="background:var(--series-1)"></i>Clinical Score</span>'
              '<span><i style="background:var(--series-2)"></i>Research Score</span></div>')
    weeks = len(issues)
    return f'''<div class="issue-head"><h1>Dashboard</h1>
<p class="lede">Where pediatric emergency research is published and what it is about.</p>
<ul class="stats"><li><b>{weeks}</b>{"issue" if weeks == 1 else "issues"}</li><li><b>{n}</b>papers in the archive</li>
<li><b>{len(set(p["journal"] for p in papers))}</b>journals</li></ul></div>
<section><h2>This archive</h2><p class="section-note">Grows every week. With few issues so far, treat these as early counts.</p>
{chart_card('c-topic', 'Papers by main topic', 'Primary topic of each included paper', {'type': 'hbar', 'rows': [{'label': TOPIC_LABEL.get(t, t), 'value': v} for t, v in tp]}, ['Topic', 'Papers'], [[TOPIC_LABEL.get(t, t), v] for t, v in tp])}
{chart_card('c-scores', 'Score distribution', 'Number of included papers at each score (0–10)', {'type': 'columns', 'categories': [str(s) for s in range(11)], 'series': [{'name': 'Clinical Score', 'values': cd, 'color': 'var(--series-1)'}, {'name': 'Research Score', 'values': rd, 'color': 'var(--series-2)'}]}, ['Score', 'Clinical', 'Research'], [[s, cd[s], rd[s]] for s in range(11)], legend)}
{chart_card('c-journal', 'Top journals in the archive', 'Included papers per journal, top 15', {'type': 'hbar', 'labelWidth': 210, 'rows': [{'label': j, 'value': v} for j, v in jr]}, ['Journal', 'Papers'], jr)}
</section>
<section><h2>Five-year reference</h2><p class="section-note">Journals of {ref["n"]:,} PEM papers listed by
<a href="http://www.pemdatabase.org/">The Pediatric Emergency Medicine Database</a>, September 2021 – September 2026
({ref["n_journals"]} journals). Shown as aggregate counts only.</p>
{chart_card('c-ref', 'Where PEM papers were published, 2021–2026', 'Top 20 journals by number of listed papers', {'type': 'hbar', 'labelWidth': 230, 'rows': [{'label': j['journal'], 'value': j['total'], 'detail': [f"{p}: {v}" for p, v in zip(ref['periods'], j['by_period'])]} for j in ref['journals']]}, ['Journal', 'Total'] + ref['periods'], [[j['journal'], j['total']] + j['by_period'] for j in ref['journals']])}
</section>'''


def about_body():
    query = open(os.path.join(ROOT, 'config', 'query.txt')).read().strip()
    return f'''<div class="issue-head"><h1>How it works</h1><p class="lede">Every step, criterion and prompt is public.</p></div>
<div class="prose">
<h2>1. Search</h2>
<p>Each week we collect PubMed records added in the previous 7 days that match a broad pediatric emergency search,
re-scanning the previous 4 weeks for records that become searchable late. Tested against five years of listings from
The Pediatric Emergency Medicine Database, the search captured 94% of the papers listed there.</p>
<details><summary>Show the PubMed query</summary><pre>{e(query)}</pre></details>
<h2>2. Screening</h2>
<p>An AI model reads each title and abstract and keeps original research, systematic reviews, guidelines and substantive
reviews that are directly relevant to the emergency care of children. Case reports, adult-only studies, inpatient-only
questions, basic science and protocols are excluded. Typically about one in eight candidates passes.</p>
<h2>3. Two scores</h2>
<p><b>Clinical Score (0–10)</b>: practice impact (0–4), evidence strength (0–3), relevance to front-line PED care (0–2)
and clinical novelty (0–1). <b>Research Score (0–10)</b>: methodological novelty (0–4), question novelty (0–3),
rigor (0–2) and whether it generates new study ideas (0–1). Journal name and impact factor are not part of either score.</p>
<h2>4. The issue</h2>
<ul><li><b>Must-read</b>: the five highest Clinical Scores (minimum 5), at most two per topic.</li>
<li><b>Researcher's pick</b>: the three highest Research Scores among the rest (minimum 5).</li>
<li><b>POCUS</b> and <b>AI & LLMs</b>: up to three papers each, when applied to pediatric emergency care.</li>
<li>Everything else that passed screening, grouped by topic.</li></ul>
<h2>Limits</h2>
<p>Summaries are written by AI in its own words from each abstract; abstracts themselves are not reproduced here, so follow the PubMed link for the original. Scores and summaries can be wrong. Preprints are labeled as not peer reviewed. Nothing on
this site is medical advice. The full rubric is published with the source code.</p>
</div>'''


def main():
    files = sorted(glob.glob(os.path.join(ROOT, 'data', 'issues', '*.json')), reverse=True)
    issues = [json.load(open(f)) for f in files]
    if os.path.exists(OUT):
        shutil.rmtree(OUT)
    os.makedirs(os.path.join(OUT, 'issues'))
    shutil.copytree(os.path.join(ROOT, 'site', 'assets'), os.path.join(OUT, 'assets'))
    open(os.path.join(OUT, '.nojekyll'), 'w').close()
    for iss in issues:
        open(os.path.join(OUT, 'issues', iss['issue'] + '.html'), 'w').write(
            page(f'{SITE_NAME} · {fmt_date(iss["issue"])}', issue_body(iss), '', prefix='../'))
    latest = issues[0]
    open(os.path.join(OUT, 'index.html'), 'w').write(page(SITE_NAME, issue_body(latest), 'index.html'))
    open(os.path.join(OUT, 'archive.html'), 'w').write(page(f'Archive · {SITE_NAME}', archive_body(issues), 'archive.html'))
    open(os.path.join(OUT, 'dashboard.html'), 'w').write(page(f'Dashboard · {SITE_NAME}', dashboard_body(issues), 'dashboard.html'))
    open(os.path.join(OUT, 'about.html'), 'w').write(page(f'Methods · {SITE_NAME}', about_body(), 'about.html'))
    print(f'built {len(issues)} issue(s) -> {OUT}')


if __name__ == '__main__':
    main()
