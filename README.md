# Global Cargo Port Connectivity Map v0.1

A runnable MapLibre geographic map and reproducible, server-side Python ETL using real Global Fishing Watch (GFW) cargo port visits. Route widths encode **observed vessel voyages, not trade**. The initial year is 2025.

## Start the map

Requires Node.js 20.19+ or 22.12+ (tested on 24), npm, and Python 3.11+.

```sh
npm ci
npm run dev
```

Open http://127.0.0.1:5173. The included processed data works immediately, with no API credential. For a production build:

```sh
npm run build
python3 -m http.server 5173 --bind 127.0.0.1 --directory dist
```

Only serve `dist`, not the project root. Basemap geometry is bundled Natural Earth 1:50m data. Optional interface web fonts use Google Fonts; the map geometry and local data do not require an internet connection. Country borders are shown without country labels. WebGL is required.

## What is included—and what is not

The initial map uses a **live-data cohort of 120 cargo vessels**, not the complete worldwide fleet and not synthetic data. All 22,660 returned events belong to those vessels and have GFW type `cargo`. Their complete API histories within 2024-12-01 through 2026-02-01 were fetched. These produce 18,237 destination-arrival-year 2025 voyages, 3,709 directed connections, and 1,072 ports participating in those voyages. There are 1,140 distinct source ports including padding-only and isolated visits.

The cohort is a deterministic convenience sample discovered at eight offsets of the start-sorted 2025 event query; it is **not random or statistically representative**. Twenty selected vessels had no qualifying 2025 voyages. Do not infer global totals, market shares, trade, or vessel activity rankings from this sample. See `public/data/manifest.json` for retrieval time, source version, coverage, and processing counters.

Live validation found 2,222,500 events in the unpadded 2025 global query and 2,587,364 in the padded extraction window. A full extraction was smoke-tested through 40,000 events, then stopped with its checkpoint intact in `data/global.sqlite`. It is **incomplete and is not used by the map**. The deliverable includes a working full-fleet ingestion command, not a claim that the entire global extraction finished.

## Map controls

- Choose full year or a month (UTC destination arrival).
- Search/select a port; switch inbound, outbound, or both directions.
- Click port nodes or ranked connections. Click a route for its directed OD and voyage count.
- Zoom/pan or reset the geographic view.
- For performance, draw the strongest 3,000 connections in the current selection, disclosed above the map. Counts and rankings use every connection; selecting a port reveals its network. Width is linear in count within each selection: `9 × count / maximum_count` pixels. The scale changes when filters change; very low counts can be faint.

Geographic lines are great-circle **OD connectors derived from observed consecutive port visits**. They are not reconstructed AIS tracks or navigable sea routes, and can cross land. Dateline connections are split correctly.

## GitHub checkout

The repository includes the processed map data and basemap, so `npm ci` followed by `npm run dev` works immediately. Raw SQLite snapshots and compressed vessel-level exports stay local and are not committed. In a fresh clone, run ingestion before rebuilding aggregates or running source-to-map validation. The existing full-extraction checkpoint is available only in the original local project folder.

## Live ingestion: environment secret only

The supplied credential was used only in server-side process memory/environment. It is not stored in this project. No `.env` or token-bearing files are required. In a fresh terminal, enter a credential with a hidden prompt (the entered value does not become a shell command or history entry):

```sh
# zsh, the default macOS shell
read -rs 'GFW_API_TOKEN?GFW API token: '
export GFW_API_TOKEN
```

For Bash: `read -rs -p 'GFW API token: ' GFW_API_TOKEN; export GFW_API_TOKEN`.

Resume/download the complete global cargo query, then publish its aggregates only after all pages finish:

```sh
python3 -m pipeline.ingest --year 2025 --page-size 10000 --db data/global.sqlite
python3 -m pipeline.build --db data/global.sqlite
python3 -m pipeline.validate --db data/global.sqlite
unset GFW_API_TOKEN
npm run build
```

Expect a large download, many API calls, and several GB of disk usage. Page size defaults to 1,000; 10,000 was tested live. Interrupted runs resume from committed pages. A different scope/year needs a separate database. The current implementation fetches sequentially to keep API load bounded. The CLI refuses to publish an incomplete extraction. Use a new database for a fresh upstream snapshot rather than resuming an old completed database.

Recreate the small cohort instead:

```sh
python3 -m pipeline.ingest --year 2025 --sample-vessels 120 --db data/sample.sqlite
python3 -m pipeline.build --db data/sample.sqlite
```

Existing sample data is already complete. Delete nothing to experiment: choose another database path. Snapshot consistency is limited by the live upstream dataset: v4.0 identifies a pipeline version, not an immutable snapshot. Saved raw events, page hashes, cohort IDs, and timestamps support reproducibility of the delivered aggregates.

