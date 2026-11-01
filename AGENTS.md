# Repository Guidelines

Project: **chatmatch** — Flask web app for 39C3 that matches participants into discussion groups of 3–5 by topic + 30-minute time slot. Nickname-only privacy (emails never shown), timezone Europe/Berlin, target 100–200 participants. Product requirements live in `spec.md` (F1–F10); license is AGPL-3.0.

## Architecture & Data Flow

Single-file Flask monolith: **`app.py`** (~1160 lines) plus Jinja templates and static favicons. No services, jobs, or background workers — everything runs synchronously inside the HTTP request.

- `create_app()` (L922) is a factory, but it assigns to **module globals** (`app`, `bootstrap`, `db`, `session`); every function re-declares them with `global db`. There is no import-time app; gunicorn target is `app:create_app()`.
- **Models** (SQLAlchemy 2.0 style, L73–139): `User` (`user_table`), `Topic` (`topic_table`), `Slot` (`slot_table`), `Match` (`match_table`). Plain `int` foreign keys with `UniqueConstraint`s, no ORM relationships. All timestamps are **naive epoch ints** via `datetime.now().timestamp()` — correct only if the host TZ is Europe/Berlin; there is no `zoneinfo`.
- **Data flow on registration** (`index()`, L228): upsert `User` by nickname+email → diff submitted slot checkboxes against existing `Match` rows → insert/cancel/restore `Match` rows → one batched `db.session.commit()` → send confirmation email + run `recalc_topic(topic.id)` in-request → redirect.
- **Matching** (`recalc_topic()`, L482–553): groups = active (non-cancelled) `Match` rows per slot; slots with `start_time <= now` are skipped; when a slot has ≥ `topic.min_users`, existing confirmed members plus FCFS-pending ones up to `max_users` get confirmed and emailed by `send_slot_mail()`. **No overflow/second-group logic** — surplus beyond `max_users` waits indefinitely (spec F4 "new group in next slot" is not implemented). A match can never be unconfirmed once set.
- **Emails** (`send_mail`, L905): `SMTP_SSL`, one connection per recipient, plaintext with manually embedded `To:`/`From:` lines. `app.debug` doubles as an email-suppression switch (prints instead of sending) — safe to dev-run locally without configuring SMTP.
- **Not implemented relative to spec**: .ics generation (F7), self-service passwordless links (F6, optional). `User.magic` is written but never used for links; `newmagic`, `lastuse_time`, and most `edit_time` columns are dead.

## Key Directories

| Path | Purpose |
| --- | --- |
| `app.py` | Everything: config, models, forms, routes, matching, mail, seeding |
| `templates/` | Jinja2 + bootstrap-flask. `base.html` (theme, flash, GDPR footer), `index.html` (landing + registration form). `register.html`, `flash.html` are leftover bootstrap-flask demo scaffolds; `admin.html` is a 20-byte theme-list stub; `site.webmanifest` is Jinja-processed |
| `static/` | Favicons/webmanifest only — no source CSS/JS (bootstrap-flask serves the framework, `BOOTSTRAP_SERVE_LOCAL=True`) |
| `spec.md` | Authoritative product requirements; changes to matching behavior should be checked against it |
| `.github/workflows/main.yml` | CI: build + push Docker image only (no test/lint steps) |

## Development Commands

Environment manager is **uv** (`uv.lock` committed, `.python-version` = 3.14).

```bash
uv sync                 # install deps into .venv from pyproject/lock
DEBUG=1 python app.py   # dev server (flask run; DEBUG=1 also suppresses mail)
# or: uv run python app.py
```

Production (matches `Dockerfile` CMD):

```bash
gunicorn --bind 0.0.0.0:8080 "app:create_app()"
docker build -t ghcr.io/berlincount/chatmatch:latest .   # CI does this automatically for push+PR to main
```

No lint, type-check, or test commands exist. No local config files — all configuration is environment variables:

| Var | Default | Notes |
| --- | --- | --- |
| `DATABASE_URI` | `sqlite:///dev.sqlite3` | Flask instance dir (`instance/`, gitignored) |
| `SECRET_KEY` | `"dev"` | set in any non-local deployment |
| `DEBUG` / `TESTING` / `DATABASE_ECHO` | off | **`bool(os.getenv(...))` pitfall**: `"0"`, `"false"`, etc. are truthy — use empty vs set, not false-like strings |
| `SMTP_SERVER`, `SMTP_PORT` | `localhost` / 465 | plus `SMTP_USERNAME`, `SMTP_PASSWORD` (placeholder defaults) |
| `SESSION_DIR` | `sessions` | cachelib `FileSystemCache` for Flask-Session |
| `THEME` | `pulse` | bootswatch theme name |
| `CHATMATCH_NAME/_TITLE/_THEME_COLOR/...` | see L938–948 | branding exposed to templates via `get_config()` Jinja global |
| `DANGER_DROP_DATABASE` | off (empty) | **destructive**: any set value drops all tables at startup |

