# AGENTS.md — Nguyễn Hà content factory

Repository files are the source of truth. Read `docs/CONTENT-FACTORY.md` before changing the writer.

## Non-negotiable rules

- Never bypass the score threshold, critical-error gate, duplicate URL, duplicate intent or similarity check.
- Never edit `data/content-index.jsonl` manually; regenerate it with `python3 scripts/content_factory.py reindex`.
- Article source belongs in one JSON shard under `content/articles/`. Existing `content/posts.json` remains legacy source.
- A production run publishes up to 50 pairs: 100 articles.
- Never add an external AI API, token or network content dependency to the writer.
- Business facts come from `config/business-facts.json`. Do not invent price, availability, legal advice or real-time information.
- Failed QA remains rejected in the append-only queue log and must not enter article source, sitemap or search index.
- Do not force-push, reset factory state or reuse a published URL/intent.

## Required checks

```sh
python3 scripts/content_factory.py run --dry-run
python3 tests/test_content_factory.py
python3 scripts/build.py
python3 scripts/validate_factory_site.py
```

Stop production safely by adding a root file named `STOP_FACTORY`, or set `enabled` to `false` in `config/content-factory.json`. Resume by reversing that change. Scheduled runs are serialized through workflow concurrency.
