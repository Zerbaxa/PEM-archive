"""Fetch candidate papers from PubMed for one weekly issue.

Usage: python -m pipeline.fetch --issue 2026-09-26 [--days 7] [--lookback 28]

Candidates are PubMed records whose Entry Date (EDAT) falls in the lookback
window and that match config/query.txt. PMIDs already seen in earlier
candidate files are skipped, so re-scanning older weeks only adds papers that
became matchable late (e.g. after MeSH indexing).
"""
import argparse
import datetime as dt
import glob
import json
import os
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EUTILS = 'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/'
TOOL = 'pem-archive'


def _call(endpoint, params):
    params = dict(params, tool=TOOL)
    if os.environ.get('NCBI_API_KEY'):
        params['api_key'] = os.environ['NCBI_API_KEY']
    data = urllib.parse.urlencode(params).encode()
    for attempt in range(5):
        try:
            with urllib.request.urlopen(EUTILS + endpoint, data=data, timeout=120) as r:
                body = r.read()
            time.sleep(0.35)  # stay under 3 requests/s without an API key
            return body
        except Exception:
            if attempt == 4:
                raise
            time.sleep(2 ** attempt)


def search(query, mindate, maxdate):
    """Return all PMIDs matching query with entry date in [mindate, maxdate]."""
    j = json.loads(_call('esearch.fcgi', dict(
        db='pubmed', term=query, retmode='json', retmax=10000,
        datetype='edat', mindate=mindate.strftime('%Y/%m/%d'), maxdate=maxdate.strftime('%Y/%m/%d'))))
    return j['esearchresult']['idlist']


def _text(el):
    return ''.join(el.itertext()).strip() if el is not None else ''


def _date(el):
    if el is None:
        return ''
    y, m, d = (_text(el.find(k)) for k in ('Year', 'Month', 'Day'))
    return '-'.join(x.zfill(2) for x in (y, m, d) if x)


def parse_article(a):
    mc = a.find('MedlineCitation')
    art = mc.find('Article')
    abstract = []
    for t in art.findall('Abstract/AbstractText'):
        label = t.get('Label')
        abstract.append((label + ': ' if label else '') + _text(t))
    authors = []
    for au in art.findall('AuthorList/Author'):
        name = (_text(au.find('LastName')) + ' ' + _text(au.find('Initials'))).strip() or _text(au.find('CollectiveName'))
        authors.append({'name': name, 'affiliation': _text(au.find('AffiliationInfo/Affiliation'))})
    ids = {i.get('IdType'): _text(i) for i in a.findall('PubmedData/ArticleIdList/ArticleId')}
    hist = {h.get('PubStatus'): _date(h) for h in a.findall('PubmedData/History/PubMedPubDate')}
    return {
        'pmid': _text(mc.find('PMID')),
        'title': _text(art.find('ArticleTitle')),
        'abstract': '\n'.join(abstract),
        'journal': _text(art.find('Journal/ISOAbbreviation')) or _text(mc.find('MedlineJournalInfo/MedlineTA')),
        'journal_full': _text(art.find('Journal/Title')),
        'pub_types': [_text(p) for p in art.findall('PublicationTypeList/PublicationType')],
        'mesh': [_text(m.find('DescriptorName')) for m in mc.findall('MeshHeadingList/MeshHeading')],
        'keywords': [_text(k) for k in mc.findall('KeywordList/Keyword')],
        'language': _text(art.find('Language')),
        'authors': authors,
        'doi': ids.get('doi', ''),
        'pmcid': ids.get('pmc', ''),
        'entry_date': hist.get('entrez') or hist.get('pubmed', ''),
    }


def fetch(pmids):
    out = []
    for i in range(0, len(pmids), 200):
        root = ET.fromstring(_call('efetch.fcgi', dict(db='pubmed', id=','.join(pmids[i:i + 200]), retmode='xml')))
        out += [parse_article(a) for a in root.findall('PubmedArticle')]
    return out


def ensure_abstracts(papers):
    """Fill in abstracts for records stored without them (see pipeline.strip)."""
    missing = [p['pmid'] for p in papers if 'abstract' not in p]
    if missing:
        got = {r['pmid']: r['abstract'] for r in fetch(missing)}
        for p in papers:
            if 'abstract' not in p:
                p['abstract'] = got.get(p['pmid'], '')
        print(f're-downloaded {len(missing)} abstracts from PubMed', flush=True)
    return papers


def history(exclude_issue):
    """PMIDs already fetched for other issues, and the earliest entry date the archive covers."""
    seen, first = set(), None
    for f in glob.glob(os.path.join(ROOT, 'data', 'candidates', '*.json')):
        if os.path.basename(f) != exclude_issue + '.json':
            d = json.load(open(f))
            seen |= {p['pmid'] for p in d['papers']}
            start = dt.date.fromisoformat(d['window'][0])
            first = start if first is None else min(first, start)
    return seen, first


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--issue', required=True, help='issue date YYYY-MM-DD (publication day)')
    ap.add_argument('--days', type=int, default=7, help='new entry window ending the day before the issue')
    ap.add_argument('--lookback', type=int, default=28, help='total re-scan window; older PMIDs already seen are skipped')
    args = ap.parse_args()
    issue = dt.date.fromisoformat(args.issue)
    end = issue - dt.timedelta(days=1)
    start = end - dt.timedelta(days=max(args.days, args.lookback) - 1)
    query = open(os.path.join(ROOT, 'config', 'query.txt')).read().strip()
    seen, first = history(args.issue)
    if first and start < first:
        start = first  # re-scan late-indexed records, but never reach back before the archive began
    pmids = [p for p in search(query, start, end) if p not in seen]
    papers = fetch(pmids)
    out = {'issue': args.issue, 'window': [start.isoformat(), end.isoformat()], 'n': len(papers), 'papers': papers}
    path = os.path.join(ROOT, 'data', 'candidates', args.issue + '.json')
    json.dump(out, open(path, 'w'), ensure_ascii=False, indent=1)
    print(f'{len(papers)} candidates ({start}..{end}, {len(seen)} previously seen skipped) -> {path}')


if __name__ == '__main__':
    main()
