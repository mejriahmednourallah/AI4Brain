# AI4BRAIN: complete Docker Compose package

The project runs as three Linux containers from one `compose.yaml`: a built React frontend
served by Nginx, the FastAPI API with local CPU KittenTTS, and Neo4j. SQLite remains the
canonical database inside an API data volume; Neo4j is the derived Brain Twin graph.
No PostgreSQL/Supabase migration, host Python/Node installation or separate database daemon
is required for this deployment.

## Start

Install/start Docker Desktop with Linux containers (or Docker Engine plus Compose v2 on
Linux). First build needs network access for public images/packages. On Windows:

```powershell
.\scripts\compose-up.ps1
```

The helper creates `.env` only if missing, generates a Neo4j password when the template
placeholder is still present, preserves existing configuration, builds and waits for health.
For an existing configured checkout, the equivalent cross-platform command is:

```sh
docker compose up --build --detach --wait --wait-timeout 240
```

For a fresh Linux/macOS checkout, copy `.env.example` to `.env`, replace `NEO4J_PASSWORD`
with your own password of at least eight characters, then run that command. The repository's
actual `.env`, API keys and learner databases are not included in the portable source ZIP.

| Endpoint | Default URL | Purpose |
|---|---|---|
| App | http://localhost:8080 | Frontend and same-origin API proxy |
| API docs | http://localhost:8080/docs | FastAPI schema via Nginx |
| API health | http://localhost:8080/health | Actual API readiness |
| Neo4j Browser | http://localhost:7475/browser/ | Graph browser; user `neo4j`, password from local `.env` |
| Neo4j Bolt | bolt://localhost:7688 | Host-side graph tools |

Ports bind to loopback. `AI4BRAIN_HTTP_PORT`, `AI4BRAIN_NEO4J_HTTP_PORT` and
`AI4BRAIN_NEO4J_BOLT_PORT` override defaults in `.env`. The defaults avoid the existing
native app's 5173/8000 and legacy graph's 7474/7687. API-to-Neo4j traffic uses service DNS
`neo4j:7687`, not a host loopback address. The API is not published separately.

The Compose project is `ai4brain`. Its new named volumes do not import or overwrite the
native checkout's `data/ai4brain.sqlite3` or the earlier `minyar` project's Neo4j volume.
Use the explicit import procedure below if you want that existing history in this deployment.

## Persistence and daily operation

| Volume | Container path | Contents |
|---|---|---|
| `app_data` | `/var/lib/ai4brain` | Canonical SQLite, including WAL/SHM files and optional backups |
| `model_cache` | `/var/cache/ai4brain` | KittenTTS model and Hugging Face cache |
| `neo4j_data` | `/data` in Neo4j | Derived graph and Neo4j authentication state |

```sh
docker compose ps
docker compose logs --tail 100
docker compose stop
docker compose start --wait
```

Container replacements/rebuilds retain these volumes. `docker compose down` removes this
project's containers/network while retaining named volumes. Never remove volumes when you
intend to keep history. Changing `.env` does not change the password of an already initialized
Neo4j volume; keep the credential that initialized that volume.

Startup ordering is Neo4j health → API health → web. API health does not imply speech weights
are downloaded or a hosted provider is reachable. The API uses one worker for process-owned
coaching reservations and speech ownership. Nginx disables proxy buffering for SSE replies.

## Local speech and optional hosted coaching

The API image installs the inspected KittenML 0.9.4 ONNX path and native audio/phoneme
dependencies. It deliberately does not install the unrelated Torch/GPU model family.
First speech use fetches the public `KittenML/kitten-tts-mini-0.8` model; subsequent use
reuses `model_cache`. Model downloads need network access, while speech text is processed
locally. To prepopulate the cache before working offline:

```sh
docker compose exec -T api python -c "from backend.app.speech_service import get_engine; get_engine().warm(); print('Local voice cache ready')"
```

That command warms a separate process/cache; the API loads its own model on its next speech
request. For a machine with no network on first run, transfer an already populated model
cache explicitly. A source ZIP alone is not an offline image/model bundle. Runtime model
failures retain the app's text fallback. Human voice acceptance is separate from synthesis.

`GEMINI_API_KEY` / `GROQ_API_KEY` and model variables are optional server-side settings.
The default experience remains local until the learner explicitly opts in to hosted use.
Secrets are injected at runtime, never passed as Docker build arguments or baked into images.
Use `docker compose config --quiet` for validation; the ordinary expanded config can include
runtime credentials, so do not publish its output.

## Optional import of existing SQLite history

Import **before the first API startup**, using a fresh destination volume. The utility refuses
to overwrite any existing database. The source is mounted read-only and copied through
SQLite's backup API. This procedure is optional; packaging does not move existing records.

```powershell
docker compose build
docker compose run --rm --no-deps --volume "${PWD}/data:/import:ro" api python /app/deploy/sqlite_transfer.py import /import/ai4brain.sqlite3
docker compose up --detach --wait
```

On a POSIX shell, use `--volume "$PWD/data:/import:ro"`. The new Neo4j volume starts separately;
opening Evidence graph invokes the existing canonical-to-derived mirror path. Old graph data
is not copied over a new canonical store.

## Consistent SQLite backup

Choose a new destination filename each time; backup refuses overwrites. The online SQLite
backup includes committed WAL-backed data without copying a potentially inconsistent lone file.

```sh
docker compose exec -T api python /app/deploy/sqlite_transfer.py backup /var/lib/ai4brain/backups/learner-backup.sqlite3
docker compose cp api:/var/lib/ai4brain/backups/learner-backup.sqlite3 ./learner-backup.sqlite3
```

Downloaded backups are private learner data. Store them separately from source distributions.

## Portable source package

`scripts/package_compose.py` builds a source ZIP containing the full runtime app, frontend
public assets, dependency locks, Dockerfiles, Compose configuration, helper and this guide.
It also includes the judge-oriented README, its selected verification suites, two dated audit
reports, contracts, and review-draft report/deck/demo script. It excludes `.env`, SQLite files,
model caches, node_modules, local venvs, raw QA data/screenshots/logs, video work and developer
history. Extract it, configure `.env`, then run the startup command above.
Build the images on the destination machine; no registry publication is performed.

See `output/verification/docker-compose-2026-10-22/REPORT.md` in the working checkout for
the actual build/runtime checks and their limitations, rather than assuming validation from
the presence of these files.

References: [Compose health-based startup](https://docs.docker.com/compose/how-tos/startup-order/),
[Neo4j Docker initialization and existing volumes](https://neo4j.com/docs/operations-manual/current/docker/introduction/).
