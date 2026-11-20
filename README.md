# SMR Digest — nuclear news & analytics with a focus on SMRs

A cross-platform app (iOS / Android, plus web for debugging) and its aggregation backend.

```
backend/   FastAPI · RSS/HTML parsing · SQLite + FTS5 · AI module · keyword push alerts
mobile/    Expo (React Native) + Expo Router
```

## What comes from each reference

| Reference | Mechanic | Where in the code |
|---|---|---|
| Particle / Artifact | Minimal card: source · date, serif headline, 3-bullet AI digest inside the card | `mobile/src/components/ui.tsx` (`ArticleCard`) |
| Feedly | Source aggregation, category tags, one story from several outlets collapsed into one card ("+1 source") | `backend/app/dedup.py`, `tagger.py`, `sources.py` |
| Readwise Reader | Reading mode for PDF reports, ask AI about the document, offline saving | `mobile/src/app/article/[id].tsx` (`AskBox`), `backend/app/ai.py`, `documents.py` |
| Crunchbase | Separate company and reactor cards: specs, stage, licensing status, their own news feed | `mobile/src/app/company/`, `reactor/`, `backend/app/catalog.py` |

## Sources

| Source | Method |
|---|---|
| World Nuclear News | RSS (full text in the feed) |
| NucNet | RSS |
| Atomic Energy 2.0 (atomic-energy.ru, Russian) | RSS `/news/rss.xml` |
| World Nuclear Association | HTML parsing of `/news-and-media` (cards that point to WNN are merged as duplicates) |
| European Commission · SMR | HTML parsing of the dated news list on the SMR page |
| Rosatom Science / CAIR (naukarosatom.ru, Russian) | HTML parsing of `/news/` |
| IAEA ARIS | Not a feed: it is the basis of the reactor catalog (`catalog.py`) |
| Custom | Any RSS feed or website: the server looks for `<link rel=alternate>`; with no feed it collects article links from the page |

Full text for items whose feed has only a teaser is fetched when the item is opened (a simplified Readability on the server).

## Running

**Backend**
```bash
cd backend
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env            # add OPENAI_API_KEY
set -a; source .env; set +a
.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
```
Sources refresh every `REFRESH_MINUTES` minutes, or on demand via `POST /api/refresh` / pull-to-refresh in the app. API docs: http://localhost:8000/docs

**Mobile app**
```bash
cd mobile
npm install
npx expo start          # i — iOS simulator, a — Android, w — web
```
The server address is detected automatically (the machine running Metro) and can be changed under Settings → Server.

## AI module
- **With an OpenAI key:** English headline translation (for Russian sources) and 3–5 bullets with facts and figures (`ai.DIGEST_PROMPT`). Questions about a document are answered from retrieved passages with [1], [2] references. Calls per refresh are capped by `AI_PER_RUN`.
- **Without a key:** "Key facts" — the sentences richest in numbers and units (MW, €, %), with no translation, so Russian items stay in Russian. Questions return the closest passages.
- Once a headline is translated, duplicates are re-checked so a Russian story merges with the English one.

## Push alerts
Keywords are set in Settings. On each refresh the server matches new items and sends pushes through the Expo Push API. Real pushes need an EAS build with a `projectId` (`npx eas-cli@latest init`) and a physical device; in Expo Go, simulators and web the subscriptions are stored but no push arrives.

## Offline
- Saved articles and reports are stored in full, including the digest (AsyncStorage).
- The last loaded feed for each category is cached, so the app opens without a network.
- Offline search runs over saved items.

## Project catalog
15 companies and 17 reactors: type, coolant, MWe/MWt, stage, licensing, sites. Statuses are based on developer data and ARIS **as of 2025** — verify against aris.iaea.org before public use. Each card's news feed is built by full-text search on the project's keywords (English and Russian).

## Next steps
- Embeddings for duplicate detection when headlines are worded very differently (title Jaccard similarity misses some NucNet/WNN pairs).
- Catalog editing in an admin panel and automatic import from ARIS.
- Accounts and syncing saved items across devices.

## Free, autonomous mode (GitHub Actions + GitHub Pages)

No server and no computer of yours needs to be running:

1. Every 2 hours `.github/workflows/update.yml` runs `python -m app.export`, which collects all sources, merges duplicates, builds digests and writes `site-data/*.json` (committed back to the repo, so history is kept).
2. The same workflow builds the app for the web (`EXPO_PUBLIC_DATA_URL` switches it to read those JSON files, see `mobile/src/lib/staticApi.ts`) and publishes it to `https://<your-github-name>.github.io/smr-digest/`.
3. On the phone: open that address in Safari (iPhone) or Chrome (Android) → **Share → Add to Home Screen**.

Setup once: create a public GitHub repository named `smr-digest`, push this project, then in the repo **Settings → Pages → Source: GitHub Actions**. Optional: add an `OPENAI_API_KEY` secret (Settings → Secrets and variables → Actions) for English translation and AI digests.

Custom sources in this mode: add `{"url": "https://…", "name": "…"}` entries to `backend/extra_sources.json`.

Not available in free mode (they need a live server): asking AI about a text, PDF import, keyword push alerts, adding sources from the app. The public site shows headline, excerpt, key facts and a link to the original — not the full article text, to respect the outlets' copyright (`CONTENT_MAX` controls this).
