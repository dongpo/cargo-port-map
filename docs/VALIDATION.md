# Validation record — 2026-09-23

## Live API

Authenticated server-side requests to `https://gateway.api.globalfishingwatch.org/v3/events` succeeded using the user-supplied environment credential. The source resolves to `public-global-port-visits-events:v4.0` and is pinned in the adapter.

Live discovery corrected two documentation assumptions: GET filters use `vessel-types[0]` and `vessel-types-operator`, not camelCase; ascending sort is `+start`, not `start`. Date matching includes overlapping visits, including visits starting before 2025. All captured cohort events have source vessel type `cargo`, and all belong to the 120 requested vessel IDs.

- Unpadded global 2025 query reported 2,222,500 events.
- Padded 2024-12-01–2026-02-01 global query reported 2,587,364 events. 40,000 were successfully checkpointed in the local full-extraction database before stopping. That incomplete extraction is not published in the map.
- All pages completed for the 120-vessel cohort: 22,660 distinct events.
- Build: 18,237 voyages, 3,709 directed OD pairs, 1,072 connected ports, 1,140 source ports including padding/isolated visits.
- 1,142 consecutive same-port visits collapsed; no overlapping/invalid rows were found in the delivered cohort.
- All monthly and annual counts reconcile to the individual voyage records. Every OD endpoint resolves to a preserved source port.
- JSON Schema validation passed for every normalized visit/voyage and every public JSON output.

## Tests and browser

Nine Python tests cover cargo restrictions, bad-visit barriers, distinct-port sequencing, cross-year/month assignment, UTC conversion, invalid coordinates, overlapping visits, gap rejection, pagination guards, interruption/resumption, incomplete-data refusal, idempotence, and aggregate conservation. Three JavaScript tests cover dateline splitting, degenerate geographic cases, direction filters, and counts. All passed. Production build passed.

The local standalone Playwright executable was blocked by the host's process sandbox. The included browser test remains runnable on an unrestricted development machine. Actual visual and interaction verification was performed in the Codex in-app browser:

- Geographic world polygons and port/route layers render; source quantization at the dateline was repaired.
- Full-year count 18,237; March count 1,525.
- Kaohsiung outbound full-year count 22; March count 2. These match independently calculated aggregate-file totals.
- Route detail: Kaohsiung → Xiamen, 19 voyages for the year; March has 2.
- Changing period closes the old popup. Port search, direction controls, reset, zoom and mobile layout were exercised.
- Responsive viewport had no horizontal document overflow.

The initial MapLibre dependency had a known advisory; it was replaced with MapLibre 6.11.0. Final npm audit: zero reported vulnerabilities. No credential is included in sources, client assets, data, logs or the archive. The final artifact was scanned for JWT-shaped values; no matches were found.

The renderer has a roughly 280 kB gzip vendor bundle; Vite emits a size advisory, not a build error. The client caps rendered edges at 3,000 per selection and discloses this. Every edge remains in the aggregates and participates in counts/rankings. Large deployments may later replace aggregate JSON with viewport queries or vector tiles.
