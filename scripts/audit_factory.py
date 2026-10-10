#!/usr/bin/env python3
"""Read-only audit of factory articles (content/articles/*.json).

Writes reports/factory-audit.csv (one row per article) and
reports/factory-audit.md (summary).  Changes nothing on the site: the
decisions are proposals for the owner to approve.

Decisions
  BO        topic does not fit the vehicle (e.g. spark plugs on a bicycle)
  GOP       same family + topic + subject as a kept article; merge into it
  GIU       representative of its group; keep
  GIU_SUA   representative, but contains money amounts not in
            config/business-facts.json; fix before keeping
  XEM_LAI   representative of a legal topic; keep only after legal review

Orphans: committed index.html files that the current build no longer
produces (not in any source, not in the sitemap).

Usage: python3 scripts/audit_factory.py [--no-orphans]
"""
import ast, collections, csv, glob, html, json, re, shutil, subprocess, sys, tempfile, zlib
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'reports'
MONEY = ['/thue-xe-may/ha-noi/', '/thue-xe-dien/ha-noi/', '/thue-xe-50cc/ha-noi/', '/bang-gia/',
         '/thue-xe-may/ha-noi/theo-thang/', '/thue-xe-may/long-bien/']

# Amounts the shop has confirmed (config/business-facts.json + content/faq.json).
ALLOWED_AMOUNTS = {
    '20.000', '50.000', '100.000', '150.000', '200.000', '600.000', '700.000', '800.000',
    '1.000.000', '1.200.000', '1.500.000', '1.800.000', '2.000.000', '5.000.000',
    '150 nghìn', '200 nghìn', '600 nghìn', '700 nghìn', '800 nghìn',
    '1 triệu', '1,2 triệu', '1,5 triệu', '1,8 triệu', '2 triệu', '5 triệu',
}
OUTDATED = {'30.000đ/giờ': 'phí quá giờ cũ 30.000đ/giờ', '18 đến dưới 20 tuổi': 'chính sách tuổi 50cc cũ'}

# Vehicle class from the intent's subject.
def vclass(subject):
    s = subject.lower()
    if 'xe đạp' in s: return 'xe_dap'
    if 'vinfast' in s or 'điện' in s: return 'xe_dien'
    if any(k in s for k in ('vision', 'lead', 'air blade', 'grande', 'tay ga', 'xe ga')): return 'xe_ga'
    return 'xe_so'  # wave, sirius, winner x, exciter, 50cc

LIQUID_COOLED = ('air blade', 'lead', 'winner x', 'exciter')
# xe-info topic -> vehicle classes it applies to (None = all)
TOPIC_FIT = {
    'thay-dau-nhot': {'xe_so', 'xe_ga'}, 'thay-loc-gio-dong-co': {'xe_so', 'xe_ga'},
    'thay-the-bugi': {'xe_so', 'xe_ga'}, 'ky-nang-tiet-kiem-nhien-lieu': {'xe_so', 'xe_ga'},
    'khoi-dong-buoi-sang-lanh': {'xe_so', 'xe_ga'}, 've-sinh-kim-phun-fi': {'xe_so', 'xe_ga'},
    'kiem-tra-nuoc-lam-mat': 'liquid', 'thay-day-curoa': {'xe_ga'}, 'thay-nhot-hop-so-lap': {'xe_ga'},
    'cham-soc-pin-xe-dien': {'xe_dien'}, 've-sinh-xich-lip': {'xe_so', 'xe_dap'},
    'kiem-tra-ac-quy': {'xe_so', 'xe_ga', 'xe_dien'},
}
ENGINE_WORDS = ('bugi', 'nhớt', 'chế hòa khí', 'kim phun', 'lọc gió động cơ', 'bình xăng')


def sections(a):
    s = a['sections']
    return ast.literal_eval(s) if isinstance(s, str) else s


def plain(a):
    body = ' '.join(t + ' ' + b for t, b in sections(a))
    return re.sub(r'\s+', ' ', re.sub('<[^>]+>', ' ', html.unescape(body)))


