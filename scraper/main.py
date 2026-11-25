"""Atualização diária do mapa de eventos.

Uso:  python -m scraper.main            (coleta tudo)
      python -m scraper.main --offline  (só reprocessa a base curada + dados existentes)
"""
from __future__ import annotations

import argparse
import json
import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

from scraper.core import (CONFIG_DIR, DATA_DIR, SITE_DATA_DIR, UFS, Event, dedupe_key, is_brazil,
                          load_themes, merge, today)
from scraper.sources import ai_discovery, platforms

log = logging.getLogger("scraper")
BRT = timezone(timedelta(hours=-3))


def load_json(path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def curated_events() -> list[Event]:
    """Eventos cadastrados manualmente em data/seed_events.json (edite à vontade)."""
    out = []
    for d in load_json(DATA_DIR / "seed_events.json", []):
        d = {k: v for k, v in d.items() if k in Event.__dataclass_fields__}
        d.setdefault("source", "curadoria")
        d.setdefault("url", "")
        out.append(Event(**d))
    return out


def collect(themes: dict, sources: dict) -> tuple[list[Event], dict]:
    terms = sorted({t for cfg in themes.values() for t in cfg["search_terms"]})
    jobs = {}
    if sources.get("sympla", {}).get("enabled"):
        jobs["sympla"] = lambda: platforms.sympla(terms, sources["sympla"].get("pages", 3))
    if sources.get("eventbrite", {}).get("enabled"):
        jobs["eventbrite"] = lambda: platforms.eventbrite(terms, sources["eventbrite"].get("pages", 2))
    if sources.get("meetup", {}).get("enabled"):
        short = [cfg["search_terms"][0] for cfg in themes.values()]
        jobs["meetup"] = lambda: platforms.meetup(short, sources["meetup"].get("cities", []))
    for name in ("even3", "doity"):
        if sources.get(name, {}).get("enabled"):
            jobs[name] = (lambda n=name: platforms.search_pages(n, sources[n]["url"], terms))
    if sources.get("extra_pages"):
        jobs["agenda"] = lambda: platforms.extra_pages(sources["extra_pages"])
    if sources.get("ai_discovery", {}).get("enabled"):
        jobs["ia_web"] = lambda: ai_discovery.discover(themes)

    results, stats = [], {}
    with ThreadPoolExecutor(max_workers=len(jobs) or 1) as pool:
        futures = {name: pool.submit(fn) for name, fn in jobs.items()}
        for name, fut in futures.items():
            try:
                evs = fut.result()
            except Exception as e:  # noqa: BLE001
                log.error("fonte %s falhou: %s", name, e)
                evs = []
            stats[name] = len(evs)
            log.info("fonte %-10s -> %d brutos", name, len(evs))
            results += evs
    return results, stats


def build(raw: list[Event], themes: dict, keep_past_days: int) -> list[dict]:
    blocklist = {dedupe_key(x) for x in load_json(DATA_DIR / "blocklist.json", [])}
    previous = {e["id"]: e for e in load_json(SITE_DATA_DIR / "events.json", {}).get("events", [])}
    now = datetime.now(BRT).date().isoformat()
    cutoff = (today() - timedelta(days=keep_past_days)).isoformat()

    merged: dict[str, dict] = {}
    by_name: dict[str, str] = {}
    for ev in raw:
        ev.finalize(themes)
        if not ev.name or not ev.themes or not is_brazil(ev):
            continue
        if dedupe_key(ev.name) in blocklist:
            continue
        if ev.end_date and ev.end_date < cutoff:
            continue
        d = ev.to_dict()
        d["last_seen"] = now
        # mesmo nome sem data (ex.: recorrente não anunciado) se junta à edição com data
        nk = dedupe_key(ev.name)
        key = ev.id
        if nk in by_name and (not ev.start_date or not merged[by_name[nk]].get("start_date")):
            key = by_name[nk]
        if key in merged:
            merged[key] = merge(merged[key], d)
        else:
            merged[key] = d
            by_name.setdefault(nk, key)

    # mantém eventos vistos antes que ainda não passaram (a fonte pode ter falhado hoje)
    for pid, old in previous.items():
        if pid in merged:
            merged[pid]["first_seen"] = old.get("first_seen") or now
            continue
        if dedupe_key(old["name"]) in blocklist:
            continue
        if old.get("end_date") and old["end_date"] < cutoff:
            continue
        if not old.get("start_date") and old.get("source") != "curadoria" and old.get("last_seen", now) < cutoff:
            continue
        merged[pid] = old
    for d in merged.values():
        d["first_seen"] = d.get("first_seen") or now
        # na primeira execução tudo é "novo"; só marca a partir da segunda
        d["is_new"] = bool(previous) and d["first_seen"] >= (today() - timedelta(days=7)).isoformat()
    return sorted(merged.values(), key=lambda d: (d.get("start_date") or "9999", d["name"]))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--offline", action="store_true", help="não acessa a internet")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    themes = load_themes()
    sources = load_json(CONFIG_DIR / "sources.json", {})
    raw = curated_events()
    stats = {"curadoria": len(raw)}
    if not args.offline:
        collected, s = collect(themes, sources)
        raw += collected
        stats.update(s)
    events = build(raw, themes, sources.get("keep_past_days", 30))

    SITE_DATA_DIR.mkdir(parents=True, exist_ok=True)
    meta = {
        "updated_at": datetime.now(BRT).isoformat(timespec="minutes"),
        "total": len(events),
        "sources_raw": stats,
        "themes": {k: {"label": v["label"], "emoji": v["emoji"], "color": v["color"]} for k, v in themes.items()},
        "states": UFS,
    }
    payload = {"meta": meta, "events": events}
    (SITE_DATA_DIR / "events.json").write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    log.info("OK: %d eventos salvos em %s", len(events), SITE_DATA_DIR / "events.json")


if __name__ == "__main__":
    main()
