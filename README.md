# Dan's Boat Life Adventure Boat Finder

This repository contains the buyer-guide waitlist, the first responsive Adventure Boat Finder, a PostgreSQL-backed session API, and the ingestion pipeline for Dan's two power-boat playlists.

## Product surfaces

- `/` - branded waitlist and lead capture, including country and buying timing.
- `/guide/` - conversational Adventure Boat Finder with a visible editable decision trail.
- `/api/` - FastAPI session, decision, result, resume and email endpoints when the backend is deployed.

The static guide remains reviewable on GitHub Pages. It clearly reports preview mode when the database API is unavailable; it never claims progress or email has been saved when it has not.

## Local production-shaped run

1. Copy `.env.example` to `.env` and add SMTP settings if email delivery is required.
2. Run `docker compose up`.
3. Initialise the schema with `python -m backend.init_db`.
4. Open `http://localhost:8000/guide/`.

The browser receives a random resume token once. The session table stores only its SHA-256 hash. Every answer revision is retained in `guide_decisions`, while `is_current` identifies the current brief. A completion email outbox necessarily contains the private resume URL until delivery and must be protected as sensitive application data.

## YouTube ingestion

The pipeline processes only the two supplied power-boat playlists: walkthroughs (`PLlJFhpC4T6dIzSUQTmDX0QT7GmwAlHu2q`) and test drives (`PLlJFhpC4T6dJjkBX4zMAgMpUV-iyrzUfE`).

```sh
PYTHONPATH=. python -m etl.ingest \
  --sales-db /absolute/path/to/soldboats_full_structured.sqlite \
  --database-url "$DATABASE_URL"
```

The job deduplicates playlist entries, retrieves full timed English transcripts and the top 50 available comments, captures current engagement metrics, and matches make/model/length using titles, descriptions and the read-only sales catalogue. Raw job snapshots are ignored by Git and make the process recoverable.

After harvesting, rerun identity logic without touching YouTube:

```sh
PYTHONPATH=. python -m etl.reconcile \
  --sales-db /absolute/path/to/soldboats_full_structured.sqlite
```

Only complete, high-confidence make/model/length identities are eligible for publication. The report separates paired models, walkthrough-only models, test-drive-only models, low-confidence matches and unresolved records.

To import already captured records without contacting YouTube, then publish the validated launch catalogue and sold-market aggregates:

```sh
PYTHONPATH=. python -m etl.import_saved --sales-db /absolute/path/to/soldboats.sqlite
PYTHONPATH=. python -m etl.import_launch_catalog --sales-db /absolute/path/to/soldboats.sqlite
```

After transcript ingestion, build the corpus-wide category and decision-field candidates, then import them:

    PYTHONPATH=. python -m etl.build_taxonomy_catalog
    PYTHONPATH=. python -m etl.import_taxonomy

This resolves the 398 real boat videos to 209 canonical boats and stores transcript-evidenced specifications, features, mission tags and overlapping category candidates. Every observation retains its video, timestamp, short excerpt, qualifier and confidence. A missing tag remains unknown; optional or conflicting configurations are not converted into a false yes/no. The workshop paper is in BOAT_TAXONOMY_WORKSHOP.md.

## Sold-boat data safety

The existing BoatWizard/YachtWorld SQLite file is opened with `mode=ro`, `immutable=1` and `PRAGMA query_only = ON`. The build never scrapes BoatWizard again and never writes to this source. Only controlled model/region aggregates belong in the guide database; sales representative contact fields are excluded.

Sold and listed prices remain separate. `sold_price_aud` and `sold_price_original` are used for sold-market evidence. Listed-price fields are asking prices and are only used for paired asking-versus-sold analysis.

## Email delivery

Completion always writes an `email_outbox` record first. When Resend or SMTP is configured, the API sends the buyer their answers, shortlist, reasons and private resume URL. If delivery is unavailable, the message remains queued and the interface says so rather than reporting a false success.

## Free review deployment

`render.yaml` defines a free Render web service for the FastAPI application. Use a separate Neon PostgreSQL project so the database does not expire with Render's 30-day free database limit. The Render Blueprint prompts for these values and never stores them in Git:

- `DATABASE_URL`: the pooled Neon connection string.
- `RESEND_API_KEY`: a restricted Resend sending key.
- `SMTP_FROM`: a sender on a domain verified in Resend.

Render runs the SQL migrations before each deploy. The public guide already targets the Blueprint service name at `https://dans-boat-life-guide-api.onrender.com`; until that service exists it falls back honestly to preview mode. If Render requires a different service name, update `guide/config.js` to the assigned origin. The free Render service sleeps after inactivity, so the first request after a quiet period can take about a minute. Render blocks outbound SMTP ports on free services; the Resend HTTPS path is therefore preferred.

GitHub Actions repeats the production-shaped checks on every pull request and every push to `main`: unit tests, JavaScript syntax, Python compilation, all PostgreSQL migrations and the complete session, decision-edit, secure-resume, shortlist and email-outbox journey.
