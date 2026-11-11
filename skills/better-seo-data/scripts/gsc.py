#!/usr/bin/env python3
"""Read Google Search Console data. Stdlib only.

Lives inside the better-seo-data skill; run it by path.

    python <skill-dir>/scripts/gsc.py sites
    python <skill-dir>/scripts/gsc.py report --property sc-domain:example.com --days 28
    python <skill-dir>/scripts/gsc.py opportunities --property sc-domain:example.com
    python <skill-dir>/scripts/gsc.py report --property ... --json gsc.json

Credentials, in order:
  1. --token / GSC_ACCESS_TOKEN     an already-minted OAuth access token
  2. --credentials PATH / GSC_CREDENTIALS   JSON with client_id, client_secret,
     refresh_token (refreshed automatically; plain HTTPS, no crypto needed)

Exit 0 on success, 2 when the API fails, 3 when credentials are missing or
invalid. 3 always prints how to fix it, never a stack trace.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

API_BASE = os.environ.get("GSC_API_BASE", "https://searchconsole.googleapis.com/webmasters/v3")
TOKEN_URL = os.environ.get("GSC_TOKEN_URL", "https://oauth2.googleapis.com/token")
DEFAULT_CREDENTIALS = "~/.config/better-seo/gsc.json"
SCOPES = "https://www.googleapis.com/auth/webmasters.readonly"

# Google finalises data with a lag; asking for today returns partial rows.
DEFAULT_LAG_DAYS = 3


SECRET_KEYS = ("access_token", "refresh_token", "client_secret", "id_token")

def redact(text: str) -> str:
    """Strip credential values from anything we are about to print.

    An OAuth token endpoint can echo the form it received inside an error body,
    and a TLS-intercepting proxy can echo more. Printing that body verbatim
    would put a refresh token in the user's terminal, shell history, or a pasted
    bug report.
    """
    for key in SECRET_KEYS:
        text = re.sub(rf'("{key}"\s*:\s*")[^"]*(")', r'\1[redacted]\2', text)
        text = re.sub(rf'({key}=)[^&\s"]+', r'\1[redacted]', text)
    return re.sub(r"(ya29\.[A-Za-z0-9._-]{10,})", "[redacted]", text)

class NotConfigured(Exception):
    """No usable credentials. Exit 3, with instructions."""


class ApiError(Exception):
    """The API said no. Exit 2."""


def setup_help() -> str:
    return """\