def fit_problem(fam, topic, subject, text):
    if fam != 'xe-info':
        return ''
    vc = vclass(subject)
    rule = TOPIC_FIT.get(topic)
    if rule == 'liquid' and not any(k in subject.lower() for k in LIQUID_COOLED):
        return f'"{topic}" không áp dụng cho xe làm mát bằng gió ({subject})'
    if isinstance(rule, set) and vc not in rule:
        return f'"{topic}" không áp dụng cho {subject}'
    if vc in ('xe_dap', 'xe_dien'):
        hits = [w for w in ENGINE_WORDS if w in text.lower()]
        if hits:
            return f'bài {subject} nói về {", ".join(hits)}'
    return ''


def qa_scores():
    best = {}
    for line in (ROOT / 'data/factory-queue.jsonl').read_text().splitlines():
        r = json.loads(line)
        qa = r.get('qa') or {}
        if qa.get('pass'):
            best[r['id']] = max(best.get(r['id'], 0), qa.get('score', 0))
    return best


def minhash_nearest(texts, k=128):
    rng = np.random.default_rng(7)
    p = np.uint64((1 << 61) - 1)
    a_ = rng.integers(1, int(p), k, dtype=np.uint64)
    b_ = rng.integers(0, int(p), k, dtype=np.uint64)
    sig = np.empty((len(texts), k), dtype=np.uint64)
    for i, t in enumerate(texts):
        w = re.findall(r'\w+', t.lower())
        sh = np.array(sorted({zlib.crc32(' '.join(w[j:j + 5]).encode()) for j in range(max(1, len(w) - 4))}), dtype=np.uint64)
        sig[i] = ((np.outer(sh, a_) + b_) % p).min(axis=0)
    near = np.zeros(len(texts))
    for i in range(len(texts)):
        s = (sig == sig[i]).mean(axis=1)
        s[i] = 0
        near[i] = s.max()
    return near


def group_key(fam, parts):
    # family + topic + subject: the axes a reader searches by.  District,
    # audience and situation are the axes that only multiply pages.
    if fam == 'du-lich':
        return (fam, parts[1])                      # destination
    if fam == 'luat':
        return (fam, parts[1])                      # legal topic
    return (fam, parts[1], parts[2])                # topic + vehicle


def orphans():
    """index.html files committed in the repo that a clean build does not produce."""
    with tempfile.TemporaryDirectory() as tmp:
        dst = Path(tmp) / 'site'
        shutil.copytree(ROOT, dst, ignore=shutil.ignore_patterns('.git', '.claude'))
        for f in dst.rglob('index.html'):
            if 'templates' not in f.parts:
                f.unlink()
        subprocess.run([sys.executable, 'scripts/build.py'], cwd=dst, check=True, capture_output=True)
        built = {f.relative_to(dst) for f in dst.rglob('index.html')}
    committed = {f.relative_to(ROOT) for f in ROOT.rglob('index.html')
                 if not {'templates', '.git', '.claude'} & set(f.relative_to(ROOT).parts)}
    return sorted('/' + str(p.parent).replace('\\', '/') + '/' for p in committed - built)


