"""Remove PubMed abstracts from stored data before it is committed.

Abstracts are usually the publisher's copyright, so the public repository keeps
only metadata, scores and our own summaries. Scoring re-downloads abstracts
from PubMed when it needs them (pipeline.fetch.ensure_abstracts).

Usage: python -m pipeline.strip
"""
import glob
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    n = 0
    for f in glob.glob(os.path.join(ROOT, 'data', '*', '*.json')):
        d = json.load(open(f))
        papers = d.get('papers') if isinstance(d, dict) else None
        if not papers or not any('abstract' in p for p in papers):
            continue
        for p in papers:
            p.pop('abstract', None)
        json.dump(d, open(f, 'w'), ensure_ascii=False, indent=1)
        n += 1
    print(f'stripped abstracts from {n} file(s)')


if __name__ == '__main__':
    main()
