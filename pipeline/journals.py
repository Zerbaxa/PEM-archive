"""Internal journal tiers used only to rank papers for selection.

The table is private: it comes from the JOURNAL_TIERS environment variable (a
GitHub Actions secret holding the JSON) or, locally, from the git-ignored file
config/journal_tiers.json. It is never written to data files, committed, or
shown on the site. Without a table every journal is tier C (weight 0) and
selection falls back to the scores alone.
"""
import functools
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@functools.lru_cache(maxsize=1)
def _table():
    if os.environ.get('JOURNAL_TIERS'):
        return json.loads(os.environ['JOURNAL_TIERS'])
    path = os.path.join(ROOT, 'config', 'journal_tiers.json')
    if os.path.exists(path):
        return json.load(open(path))
    print('note: no journal tier table; selection uses scores only', flush=True)
    return {'weights': {'C': 0}, 'S': [], 'A': [], 'B': [], 'D': [], 'D_patterns': []}


def tier(journal):
    t = _table()
    for k in ('S', 'A', 'B', 'D'):
        if journal in t[k]:
            return k
    if any(s in journal for s in t['D_patterns']):
        return 'D'
    return 'C'


def weight(paper):
    return _table()['weights'][tier(paper.get('journal', ''))]
