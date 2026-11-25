"""Diagnóstico: mostra onde as páginas de evento guardam o preço (roda no GitHub Actions)."""
import json
import re
import sys

from scraper.sources.common import HEADERS, extract_next_data
import requests

for url in sys.argv[1:]:
    print("=" * 100, "\n", url)
    try:
        r = requests.get(url, headers=HEADERS, timeout=20)
    except Exception as e:  # noqa: BLE001
        print("ERRO", e)
        continue
    print("status", r.status_code, "len", len(r.text))
    for m in re.finditer(r'<script[^>]*application/ld\+json[^>]*>(.*?)</script>', r.text, re.S):
        print("JSON-LD:", m.group(1)[:1500])
    nd = extract_next_data(r.text)
    if nd:
        def walk(o, path=""):
            if isinstance(o, dict):
                for k, v in o.items():
                    if re.search(r"price|preco|valor|ticket|amount|free|gratu|sale", k, re.I) and not isinstance(v, (dict, list)):
                        print("NEXT", path + "." + k, "=", str(v)[:80])
                    walk(v, path + "." + k)
            elif isinstance(o, list):
                for i, v in enumerate(o[:5]):
                    walk(v, f"{path}[{i}]")
        walk(nd)
    for m in list(re.finditer(r"R\$\s?[\d.,]+", r.text))[:8]:
        print("TEXTO:", r.text[max(0, m.start() - 80):m.end() + 20].replace("\n", " "))
    for k in ("price", "lowPrice", "gratuito", "Gratuito"):
        i = r.text.find(k)
        if i >= 0:
            print(f"ACHOU '{k}':", r.text[max(0, i - 150):i + 150].replace("\n", " "))
