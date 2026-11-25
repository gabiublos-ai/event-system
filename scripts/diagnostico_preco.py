"""Diagnóstico: mostra onde as páginas de evento guardam o preço (roda no GitHub Actions)."""
import json
import re
import sys

import requests

from scraper.sources.common import HEADERS, extract_next_data

for url in sys.argv[1:]:
    print("=" * 100, "\n", url)
    r = requests.get(url, headers=HEADERS, timeout=20)
    print("status", r.status_code)
    nd = extract_next_data(r.text) or {}
    ev = (((nd.get("props") or {}).get("pageProps") or {}).get("hydrationData") or {}).get("eventHydration", {}).get("event")
    if ev:
        for k, v in ev.items():
            print("EVENT", k, "=", json.dumps(v, ensure_ascii=False)[:200])
    def walk(o, path=""):
        if isinstance(o, dict):
            for k, v in o.items():
                if re.search(r"fee|price|amount|currency|free|paid|ticket", k, re.I) and "localeMessages" not in path:
                    print("KEY", path + "." + k, "=", json.dumps(v, ensure_ascii=False)[:200])
                walk(v, path + "." + k)
        elif isinstance(o, list):
            for i, v in enumerate(o[:3]):
                walk(v, f"{path}[{i}]")
    walk(nd)
    apis = sorted(set(re.findall(r'["\'](https?://[^"\']*(?:api|ticket)[^"\']*|/api/[^"\']+)["\']', r.text)))
    print("APIS:", apis[:40])
