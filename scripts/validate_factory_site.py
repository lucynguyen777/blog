#!/usr/bin/env python3
from pathlib import Path
import json,re,sys
ROOT=Path(__file__).resolve().parents[1];errors=[]
site=json.loads((ROOT/'content/site.json').read_text())
posts=json.loads((ROOT/'content/posts.json').read_text())
for p in sorted((ROOT/'content/articles').glob('*.json')):posts.append(json.loads(p.read_text()))
urls=[p['url'] for p in posts]
if len(urls)!=len(set(urls)):errors.append('duplicate article URL')
for p in posts:
 out=ROOT/p['url'].strip('/')/'index.html'
 if not out.exists():errors.append('missing HTML '+p['url'])
 else:
  html_txt=out.read_text()
  if html_txt.count('<h1')!=1:errors.append('H1 count '+p['url'])
  if f'<link rel="canonical" href="{site["url"]}{p["url"]}">' not in html_txt:errors.append('invalid canonical '+p['url'])
  title=p.get('title','')
  if len(title)<10 or len(title)>120:errors.append(f'abnormal title length ({len(title)}): '+p['url'])
  imgs=re.findall(r'<img\s+([^>]+)>', html_txt)
  for img in imgs:
   if 'alt=' not in img:errors.append('img missing alt in '+p['url'])
index=[json.loads(x) for x in (ROOT/'data/content-index.jsonl').read_text().splitlines() if x.strip()]
if len(index)!=len([p for p in posts if p.get('kind') not in ('hub','page')]):errors.append('content index drift')
# Sitemap index -> child sitemaps: every source URL must be listed exactly once.
import xml.etree.ElementTree as ET
NS='{http://www.sitemaps.org/schemas/sitemap/0.9}'
sitemap_urls=[]
try:
 idx=ET.parse(ROOT/'sitemap.xml').getroot()
 if idx.tag!=NS+'sitemapindex':errors.append('sitemap.xml is not a sitemap index')
 for loc in idx.iter(NS+'loc'):
  child=ROOT/loc.text.removeprefix(site['url']+'/')
  if not child.exists():errors.append('missing child sitemap '+loc.text);continue
  locs=[(u.findtext(NS+'loc'),u.findtext(NS+'lastmod')) for u in ET.parse(child).getroot().iter(NS+'url')]
  if len(locs)>=50000:errors.append(f'{child.name} has {len(locs)} URLs (limit 50,000)')
  for u,lm in locs:
   if not lm:errors.append('missing lastmod '+u)
   sitemap_urls.append(u.removeprefix(site['url']))
except ET.ParseError as exc:errors.append(f'sitemap parse error: {exc}')
if len(sitemap_urls)!=len(set(sitemap_urls)):errors.append('duplicate sitemap URL')
in_sitemap=set(sitemap_urls)
for p in posts:
 if p['url'] not in in_sitemap:errors.append('not in sitemap '+p['url'])
for u in in_sitemap:
 if not (ROOT/u.strip('/')/'index.html').exists() and u!='/':errors.append('sitemap URL without HTML '+u)
if 'Sitemap: '+site['url']+'/sitemap.xml' not in (ROOT/'robots.txt').read_text():errors.append('robots.txt does not point at sitemap.xml')
if site['hours']!='08:00–17:00 hằng ngày':errors.append('NAP hours drift')
if errors:
 print('\n'.join(errors));sys.exit(1)
print(f'PASS: {len(posts)} sources, {len(index)} index rows, {len(sitemap_urls)} sitemap URLs, unique URLs, rendered HTML')
