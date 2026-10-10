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
next_seq=json.loads((ROOT/'data/factory-state.json').read_text()).get('next_sequence',1)
for i in range(next_seq,next_seq+240):
 a=f.make_article(f.spec_for(i));qa=f.score(a,existing+accepted)
 if qa['pass']:accepted.append(a)
 if len(accepted)==12:break
assert len(accepted)==12, f'Only {len(accepted)} articles passed'
for a in accepted:
 q=f.score(a,existing)
 assert q['score']>=75 and not q['critical']
 assert f.CFG['minimum_words']<=q['word_count']<=f.CFG['maximum_words']
pairs_per_run=f.CFG['pairs_per_run']
assert isinstance(f.CFG.get('noindex_factory_articles',False),bool), 'noindex_factory_articles must be true/false'
assert f.CFG['pair_size']==2 and 1<=pairs_per_run<=50, f'pairs_per_run={pairs_per_run} out of range'
facts=json.loads((ROOT/'config/business-facts.json').read_text())
assert facts['hours']=='08:00–17:00 hằng ngày'
assert facts['phone']=='0334 699 969'
# enabled=false must block real runs (e.g. manual workflow_dispatch) while --dry-run keeps working.
# Everything is redirected to a temp dir so the test never touches real repo state.
import contextlib, io, tempfile
saved={k:getattr(f,k) for k in ('ROOT','CFG','STATE_PATH','QUEUE_PATH','INDEX_PATH','ARTICLES','load_existing','is_operating_hours')}
try:
 with tempfile.TemporaryDirectory() as tmp:
  tmp=Path(tmp)
  (tmp/'data').mkdir();(tmp/'data/factory-state.json').write_text(json.dumps({'next_sequence':next_seq}))
  f.ROOT=tmp;f.CFG=dict(saved['CFG'],enabled=False)
  f.STATE_PATH=tmp/'data/factory-state.json';f.QUEUE_PATH=tmp/'data/factory-queue.jsonl';f.INDEX_PATH=tmp/'data/content-index.jsonl';f.ARTICLES=tmp/'content/articles'
  f.load_existing=lambda:[];f.is_operating_hours=lambda:True
  before=sorted(x.relative_to(tmp) for x in tmp.rglob('*'))
  out=io.StringIO()
  with contextlib.redirect_stdout(out):rc=f.run(limit=2,dry_run=False)
  assert rc==0 and 'Factory disabled' in out.getvalue(), out.getvalue()
  assert sorted(x.relative_to(tmp) for x in tmp.rglob('*'))==before, 'disabled run wrote files'
  out=io.StringIO()
  with contextlib.redirect_stdout(out):rc=f.run(limit=2,dry_run=True)
  assert rc==0 and '"dry_run": true' in out.getvalue(), 'dry-run must still work when disabled'
  assert sorted(x.relative_to(tmp) for x in tmp.rglob('*'))==before, 'dry-run wrote files'
finally:
 for k,v in saved.items():setattr(f,k,v)
print(f'PASS: 50,000 unique plans; {pairs_per_run}x2 queue; QA >= 75; NAP facts; enabled=false blocks real runs, dry-run allowed')
