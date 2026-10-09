import copy
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import facebook_pipeline as f
from latest_articles import build_feed


def article(index=1):
    return {'id': f'NH-{index:05}', 'title': 'Kiểm tra phanh xe máy trước chuyến đi',
            'url': f'https://thuha.rentbikehanoi.com/kinh-nghiem/bai-{index}/',
            'published_at': f'2026-10-09T0{index % 3}:00:00+00:00',
            'text': 'Kiểm tra phanh trước chuyến đi giúp nhận biết dấu hiệu bất thường.',
            'sections': [{'heading': 'Phanh', 'text': 'Kiểm tra phanh trước chuyến đi giúp nhận biết dấu hiệu bất thường.'}]}


def draft():
    # Fake AI only exercises validation and state transitions, never offered as AI content.
    return {'title': 'Kiểm tra phanh xe máy trước chuyến đi',
            'intro': ' '.join(['Kiểm tra phanh trước mỗi chuyến đi giúp bạn chuẩn bị kỹ hơn.'] * 4),
            'highlights': [{'text': ' '.join(['Quan sát và thử phanh ở vị trí phù hợp trước khi di chuyển.'] * 4),
                            'evidence': 'Kiểm tra phanh trước chuyến đi'} for _ in range(3)],
            'closing': ' '.join(['Trao đổi với thợ khi phát hiện bất thường.'] * 4),
            'hashtags': ['#KiemTraPhanh', '#XeMay', '#HaNoi']}


class MemoryStore:
    remote = True
    def __init__(self):
        self.data = {}
        self.fail_on = None
    def read(self, path):
        return copy.deepcopy(self.data.get(path))
    def write(self, path, value):
        if self.fail_on and self.fail_on(value):
            raise RuntimeError('state unavailable')
        self.data[path] = copy.deepcopy(value)