def main():
    arts = [json.loads(Path(f).read_text()) for f in sorted(glob.glob(str(ROOT / 'content/articles/*.json')))]
    qa = qa_scores()
    texts = [plain(a) for a in arts]
    near = minhash_nearest(texts)
    rows = []
    for a, t, nn in zip(arts, texts, near):
        parts = a['intent'].split('|')
        fam = parts[0]
        body = ' '.join(b for _, b in sections(a))
        amounts = set(re.findall(r'\d{1,3}(?:\.\d{3})+(?=\s*(?:đ|đồng|VNĐ))|\d+(?:,\d+)?\s(?:triệu|nghìn)', t))
        unsupported = sorted(x for x in amounts if x not in ALLOWED_AMOUNTS)
        rows.append(dict(
            id=a['id'], url=a['url'], title=a['title'], family=fam, topic=parts[1],
            subject=parts[2] if len(parts) > 2 else '', words=a.get('wordCount', 0), qa=qa.get(a['id'], 0),
            money_links=sum(body.count(f'href="{u}"') for u in MONEY),
            near_dup=round(float(nn), 2), unsupported_amounts=' '.join(unsupported),
            outdated='; '.join(v for k, v in OUTDATED.items() if k in t),
            fit=fit_problem(fam, parts[1], parts[2] if len(parts) > 2 else '', t),
            key=group_key(fam, parts)))
    groups = collections.defaultdict(list)
    for r in rows:
        if not r['fit']:
            groups[r['key']].append(r)
    for g in groups.values():
        g.sort(key=lambda r: (-r['qa'], -r['money_links'], len(r['unsupported_amounts']), -r['words'], len(r['url'])))
        rep = g[0]
        for r in g[1:]:
            r['decision'], r['merge_into'] = 'GOP', rep['url']
        if rep['family'] == 'luat':
            rep['decision'] = 'XEM_LAI'
        elif rep['unsupported_amounts'] or rep['outdated']:
            rep['decision'] = 'GIU_SUA'
        else:
            rep['decision'] = 'GIU'
        rep['merge_into'] = ''
    for r in rows:
        if r['fit']:
            r['decision'], r['merge_into'] = 'BO', ''
    OUT.mkdir(exist_ok=True)
    cols = ['id', 'decision', 'url', 'merge_into', 'family', 'topic', 'subject', 'title', 'qa', 'words',
            'money_links', 'near_dup', 'fit', 'unsupported_amounts', 'outdated']
    with open(OUT / 'factory-audit.csv', 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction='ignore')
        w.writeheader()
        w.writerows(sorted(rows, key=lambda r: (r['decision'], r['family'], r['url'])))
    orph = [] if '--no-orphans' in sys.argv else orphans()
    (OUT / 'factory-orphans.txt').write_text(''.join(u + '\n' for u in orph))
    summary(rows, orph, near)


def summary(rows, orph, near):
    by = collections.Counter((r['family'], r['decision']) for r in rows)
    fams = sorted({r['family'] for r in rows})
    decs = ['GIU', 'GIU_SUA', 'XEM_LAI', 'GOP', 'BO']
    lines = ['# Chấm lại bài xưởng', '',
             f'{len(rows)} bài trong content/articles/. Báo cáo chỉ đề xuất, chưa thay đổi gì trên site.', '',
             '| Nhóm | ' + ' | '.join(decs) + ' | Tổng |', '|' + ' --- |' * (len(decs) + 2)]
    for f in fams:
        lines.append(f'| {f} | ' + ' | '.join(str(by[(f, d)]) for d in decs) + f' | {sum(by[(f, d)] for d in decs)} |')
    lines.append('| **Tổng** | ' + ' | '.join(str(sum(by[(f, d)] for f in fams)) for d in decs) + f' | {len(rows)} |')
    lines += ['', f'Độ trùng (MinHash, cụm 5 từ) với bài giống nhất: trung vị {np.median(near):.2f}, '
              f'90% bài ≥ {np.percentile(near, 10):.2f}.', '',
              f'Bài có số tiền không có trong business-facts.json: {sum(1 for r in rows if r["unsupported_amounts"])}.',
              f'Bài không link tới trang tiền nào: {sum(1 for r in rows if not r["money_links"])}.',
              f'Trang HTML mồ côi (build hiện tại không tạo ra): {len(orph)} (xem reports/factory-orphans.txt).', '',
              '## Ví dụ bài BỎ', '']
    for r in [r for r in rows if r['decision'] == 'BO'][:10]:
        lines.append(f'- `{r["url"]}`: {r["fit"]}')
    (OUT / 'factory-audit.md').write_text('\n'.join(lines) + '\n')
    print('\n'.join(lines[:len(fams) + 8]))


if __name__ == '__main__':
    main()
