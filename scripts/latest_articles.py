"""Bounded publication feed for the aggregate /cam-nang/ page (stdlib only)."""
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
import hashlib
import argparse
import json
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
SITE = 'https://thuha.rentbikehanoi.com'


class PlainText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style'):
            self.skip += 1
        if tag in ('p', 'li', 'br', 'h2', 'h3', 'tr', 'td', 'th'):
            self.parts.append('\n')

    def handle_endtag(self, tag):
        if tag in ('script', 'style'):
            self.skip = max(0, self.skip - 1)
        if tag in ('p', 'li', 'h2', 'h3', 'tr'):
            self.parts.append('\n')

    def handle_data(self, text):
        if not self.skip:
            self.parts.append(text)


def plain(text):
    parser = PlainText()
    parser.feed(text)
    return '\n'.join(' '.join(x.split()) for x in ''.join(parser.parts).splitlines() if x.strip())


def git(root, *args):
    return subprocess.check_output(['git', '-C', str(root), *args], text=True)


def publication_history(root):
    """First source commit is auditable provenance, never mtime or current build time."""
    dates = {}
    stamp = None
    for line in git(root, 'log', '--reverse', '--diff-filter=A', '--format=DATE:%cI',
                    '--name-only', '--', 'content/articles').splitlines():
        if line.startswith('DATE:'):
            stamp = line[5:]
        elif line.startswith('content/articles/') and stamp:
            dates[line] = stamp
    legacy = {}
    for sha in git(root, 'log', '--reverse', '--format=%H', '--', 'content/posts.json').splitlines():
        stamp = git(root, 'show', '-s', '--format=%cI', sha).strip()
        try:
            posts = json.loads(git(root, 'show', f'{sha}:content/posts.json'))
        except (subprocess.CalledProcessError, json.JSONDecodeError):
            continue
        for post in posts:
            legacy.setdefault(post['url'], stamp)
    return dates, legacy


def build_feed(root=ROOT, limit=100, as_of=None):
    root = Path(root)
    dates, legacy = publication_history(root)
    posts = [(p, 'content/posts.json', legacy.get(p['url']))
             for p in json.loads((root / 'content/posts.json').read_text())]
    for path in sorted((root / 'content/articles').glob('*.json')):
        rel = path.relative_to(root).as_posix()
        posts.append((json.loads(path.read_text()), rel, dates.get(rel)))
    seen = set()
    rows = []
    excluded = []
    for post, source, first_commit in posts:
        if post.get('kind', 'article') not in ('article', 'pillar'):
            continue
        url = post['url']
        if url in seen:
            raise ValueError(f'Duplicate canonical URL: {url}')
        seen.add(url)
        published = post.get('published_at') or first_commit
        if not published:
            excluded.append(url)
            continue
        dt = datetime.fromisoformat(published.replace('Z', '+00:00'))
        if dt.tzinfo is None:
            raise ValueError(f'Publication timestamp needs timezone: {url}')
        if not (root / url.strip('/') / 'index.html').exists():
            excluded.append(url)
            continue
        sections = [{'heading': heading, 'text': plain(body)} for heading, body in post['sections']]
        text = '\n\n'.join(s['heading'] + '\n' + s['text'] for s in sections)
        rows.append({'id': post.get('id', url), 'title': post['title'], 'url': SITE + url,
                     'published_at': dt.astimezone(timezone.utc).isoformat(),
                     'date_source': 'source_timestamp' if post.get('published_at') else 'git_first_source_commit',
                     'hub': post['hub'], 'collection': '/cam-nang/', 'source_file': source,
                     'content_sha256': hashlib.sha256(text.encode()).hexdigest()})
    # A batch shares one timestamp: stable numeric source ID orders newest first.
    rows.sort(key=lambda r: (r['published_at'], int(re.sub(r'\D', '', str(r['id'])) or 0), r['url']), reverse=True)
    if as_of:
        cutoff = datetime.fromisoformat(as_of)
        if cutoff.tzinfo is None:
            raise ValueError('as_of must include timezone')
        rows = [r for r in rows if datetime.fromisoformat(r['published_at']) <= cutoff]
    feed = {'schema_version': 1, 'site': SITE, 'collection': '/cam-nang/',
            'total': len(rows), 'excluded_missing_publication': excluded,
            'articles': rows[:limit]}
    target = root / 'assets/latest-articles.json'
    target.write_text(json.dumps(feed, ensure_ascii=False, indent=2) + '\n')
    return feed


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--as-of')
    args = parser.parse_args()
    result = build_feed(as_of=args.as_of)
    print(f"Latest feed: {result['total']} dated articles, {len(result['articles'])} exported")