## Code Conventions & Common Patterns

- **No types on routes**, type annotations only on model columns (`Mapped[...]`); no docstrings anywhere. Match this baseline; don't introduce style churn in passing edits.
- **Logging is `print()` with ✅/❎ emoji prefixes** plus `pprint` behind `if app.debug`; user-facing errors use `flash(msg, "danger")`.
- **Error handling pattern**: `try: db.session.add/commit except IntegrityError:` → print + flash + `redirect(url_for("index"))`. This is the only guarded path; most other errors are uncaught (see known issues).
- **Config**: inline `os.getenv` inside `app.config.from_mapping(...)` at L926 — no Config class.
- **Hardcoded seeds in `create_app()`** (L984–1122): system user, hidden "Default" topic + 6 relationship topics (`min_users=3`, `max_users=5`), and 30-min slots for 2025-12-27…30 with per-day hour ranges. For a new event date range, editing this seed block is the intended mechanism.
- **Stale caches**: `fetch_topics()` / `fetch_slots(topic_id)` wrap DB queries in `@lru_cache(maxsize=16)` and are **never invalidated** — form choices can go stale until process restart. A FIXME also hardcodes `choices=fetch_slots(1)` in the live form (L301–302).
- **Dead code is common**: unrouted demo functions (`register()`, L684, references an undefined `UserForm`; demo block L719+ references an undefined `Message` model), unused forms `RegisterButtonForm`/`HelloForm`, commented-out routes (`/register`, `/topics`, `/calendar`, …) whose templates don't exist. Don't "fix" or reuse them; treat as intentionally dormant.

### Known issues to be aware of when editing

1. `except IntegrityError, PendingRollbackError:` (L992, 1004, 1075, 1120) is **valid only on Python ≥3.14** (PEP 758 allows dropped parentheses). `pyproject.toml` claims `>=3.12` but the runtime everywhere is 3.14 — adding such clauses is fine on the pinned runtime, but parenthesized form stays portable if you want it.
2. `recalc_topic()` L551 passes the loop variable **`slot`** (the last iterated slot) into `send_slot_mail()` for every qualifying slot — emails show the wrong time when ≥2 slots of a topic cross `min_users` in one pass.
3. `/recalc_all_topics` is an **unauthenticated GET** that re-matches everything and mass-emails; CSRF cannot protect GET. There is no admin auth anywhere (`/admin` only prints the theme list).
4. `base64.b64encode(...)` (bytes) is assigned to `User.magic: Mapped[str]` (L323, L1000).

## Important Files

- `app.py` — single entry point; `if __name__ == "__main__"` at L1156. Registration + matching in `index()`/`recalc_topic()`, mail in `send_mail()`/`send_slot_mail()`.
- `spec.md` — requirements F1–F10: group size 3–5, cancellation keeps a group only while ≥3 members remain and returns unexpired slots to the pool, nicknames-only privacy, .ics with Europe/Berlin. Use as the change contract.
- `Dockerfile` — multi-stage with `uv:0.9.18`, runtime `python:3.14-slim-bookworm`, runs as root, port 8080 hardcoded, **installs from `requirements.txt` only** (never reads `pyproject.toml`/`uv.lock`).
- `.github/workflows/main.yml` — build+push to `ghcr.io/berlincount/chatmatch:latest` on push and PR.

## Runtime/Tooling Preferences

- **Python 3.14** everywhere (`.python-version`, Docker base, CI). Don't downgrade assumptions in `pyproject.toml` without fixing the PEP 758 syntax above.
- **uv** for local envs; Docker is the deployment unit.
- **Dependency changes require updating two files**: `pyproject.toml` (local/uv) and `requirements.txt` (Docker authority). They are currently byte-identical in pin set — keep them in sync, and run `uv lock` after changing `pyproject.toml`.
- Port 8080 is hardcoded in the Dockerfile; there is no env var for it.

## Testing & QA

**There is no test suite, no lint/type tooling, and CI runs nothing but the Docker build.** There are zero test files, no `[tool.pytest]`/dev groups, no ruff/mypy config.

If adding tests:

```bash
uv run --with pytest pytest          # start here; create tests/
```

Config notes for a test harness: `create_app()` accepts `test_config=None` but **never reads it** — pass overrides via environment instead, e.g. `DATABASE_URI=sqlite:///:memory:` before invoking `create_app()`. Beware side effects: every `create_app()` call runs `db.create_all()` + the full seeding block (system user, topics, ~60 slots per topic) and needs an app context; sessions use `SESSION_DIR` (point tests at a tmp dir). A smoke test should minimally exercise registration → `recalc_topic()` crossing `min_users` with debug-mode mail suppression.
