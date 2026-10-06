#!/usr/bin/env python3
from pathlib import Path
import importlib.util, json, sys
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('factory',ROOT/'scripts/content_factory.py');f=importlib.util.module_from_spec(spec);spec.loader.exec_module(f)
# The planner must cover the requested future range without URL or intent collisions.
# We test 50,000 plans (target article count) to keep runtime reasonable.
urls=set();intents=set()
for i in range(1,50001):
 s=f.spec_for(i)
 assert s['url'] not in urls, ('duplicate url',i,s['url'])
 assert s['intent'] not in intents, ('duplicate intent',i,s['intent'])
 urls.add(s['url']);intents.add(s['intent'])
existing=f.load_existing();accepted=[]
for i in range(1,241):
 a=f.make_article(f.spec_for(i));qa=f.score(a,existing+accepted)
 if qa['pass']:accepted.append(a)
 if len(accepted)==12:break
assert len(accepted)==12, f'Only {len(accepted)} articles passed'
for a in accepted:
 q=f.score(a,existing)
 assert q['score']>=75 and not q['critical']
 assert 900<=q['word_count']<=1800
pairs_per_run=f.CFG['pairs_per_run']
assert f.CFG['pair_size']==2 and 6<=pairs_per_run<=10, f'pairs_per_run={pairs_per_run} out of range'
facts=json.loads((ROOT/'config/business-facts.json').read_text())
assert facts['hours']=='09:00–21:00 hằng ngày'
assert facts['phone']=='0334 699 969'
print(f'PASS: 50,000 unique plans; {pairs_per_run}x2 queue; QA >= 75; NAP facts')
