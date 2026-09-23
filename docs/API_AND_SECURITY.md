# API contract and secret handling

Primary references, checked 2026-09-23:

- [GFW Events API](https://globalfishingwatch.org/our-apis/documentation/docs/v3/events/get-all-events)
- [Port-visit response example](https://api-doc.globalfishingwatch.org/our-apis/documentation/docs/examples/events/get-example4)
- [Anchorages, ports and voyages](https://globalfishingwatch.org/datasets-and-code-anchorages/)
- [GFW license and rate limits](https://globalfishingwatch.org/our-apis/documentation/docs/license-rate-limits)

Live verified request shape (no credential included):

```text
GET https://gateway.api.globalfishingwatch.org/v3/events
  datasets[0]=public-global-port-visits-events:v4.0
  vessel-types[0]=CARGO
  vessel-types-operator=INCLUDE
  start-date=2025-01-01
  end-date=2026-01-01
  sort=+start
  limit=1000
  offset=0
  include-regions=false
```

Cohort history requests add `vessels[0]`, `vessels[1]`, etc. Pagination follows `nextOffset` and verifies progress against `total`. The payload has `metadata`, `entries`, `limit`, `offset`, `nextOffset`, and `total`. Each port visit has `id`, `type`, `start`, `end`, `vessel`, and `port_visit.intermediateAnchorage`. Port and anchorage identifiers are distinct; preserve both. Vessel type is verified in normalized records, rather than relying solely on query filters.

The API client's token comes solely from `os.environ['GFW_API_TOKEN']`. It is sent only in an Authorization header to the fixed GFW gateway HTTPS origin. The code does not accept a custom upstream host, proxy credentials to the browser, or persist request headers. Exception messages omit response bodies and header values. Authentication failures stop immediately; transient network/429/5xx failures use bounded retries. The API key is not needed to run the map from already processed files.

Raw vessel identifiers remain in local SQLite/compressed audit exports. Only aggregate counts and port coordinates/names are published. The Vite development server denies local SQLite and compressed private exports; production serves only `dist`. Text from source port names uses `textContent`/DOM nodes, never HTML interpolation. No authentication secret is placed in Vite environment variables, URLs, generated files, screenshots, or source control.

GFW-derived data remains subject to GFW's noncommercial license and attribution requirements. AIS-based cargo classification is used exactly as provided; observations do not establish loading activity or physical cargo quantities.
