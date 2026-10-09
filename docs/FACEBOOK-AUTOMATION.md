# GitHub Actions + Meta Graph API

## Installed behavior

This pipeline targets **Cho thuê xe máy 50cc Long Biên Hà Nội**, Page ID
`1397799880080241`, using `Asia/Ho_Chi_Minh`.

It is installed in **dry-run mode**. No Meta POST is possible while
`config/facebook.json` has `live_enabled: false`. The code additionally requires
both repository variables `FACEBOOK_LIVE_ENABLED=true` and
`FACEBOOK_TESTS_PASSED=true`, and checks `STOP_FACEBOOK` before running.
None of those switches is enabled by installation or a passing unit test.

- 10:00: snapshot up to 10 newest dated, published article/pillar sources in the
  `/cam-nang/` aggregate. Read each deployed canonical page and verify its full
  section content matches the source. Prepare 10 independent Vietnamese drafts.
- After preparation, when explicitly enabled: ask Meta to schedule each post at
  11:00, 11:30, 12:00, 12:30, 13:00, 13:30, 14:00, 14:30, 15:00, 15:30.
  These are native scheduled Page posts (`published=false`), **not immediate posts**.
- 16:00: verify existing Post IDs and produce a daily report.
- `workflow_dispatch`: prepare, read-only preflight, or report. There is no manual
  switch that bypasses the live gates.

GitHub cron is UTC (03:00/09:00) and can be delayed or dropped. The preparation
cutoff is always 10:00 local; even a delayed runner does not silently replace the
list with newer articles. A slot with less than 11 minutes remaining is marked
`missed`; it is never shifted or published immediately. Native Meta scheduling
avoids relying on ten precisely timed Actions invocations. Public repository
scheduled workflows can be automatically disabled after 60 days without activity.

## Article index and dates

`assets/latest-articles.json` is a bounded feed of 100 articles with canonical URL,
title, publication timestamp, provenance and full-content hash. `scripts/build.py`
rebuilds it automatically; the social preparation also rebuilds from its checkout
with the 10:00 cutoff **before** applying the size limit. All nine hubs displayed
by `/cam-nang/` are eligible; this URL is an aggregate, not a WordPress category.

New factory articles get a timezone-aware `published_at` at acceptance. Existing
sources have no trustworthy per-article publication timestamp (HTML currently
uses a fixed 2026-10-06 date). For these, the index uses the auditable **first source
commit timestamp**, labelled `git_first_source_commit`. That is an approximation
of first publication, not a recovered exact Pages deployment time. Never use file
mtime, a rebuild date, or a sitemap lastmod as publication time. A tie is broken
by numeric source ID then canonical URL. No existing article text or QA gate is
changed by the index integration.

The feed stores metadata, not 100 copies of the full article. Preparation loads
all sections from the source shard/legacy JSON, validates the hash, and reads the
live page. Missing/unavailable/not-yet-deployed content is a recorded error. It
does not select an older substitute. Fewer than ten sources means fewer drafts,
with `missing` recorded. Same-day reruns preserve the first source list; repeated
URLs from the preceding day produce warnings but remain eligible as requested.

## AI without a paid API

The job runs official `ollama/ollama:0.34.2` locally on the standard Ubuntu runner,
with cloud access disabled and `qwen3:4b-instruct-2507-q4_K_M` (Apache 2.0). It does
not use ChatGPT subscriptions, browser sessions, GitHub Models, or any paid AI API.
GitHub Models was retired on 2026-07-30. Standard runners in public repositories
are currently free, subject to GitHub usage policies; this is not an unlimited
service guarantee. No model/cache artifact is retained between daily jobs.

Each draft is based on the full source, with 3–5 evidence excerpts retained for
validation but excluded from the public post. The code inserts the exact contact
block directly below the title, then the 225–275-word body, source URL, and 3–5
unaccented hashtags. Length is counted by whitespace. It rejects incomplete JSON,
missing evidence, new numeric values, outdated 08:00–17:00 shop hours, and near
identical daily bodies. The authoritative social hours are 09:00–21:00; repository
business files still contain older hours and are not silently republished here.
Evidence and numerical checks reduce errors but do not establish semantic truth.
Review the full AI dry-run drafts before activation.

There are at most two generation/validation attempts per draft. No deterministic
paragraph generator is presented as AI. Full prompts that exceed a conservative
UTF-8-byte/context budget are rejected, never truncated. CPU inference/model
pulls may take too long for the first slot; daily preparation is capped at 50
minutes. Measure all ten drafts on Actions before activation. If the model is too
slow or drafts fail QA, keep live disabled; use a suitably provisioned self-hosted
runner or adjust the local model only after another full dry-run.

## Durable anti-duplicate ledger