No Search Console credentials found. Pick one:

  1. Quick and temporary - mint a token in the OAuth Playground
     (https://developers.google.com/oauthplayground, scope
     https://www.googleapis.com/auth/webmasters.readonly) and export it:

       export GSC_ACCESS_TOKEN=ya29....

  2. Durable - create a Desktop OAuth client in Google Cloud, authorise once,
     then save a file at ~/.config/better-seo/gsc.json:

       {"client_id": "...", "client_secret": "...", "refresh_token": "..."}

     Or point GSC_CREDENTIALS at wherever you keep it.

Never commit that file. Service-account keys are not supported: signing an RS256
JWT needs crypto that Python's stdlib does not provide, and shipping a
half-working signer would be worse than saying so.

The property must already exist in Search Console and be verified."""


def resolve_credentials(args) -> dict:
    token = args.token or os.environ.get("GSC_ACCESS_TOKEN", "")
    if token.strip():
        return {"kind": "token", "access_token": token.strip()}

    path = Path(args.credentials or os.environ.get("GSC_CREDENTIALS", DEFAULT_CREDENTIALS))
    path = path.expanduser()
    if not path.is_file():
        raise NotConfigured(setup_help())
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise NotConfigured(f"{path} is not valid JSON: {e}\n\n{setup_help()}")
    missing = [k for k in ("client_id", "client_secret", "refresh_token") if not data.get(k)]
    if missing:
        raise NotConfigured(f"{path} is missing {', '.join(missing)}.\n\n{setup_help()}")
    return {"kind": "refresh", "path": str(path), **{k: data[k] for k in
            ("client_id", "client_secret", "refresh_token")}}


def post_form(url: str, fields: dict, insecure: bool, timeout: float = 30.0) -> dict:
    body = urllib.parse.urlencode(fields).encode()
    req = urllib.request.Request(url, data=body, headers={
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "application/json",
    })
    ctx = ssl._create_unverified_context() if insecure else None
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
            return json.loads(r.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as e:
        detail = redact(e.read().decode("utf-8", "replace")[:500])
        raise ApiError(f"token endpoint {e.code}: {detail}")
    except (urllib.error.URLError, OSError, ValueError) as e:
        raise ApiError(f"token endpoint unreachable: {e}")


def access_token(creds: dict, insecure: bool) -> str:
    if creds["kind"] == "token":
        return creds["access_token"]
    default_url = "https://oauth2.googleapis.com/token"
    if TOKEN_URL.rstrip("/") != default_url:
        # GSC_TOKEN_URL exists for testing a mock. Sending a real refresh token
        # to a host that is not Google is how a credential walks out the door.
        print(f"warning: posting OAuth credentials to non-Google endpoint {TOKEN_URL}",
              file=sys.stderr)
    data = post_form(TOKEN_URL, {
        "grant_type": "refresh_token",
        "client_id": creds["client_id"],
        "client_secret": creds["client_secret"],
        "refresh_token": creds["refresh_token"],
    }, insecure)
    token = data.get("access_token", "")
    if not token:
        raise NotConfigured(
            "Refresh failed: Google returned no access_token. The refresh token is "
            f"probably revoked or was issued for a different client.\n\n{setup_help()}")
    return token


def call(path: str, token: str, insecure: bool, payload: dict | None = None,
         timeout: float = 60.0) -> dict:
    url = API_BASE.rstrip("/") + path
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, headers={
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    })
    ctx = ssl._create_unverified_context() if insecure else None
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
            raw = r.read().decode("utf-8", "replace")
            return json.loads(raw) if raw.strip() else {}
    except urllib.error.HTTPError as e:
        detail = redact(e.read().decode("utf-8", "replace")[:500])
        if e.code in (401, 403):
            raise NotConfigured(
                f"The token was rejected ({e.code}). It expired, lacks the "
                f"webmasters.readonly scope, or the property is not verified for "
                f"this account.\n\n{detail}\n\n{setup_help()}")
        raise ApiError(f"{e.code} on {path}: {detail}")
    except (urllib.error.URLError, OSError, ValueError) as e:
        raise ApiError(f"unreachable {path}: {e}")


def date_range(days: int, lag: int) -> tuple[str, str]:
    today = dt.datetime.now(dt.timezone.utc).date()
    end = today - dt.timedelta(days=max(lag, 0))
    start = end - dt.timedelta(days=max(days, 1) - 1)
    return start.isoformat(), end.isoformat()


def query(token: str, prop: str, start: str, end: str, dimensions: list[str],
          limit: int, insecure: bool) -> list[dict]:
    path = f"/sites/{urllib.parse.quote(prop, safe='')}/searchAnalytics/query"
    payload = {
        "startDate": start,
        "endDate": end,
        "dimensions": dimensions,
        "rowLimit": limit,
        "type": "web",
    }
    data = call(path, token, insecure, payload)
    return data.get("rows", []) or []


def summarise(rows: list[dict], key: str) -> list[dict]:
    """Normalise API rows into a flat shape with ctr as a percentage."""
    out = []
    for r in rows:
        out.append({
            key: (r.get("keys") or [""])[0],
            "clicks": r.get("clicks", 0),
            "impressions": r.get("impressions", 0),
            "ctr": round((r.get("ctr") or 0) * 100, 2),
            "position": round(r.get("position") or 0, 1),
        })
    return out


def find_opportunities(pages: list[dict], min_impressions: int = 100,
                       max_ctr: float = 2.0) -> list[dict]:
    """Pages Google shows often but nobody clicks.

    A page ranking on page one with a 0.4% CTR is a title/description problem,
    not a ranking problem -- and that is fixable with /seo-build.
    """
    out = [p for p in pages
           if p["impressions"] >= min_impressions and p["ctr"] <= max_ctr]
    out.sort(key=lambda p: (-p["impressions"], p["ctr"]))
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Read Google Search Console data.")
    ap.add_argument("action", choices=["sites", "report", "opportunities"])
    ap.add_argument("--property", help="e.g. sc-domain:example.com or https://example.com/")
    ap.add_argument("--days", type=int, default=28, help="lookback window (default 28)")
    ap.add_argument("--lag", type=int, default=DEFAULT_LAG_DAYS,
                    help=f"days to skip for finalised data (default {DEFAULT_LAG_DAYS})")
    ap.add_argument("--limit", type=int, default=100, help="rows per dimension (default 100)")
    ap.add_argument("--min-impressions", type=int, default=100,
                    help="opportunities: ignore pages below this (default 100)")
    ap.add_argument("--max-ctr", type=float, default=2.0,
                    help="opportunities: flag pages at or below this CTR %% (default 2.0)")
    ap.add_argument("--token", help="OAuth access token (or set GSC_ACCESS_TOKEN)")
    ap.add_argument("--credentials", help=f"credentials JSON (default {DEFAULT_CREDENTIALS})")
    ap.add_argument("--json", help="write the result to this path")
    ap.add_argument("--quiet", action="store_true")
    ap.add_argument("--insecure", action="store_true")
    args = ap.parse_args(argv)

    try:
        creds = resolve_credentials(args)
        token = access_token(creds, args.insecure)

        if args.action == "sites":
            data = call("/sites", token, args.insecure)
            entries = data.get("siteEntry", []) or []
            result = {"action": "sites", "count": len(entries),
                      "sites": [{"site": e.get("siteUrl"),
                                 "permission": e.get("permissionLevel")}
                                for e in entries]}
        else:
            if not args.property:
                ap.error("--property is required for report and opportunities")
            start, end = date_range(args.days, args.lag)
            by_page = summarise(query(token, args.property, start, end,
                                      ["page"], args.limit, args.insecure), "page")
            by_query = summarise(query(token, args.property, start, end,
                                       ["query"], args.limit, args.insecure), "query")
            result = {
                "action": args.action,
                "property": args.property,
                "start": start,
                "end": end,
                "lag_days": args.lag,
                "totals": {
                    "clicks": sum(p["clicks"] for p in by_page),
                    "impressions": sum(p["impressions"] for p in by_page),
                },
                "pages": by_page,
                "queries": by_query,
            }
            if args.action == "opportunities":
                result["opportunities"] = find_opportunities(
                    by_page, args.min_impressions, args.max_ctr)

    except NotConfigured as e:
        print(json.dumps({"error": "not_configured", "detail": str(e)},
                         ensure_ascii=False), file=sys.stderr)
        return 3
    except ApiError as e:
        print(json.dumps({"error": "api", "detail": str(e)}), file=sys.stderr)
        return 2

    blob = json.dumps(result, indent=2, ensure_ascii=False)
    if args.json:
        Path(args.json).write_text(blob, encoding="utf-8")
    if not args.quiet:
        print(blob)
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass
    sys.exit(main())
