#!/usr/bin/env python3
from pathlib import Path
import json,re,sys
ROOT=Path(__file__).resolve().parents[1];errors=[]
posts=json.loads((ROOT/'content/posts.json').read_text())
for p in sorted((ROOT/'content/articles').glob('*.json')):posts.append(json.loads(p.read_text()))
urls=[p['url'] for p in posts]
if len(urls)!=len(set(urls)):errors.append('duplicate article URL')
for p in posts:
 out=ROOT/p['url'].strip('/')/'index.html'
 if not out.exists():errors.append('missing HTML '+p['url'])
 elif out.read_text().count('<h1')!=1:errors.append('H1 count '+p['url'])
index=[json.loads(x) for x in (ROOT/'data/content-index.jsonl').read_text().splitlines() if x.strip()]
if len(index)!=len([p for p in posts if p.get('kind') not in ('hub','page')]):errors.append('content index drift')
site=json.loads((ROOT/'content/site.json').read_text())
if site['hours']!='09:00–21:00 hằng ngày':errors.append('NAP hours drift')
if errors:
 print('\n'.join(errors));sys.exit(1)
print(f'PASS: {len(posts)} sources, {len(index)} index rows, unique URLs, rendered HTML')
