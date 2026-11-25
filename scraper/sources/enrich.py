"""Completa os eventos com VALOR e DESCRIÇÃO abrindo a página de cada um.

As plataformas (Sympla, Eventbrite, Meetup...) publicam na página do evento os dados
estruturados (JSON-LD) com descrição e preço. O resultado fica em cache
(data/enrich_cache.json) para cada página ser aberta uma vez só.
"""
from __future__ import annotations

import html
import json
import logging
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta

from bs4 import BeautifulSoup

from scraper.core import DATA_DIR
from scraper.sources.common import _is_event, _walk, extract_next_data, fetch, fmt_brl, price_from_offers

log = logging.getLogger("scraper")
CACHE_FILE = DATA_DIR / "enrich_cache.json"
CACHE_VERSION = 3  # aumente para forçar reabrir todas as páginas
PAID = "Pago (valor no site)"
FREE_RX = re.compile(r"\b(evento gratuito|entrada gratuita|entrada franca|gratuito|gratuita|gratis|free)\b", re.I)
BRL_RX = re.compile(r"R\$\s?(\d{1,3}(?:\.\d{3})*(?:,\d{2})?|\d+(?:,\d{2})?)")


def clean_text(text: str) -> str:
    text = html.unescape(re.sub(r"<[^>]+>", " ", text or ""))
    return re.sub(r"\s+", " ", text).strip()


def summarize(text: str, limit: int = 240) -> str:
    """Primeiras frases até ~limit caracteres."""
    text = clean_text(text)
    if len(text) <= limit:
        return text
    cut = text[:limit]
    end = max(cut.rfind(". "), cut.rfind("! "), cut.rfind("? "))
    if end > 80:
        return cut[:end + 1]
    return cut[:cut.rfind(" ")].rstrip(",;:-") + "…"


def _amount(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def parse_page(html: str) -> dict:
    """Extrai {'description', 'price'} de uma página de evento."""
    soup = BeautifulSoup(html, "html.parser")
    desc, price = "", None
    for tag in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(tag.string or tag.get_text() or "")
        except json.JSONDecodeError:
            continue
        for d in _walk(data):
            if _is_event(d):
                desc = desc or clean_text(d.get("description") if isinstance(d.get("description"), str) else "")
                price = price or price_from_offers(d.get("offers"), d.get("isAccessibleForFree"))
    nd = extract_next_data(html) or {}
    # Sympla: dados do evento no __NEXT_DATA__ (preço exato só no checkout; aqui vem pago/gratuito)
    sev = (((nd.get("props") or {}).get("pageProps") or {}).get("hydrationData") or {}).get("eventHydration", {})
    sev = sev.get("event") if isinstance(sev, dict) else None
    if isinstance(sev, dict):
        desc = desc or clean_text(sev.get("strippedDetail") or "")
        kind = str(sev.get("paymentEventType") or "").lower()
        if not price and kind:
            price = ("Gratuito" if kind in ("free", "unpaid") else PAID if kind == "paid"
                     else "Gratuito e pago (ver no site)")
    # Meetup: feeSettings nulo = sem cobrança
    for d in _walk(nd):
        if "feeSettings" in d and not price:
            fee = d.get("feeSettings")
            if fee is None:
                price = "Gratuito"
            elif isinstance(fee, dict) and _amount(fee.get("amount")) is not None:
                price = fmt_brl(_amount(fee["amount"])) if str(fee.get("currency", "BRL")).upper() == "BRL" \
                    else f"{fee.get('currency')} {fee['amount']}"
            break
    if not desc:
        for attrs in ({"property": "og:description"}, {"name": "description"}):
            m = soup.find("meta", attrs=attrs)
            if m and m.get("content"):
                desc = clean_text(m["content"])
                break
    if not price and desc:
        if FREE_RX.search(desc):
            price = "Gratuito"
        else:
            vals = [float(v.replace(".", "").replace(",", ".")) for v in BRL_RX.findall(desc)]
            vals = [v for v in vals if v > 0]
            if vals:
                price = f"A partir de {fmt_brl(min(vals))}"
    return {"description": desc, "price": price}


def enrich(events: list[dict], max_pages: int = 400, refresh_days: int = 30) -> None:
    try:
        cache = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        cache = {}
    limit = (date.today() - timedelta(days=refresh_days)).isoformat()
    need = [e for e in events if e.get("url", "").startswith("http") and (not e.get("price") or len(e.get("description") or "") < 40)]
    def stale(info):
        return info.get("v") != CACHE_VERSION or info.get("date", "") <= limit
    todo = [e["url"] for e in need if stale(cache.get(e["url"], {}))]
    todo = list(dict.fromkeys(todo))[:max_pages] if max_pages else []
    log.info("enriquecimento: %d eventos sem valor/descrição, %d páginas para abrir", len(need), len(todo))

    def work(url):
        r = fetch(url, retries=1, timeout=12)
        return url, (parse_page(r.text) if r else {})

    with ThreadPoolExecutor(max_workers=8) as pool:
        for url, info in pool.map(work, todo):
            if not info and cache.get(url):
                continue
            if info.get("description"):
                info["description"] = info["description"][:1000]
            cache[url] = {**info, "date": date.today().isoformat(), "v": CACHE_VERSION}

    for e in events:
        info = cache.get(e.get("url", ""))
        if not info:
            continue
        if info.get("price"):
            e["price"] = info["price"]
        if len(info.get("description") or "") > len(e.get("description") or ""):
            e["description"] = info["description"][:600]
    for e in events:
        if (e.get("price") or "").startswith("R$ -"):
            e["price"] = None
        m = re.match(r"R\$ ([\d.,]+) a R\$ ([\d.,]+)$", e.get("price") or "")
        if m:
            lo, hi = (float(x.replace(".", "").replace(",", ".")) for x in m.groups())
            if hi > 10000 and hi > 20 * lo:  # valor fora da curva (erro de cadastro)
                e["price"] = f"A partir de R$ {m.group(1)}"
        e["summary"] = summarize(e.get("description") or "")
    old = (date.today() - timedelta(days=180)).isoformat()
    cache = {u: v for u, v in cache.items() if v.get("date", "") > old}
    CACHE_FILE.write_text(json.dumps(cache, ensure_ascii=False, indent=0, sort_keys=True), encoding="utf-8")