class FakeMeta:
    def __init__(self):
        self.calls = 0
        self.fail = False
        self.wrong_time = False
        self.rows = []
        self.last_entry = None
    def preflight(self):
        return {'valid': True}
    def posts(self, edge):
        return self.rows if edge == 'scheduled_posts' else []
    def schedule(self, entry):
        self.calls += 1
        self.last_entry = copy.deepcopy(entry)
        if self.fail:
            raise f.APIError('Meta')
        return '1397799880080241_123'
    def inspect(self, post_id):
        return {'id': post_id, 'is_published': False,
                'scheduled_publish_time': 0 if self.wrong_time else int(datetime.fromisoformat(self.last_entry['scheduled_at']).timestamp())}


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.store = MemoryStore()
        self.clock = lambda: datetime(2026, 10, 9, 3, 30, tzinfo=timezone.utc)

    def queue(self):
        msg, body = f.validate_draft(draft(), article())
        return {'date': '2026-10-09', 'mode': 'dry-run', 'found': 1, 'missing': 9,
                'entries': [{'url': article()['url'], 'title': article()['title'], 'message': msg,
                             'body': body, 'status': 'ready', 'scheduled_at': '2026-10-09T11:00:00+07:00'}]}

    def live(self):
        return patch.multiple(f.CONFIG, live_enabled=True)  # dict patched separately in tests

    def test_default_gate_never_posts(self):
        meta = FakeMeta()
        f.schedule(self.store, self.queue(), meta, self.clock)
        self.assertEqual(meta.calls, 0)

    def test_contact_position_and_length(self):
        message, body = f.validate_draft(draft(), article())
        self.assertTrue(message.startswith(draft()['title'] + '\n\n' + f.CONTACT))
        self.assertTrue(225 <= len(body.split()) <= 275)
        self.assertIn(article()['url'], message)

    def test_reject_invented_numbers_evidence_length_duplicate(self):
        for change in ('numbers', 'evidence', 'length'):
            d = draft()
            if change == 'numbers': d['title'] += ' giảm 999999 đồng'
            if change == 'evidence': d['highlights'][0]['evidence'] = 'Not in source at all'
            if change == 'length': d['intro'] = 'Ngắn'
            with self.assertRaises(ValueError): f.validate_draft(d, article())
        _, body = f.validate_draft(draft(), article())
        with self.assertRaises(ValueError): f.validate_draft(draft(), article(), [body])

    def test_selection_cutoff_and_duplicates(self):
        rows = [article(i) for i in range(1, 14)]
        future = article(100)
        future['published_at'] = '2026-10-09T04:00:00+00:00'
        feed = {'site': f.CONFIG['site'], 'collection': '/cam-nang/', 'articles': rows + [future]}
        result = f.select_articles(feed, '2026-10-09')
        self.assertEqual(len(result), 10)
        self.assertNotIn(future, result)
        feed['articles'].append(rows[0])
        with self.assertRaises(ValueError): f.select_articles(feed, '2026-10-09')

    def test_partial_collection_freezes_sources_and_warns_next_day(self):
        feed = {'site': f.CONFIG['site'], 'collection': '/cam-nang/', 'articles': [article()]}
        queue = f.prepare(self.store, '2026-10-09', feed, ai=lambda a, b: (draft(), 1), verify=lambda a: None)
        self.assertEqual(queue['missing'], 9)
        self.assertEqual(queue['entries'][0]['status'], 'ready')
        again = f.prepare(self.store, '2026-10-09', {**feed, 'articles': [article(2)]}, ai=lambda a, b: self.fail(), verify=lambda a: self.fail())
        self.assertEqual(again['entries'][0]['url'], article()['url'])
        tomorrow = f.prepare(self.store, '2026-10-10', feed, ai=lambda a, b: (draft(), 1), verify=lambda a: None)
        self.assertEqual(len(tomorrow['warnings']), 1)

    @patch.dict('os.environ', {'FACEBOOK_LIVE_ENABLED': 'true', 'FACEBOOK_TESTS_PASSED': 'true'})
    def test_success_and_rerun_do_not_duplicate(self):
        with patch.dict(f.CONFIG, {'live_enabled': True}):
            meta = FakeMeta()
            q = f.schedule(self.store, self.queue(), meta, self.clock)
            f.schedule(self.store, q, meta, self.clock)
            self.assertEqual(meta.calls, 1)
            self.assertEqual(q['entries'][0]['status'], 'scheduled')

    @patch.dict('os.environ', {'FACEBOOK_LIVE_ENABLED': 'true', 'FACEBOOK_TESTS_PASSED': 'true'})
    def test_unknown_response_never_blindly_retries(self):
        with patch.dict(f.CONFIG, {'live_enabled': True}):
            meta = FakeMeta(); meta.fail = True
            q = f.schedule(self.store, self.queue(), meta, self.clock)
            f.schedule(self.store, q, meta, self.clock)
            self.assertEqual(meta.calls, 1)
            self.assertEqual(q['entries'][0]['status'], 'unknown')
            meta.rows = [{'id': '1397799880080241_123', 'message': q['entries'][0]['message'], 'created_time': '2026-10-09T03:30:00+0000'}]
            q = f.schedule(self.store, q, meta, self.clock)
            self.assertEqual(q['entries'][0]['post_id'], '1397799880080241_123')
            self.assertEqual(meta.calls, 1)

    @patch.dict('os.environ', {'FACEBOOK_LIVE_ENABLED': 'true', 'FACEBOOK_TESTS_PASSED': 'true'})
    def test_failed_checkpoint_prevents_post(self):
        with patch.dict(f.CONFIG, {'live_enabled': True}):
            meta = FakeMeta()
            self.store.fail_on = lambda q: q['entries'][0]['status'] == 'submitting'
            with self.assertRaises(RuntimeError): f.schedule(self.store, self.queue(), meta, self.clock)
            self.assertEqual(meta.calls, 0)

    @patch.dict('os.environ', {'FACEBOOK_LIVE_ENABLED': 'true', 'FACEBOOK_TESTS_PASSED': 'true'})
    def test_crash_after_post_keeps_submitting_checkpoint(self):
        with patch.dict(f.CONFIG, {'live_enabled': True}):
            meta = FakeMeta()
            self.store.fail_on = lambda q: q['entries'][0]['status'] == 'scheduled'
            with self.assertRaises(RuntimeError): f.schedule(self.store, self.queue(), meta, self.clock)
            self.assertEqual(self.store.read('days/2026-10-09.json')['entries'][0]['status'], 'submitting')
            self.assertEqual(meta.calls, 1)

    @patch.dict('os.environ', {'FACEBOOK_LIVE_ENABLED': 'true', 'FACEBOOK_TESTS_PASSED': 'true'})
    def test_late_slot_never_shifted(self):
        with patch.dict(f.CONFIG, {'live_enabled': True}):
            meta = FakeMeta()
            q = f.schedule(self.store, self.queue(), meta, lambda: datetime(2026, 10, 9, 3, 55, tzinfo=timezone.utc))
            self.assertEqual(meta.calls, 0)
            self.assertEqual(q['entries'][0]['status'], 'missed')

    def test_live_requires_remote_journal(self):
        with patch.dict(f.CONFIG, {'live_enabled': True}), patch.dict('os.environ', {'FACEBOOK_LIVE_ENABLED': 'true', 'FACEBOOK_TESTS_PASSED': 'true'}):
            with tempfile.TemporaryDirectory() as folder:
                with self.assertRaises(ValueError): f.schedule(f.Store(directory=folder), self.queue(), FakeMeta(), self.clock)

    def test_missing_meta_token_is_explicit(self):
        with patch.dict('os.environ', {}, clear=True):
            with self.assertRaisesRegex(ValueError, 'Missing META'): f.Meta().preflight()

    def test_preflight_wrong_page_and_scopes(self):
        with patch.dict('os.environ', {'META_PAGE_ACCESS_TOKEN': 'fake', 'META_APP_ID': '123', 'META_APP_SECRET': 'fake'}):
            meta = f.Meta()
            with patch.object(meta, 'call', return_value={'id': 'wrong', 'name': 'wrong'}):
                with self.assertRaisesRegex(ValueError, 'identity'): meta.preflight()
            with patch.object(meta, 'call', side_effect=[{'id': f.CONFIG['page_id'], 'name': f.CONFIG['page_name']}, {'data': {'is_valid': True, 'app_id': '123', 'scopes': []}}]):
                with self.assertRaisesRegex(ValueError, 'scopes'): meta.preflight()

    def test_feed_rebuild_is_deterministic_and_bounded(self):
        feed = build_feed(ROOT)
        self.assertEqual(len(feed['articles']), 100)
        before = (ROOT / 'assets/latest-articles.json').read_bytes()
        build_feed(ROOT)
        self.assertEqual(before, (ROOT / 'assets/latest-articles.json').read_bytes())
        self.assertTrue(all(x['date_source'] in ('source_timestamp', 'git_first_source_commit') for x in feed['articles']))


if __name__ == '__main__':
    unittest.main()