## Processing rules

`GFW events → durable raw SQLite pages → normalized visits → chronological vessel sequences → directed voyages → monthly/yearly OD JSON → MapLibre GeoJSON layers`

1. Pin `public-global-port-visits-events:v4.0`; request `vessel-types[0]=CARGO`. Validate response metadata and event shape. Normalize only explicit cargo records; no fishing/carrier/tanker substitution.
2. Deduplicate raw events by source event ID. Store raw source records server-side. Preserve vessel ID/SSVID, port and anchorage IDs, original names and coordinates, arrival/departure, confidence, and provenance in normalized records.
3. Sort by vessel ID, UTC arrival, event ID. Use `intermediateAnchorage.id` as the port identity. Collapse consecutive visits to the same ID; preserve the earliest arrival and latest departure. Different source port IDs remain different even when physically close. These can include anchorage subdivisions, not necessarily commercial port authorities.
4. Pair successive distinct ports for the same vessel. Exclude non-cargo/missing-port/invalid-coordinate records as sequence barriers. An unorderable timestamp excludes that vessel. Overlapping distinct-port visits block pairing through the ambiguous interval. Do not skip a bad visit and invent a connection across it.
5. Reject travel gaps over 90 days (configurable with `--max-gap-days`). Assign voyage year/month to **destination arrival in UTC**. December 2024/January 2026 padding reduces but does not eliminate boundary censoring.
6. Aggregate directed OD counts. TEU, cargo tonnes, and USD trade value remain `null`; they are never estimated from voyages. Store one file per month and one annual file, loading only the active period. Map geometry is computed only for the strongest 3,000 current connections.

Normalized visits retain each exact source coordinate. The map uses one deterministic, observed representative coordinate per source port ID (the first in event-ID order), not a fabricated port centroid. The raw source JSON retains start/intermediate/end anchorages and vessel identity details. Confidence values are preserved, not used as an undisclosed selection filter. Repeated short shuttles can dominate counts.

## Project layout

- `pipeline/gfw.py`: authenticated HTTPS requests, pinned source, pagination guards, bounded retry/backoff; error bodies/headers are not logged.
- `pipeline/ingest.py`: raw events, page hashes and retrieval checkpoints in SQLite.
- `pipeline/build.py`: normalization, sequencing, monthly and annual aggregates; local compressed visit/voyage exports.
- `pipeline/validate.py`: source-to-map count and reference checks.
- `schemas/`: JSON Schema contracts for normalized visits, voyages, ports and period aggregates.
- `web/`: interface, MapLibre rendering, antimeridian-safe geography.
- `public/data/`: client-safe aggregate outputs only. No vessel IDs or credentials.
- `data/`: local raw/normalized provenance; ignored by git and denied by the Vite development server.
- `docs/`: validation results, source caveats and security notes.

The normalized `data/visits.jsonl.gz` and `data/voyages.jsonl.gz` contain vessel identifiers for local research. Do not publish them unintentionally. The downloadable archive includes the completed sample SQLite snapshot, compressed audit records and production build, but excludes the partial global database and installed dependencies. The full local project folder retains the global checkpoint for resuming.

## Tests

```sh
python3 -m unittest discover -s tests
python3 -m pipeline.validate --db data/sample.sqlite
npm test
npm run build
# Optional automated browser tests, with npm run dev running:
npx playwright install chromium
node tests/browser.mjs
```

Browser launch was restricted by the host sandbox during this session; actual UI verification used the Codex in-app browser instead. See `docs/VALIDATION.md` for checks performed and their results.

## Attribution and caveats

[Powered by Global Fishing Watch](https://globalfishingwatch.org). Copyright 2026 Global Fishing Watch, Inc., https://globalfishingwatch.org/our-apis/. GFW API data is subject to its [terms and CC BY-NC 4.0 noncommercial license](https://globalfishingwatch.org/our-apis/documentation/docs/license-rate-limits). This code does not grant additional data rights.

Basemap: [Natural Earth](https://www.naturalearthdata.com/about/terms-of-use/), public domain, distributed through `world-atlas`; regenerate with `node scripts/basemap.mjs`. Renderer: MapLibre GL JS (BSD-3-Clause). Other packages retain their licenses.

AIS reception, vessel classification, fragmented vessel identities, port detection and source revisions affect counts. A visit is not proof of cargo loading, unloading, quantity, trade value or commercial purpose. Nearby distinct anchorages can inflate apparent port-to-port counts. Missing visits can cause observed consecutive ports to differ from actual consecutive calls. No knowledge graph or track reconstruction is included in v0.1.