`facebook-state` is a dedicated Git branch in this same public repository. It must
exist before the daily job runs. `days/YYYY-MM-DD.json` freezes source order and
stores draft, scheduled time, status, errors and Meta Post ID. Reports live at
`reports/YYYY-MM-DD.json`. No token or raw API response is written to the ledger.
Drafts and reports are visible to anyone who can read this public repository.

State changes use the GitHub Contents API with a blob-SHA compare-and-swap. A
conflict or network failure aborts; it never rebases/overwrites ledger state.
`contents: write` is scoped to jobs that need it. Code checkout does not persist
credentials. The social workflow has its own concurrency group, separate from
content generation; all social operations serialize without cancelling a sender.

Every Meta POST has a durable `submitting` checkpoint **before** network I/O.
After success its Post ID is checkpointed before proceeding, and the requested
schedule is read back. If either the request/response or a subsequent checkpoint
is lost, a rerun searches the Page's scheduled posts and feed, matching exact
message and local day. Pagination must complete. A single match is adopted;
zero or ambiguous matches remain `unknown`, **with no blind POST retry**. This is
at-most-once submission under uncertainty; no unsupported Meta idempotency key or
exactly-once guarantee is assumed. An operator must reconcile `unknown` states
with Meta before any retry. Never reset the state branch or mark an unknown entry
`ready` without confirming that no post exists.

## Permission and token setup (still required)

GitHub repository read/write/admin permission was verified during installation.
The connector cannot inspect or populate repository secrets here; successful
connection to Windsor/Upload-Post does not supply credentials to this workflow.

Add these **GitHub Actions secrets** in repo Settings → Secrets and variables →
Actions, never in source code, issues, logs or chat:

| Secret | Purpose |
|---|---|
| `META_PAGE_ACCESS_TOKEN` | Page access token for Page 1397799880080241 |
| `META_APP_ID` | The Meta app that issued the token |
| `META_APP_SECRET` | Read-only token debugging authentication |

The Page token must grant `pages_manage_posts` and `pages_read_engagement` for the
correct Page. Obtain it through an authorized Meta app/user with Page content
creation tasks; `pages_show_list` is normally needed when discovering/exchanging
Page tokens. App review/access level and app mode depend on the app and people
using it; follow Meta's current requirements. This implementation never creates
an app, exchanges a user token, or changes Page permissions automatically.

Run `preflight` from Actions after secrets are supplied. It performs only GETs:
checks `/me` ID and name, `/debug_token` validity/app/scopes/granular targets and
expiry through the posting window, and read access to scheduled/feed endpoints.
It cannot prove create-post permission without a separately authorized write
integration test. Token errors are reported without exposing credentials.

## Verification and activation

1. Run the required factory checks plus the social unittest suite.
2. The `codex/facebook-*` branch push runs a **full 10-source local AI dry-run**
   on Actions, without Meta secrets; inspect its artifacts and elapsed time.
   Re-run `prepare` manually on the default branch if further review is needed.
3. Supply Meta secrets and run read-only `preflight`.
4. Obtain authorization for a controlled Meta write integration test; dry-run
   alone does not prove API scheduling works. Inspect native scheduled time and
   Page identity. Do not enable recurring publication while these steps fail.
5. Only after all tests and reviewed drafts pass: set `FACEBOOK_TESTS_PASSED=true`,
   change JSON `live_enabled` to true, then set `FACEBOOK_LIVE_ENABLED=true`.
   Installation does **not** perform this activation.

Stop future submissions by setting the live variable false, setting JSON live
false, disabling the workflow or committing `STOP_FACEBOOK`. Cancel a running
workflow as well. Already scheduled Meta posts remain scheduled and must be
managed in Meta separately. Do not delete ledger records to stop posting.

The report distinguishes prepared/scheduled/published/errors/unposted and records
source URLs, planned times, Post IDs/permalinks and Meta `created_time`. Meta may
return the scheduled object's creation time rather than the exact public publish
instant; that value is labelled, never claimed as a precise observed publication
time. Failed reporting does not convert an unverified post into a success.

## Local commands

```sh
python3 scripts/latest_articles.py
python3 -m unittest discover -s tests -p 'test_facebook*.py' -v
python3 scripts/facebook_pipeline.py prepare  # local durable files, no Meta POST
python3 scripts/facebook_pipeline.py preflight  # only with secrets in environment
```

Primary references checked 2026-10-09:
- https://docs.github.com/en/github-models
- https://docs.github.com/en/actions/concepts/billing-and-usage
- https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows
- https://developers.facebook.com/documentation/pages-api/posts
- https://developers.facebook.com/docs/graph-api/reference/debug_token/
- https://docs.ollama.com/api/generate
- https://ollama.com/library/qwen3:4b-instruct-2507-q4_K_M
