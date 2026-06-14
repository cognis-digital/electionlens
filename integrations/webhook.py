#!/usr/bin/env python3
"""Minimal, dependency-free webhook forwarder for Cognis findings.

Reads JSON findings on stdin and POSTs them to a URL (SIEM/Slack/Jira bridge).
Usage:  <tool> scan . --format json | python integrations/webhook.py --url URL
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.request


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", required=True)
    ap.add_argument("--header", action="append", default=[], help="Key: Value")
    args = ap.parse_args()

    # Validate that the URL uses an http/https scheme to avoid surprising
    # protocols being passed to urlopen.
    url = args.url.strip()
    if not (url.startswith("http://") or url.startswith("https://")):
        print(
            "error: --url must start with http:// or https://",
            file=sys.stderr,
        )
        return 2

    raw = sys.stdin.read()
    if not raw.strip():
        print("error: stdin is empty — expected JSON findings", file=sys.stderr)
        return 2
    try:
        json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"error: stdin is not valid JSON: {e}", file=sys.stderr)
        return 2

    payload = raw.encode("utf-8")
    req = urllib.request.Request(url, data=payload, method="POST")
    req.add_header("Content-Type", "application/json")
    for h in args.header:
        k, _, v = h.partition(":")
        k = k.strip()
        v = v.strip()
        if not k:
            print(f"error: malformed --header {h!r} (expected 'Key: Value')",
                  file=sys.stderr)
            return 2
        req.add_header(k, v)

    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            print(f"posted {len(payload)} bytes -> {r.status}")
        return 0
    except Exception as e:
        print(f"webhook error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
