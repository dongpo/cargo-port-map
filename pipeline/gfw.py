"""GFW v3 adapter. Secrets are read only from the process environment."""
import json, os, time, urllib.request, urllib.parse, urllib.error
BASE = 'https://gateway.api.globalfishingwatch.org/v3/events'
DATASET = 'public-global-port-visits-events:v4.0'
class APIError(RuntimeError): pass

def request(params, attempts=5):
    token = os.environ.get('GFW_API_TOKEN')
    if not token: raise APIError('Set GFW_API_TOKEN in the server-side process environment.')
    query = urllib.parse.urlencode(params)
    for attempt in range(attempts):
        req = urllib.request.Request(BASE+'?'+query, headers={
            'Authorization': 'Bearer '+token, 'Accept': 'application/json',
            'User-Agent': 'Mozilla/5.0 CargoPortConnectivity/0.1'})
        try:
            with urllib.request.urlopen(req, timeout=120) as response:
                result = json.load(response)
            if not isinstance(result.get('entries'), list) or not isinstance(result.get('total'), int):
                raise APIError('Unexpected GFW page schema; ingestion stopped.')
            meta = result.get('metadata', {})
            if meta.get('vesselTypes') != ['CARGO']:
                raise APIError('Response did not confirm the CARGO filter.')
            if meta.get('datasets') != [DATASET]:
                raise APIError('Dataset version differs from pinned v4.0.')
            return result
        except urllib.error.HTTPError as exc:
            if exc.code in (401,403):
                raise APIError(f'GFW HTTP {exc.code}: authentication/access failed.') from None
            if exc.code not in (429,500,502,503,504) or attempt == attempts-1:
                raise APIError(f'GFW HTTP {exc.code}; request stopped (response body withheld).') from None
            delay = min(60, int(exc.headers.get('Retry-After','0')) if exc.headers.get('Retry-After','').isdigit() else 0)
            time.sleep(max(delay,2**attempt))
        except (urllib.error.URLError, TimeoutError):
            if attempt == attempts-1: raise APIError('GFW network request failed after retries.') from None
            time.sleep(2**attempt)
    raise APIError('Retry limit reached')

def params(start, end, offset=0, limit=1000, vessels=()):
    p = {'datasets[0]':DATASET, 'vessel-types[0]':'CARGO',
         'vessel-types-operator':'INCLUDE', 'start-date':start, 'end-date':end,
         'offset':offset, 'limit':limit, 'sort':'+start', 'include-regions':'false'}
    p.update({f'vessels[{i}]':v for i,v in enumerate(vessels)})
    return p

def next_offset(page, offset):
    nxt = page.get('nextOffset')
    if offset + len(page['entries']) >= page['total']: return None
    if not page['entries'] or not isinstance(nxt,int) or nxt <= offset:
        raise APIError('Non-progressing or prematurely empty pagination; not marked complete.')
    return nxt
