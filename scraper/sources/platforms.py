"""Coletores das plataformas de eventos: Sympla, Eventbrite, Meetup, Even3, Doity e páginas extras.

Cada coletor é tolerante a falhas: se a plataforma mudar o HTML ou bloquear, ele
registra um aviso e devolve lista vazia — os outros continuam funcionando.
"""
from __future__ import annotations

import logging
import re
from urllib.parse import quote, quote_plus, urljoin

from scraper.core import Event
from scraper.sources.common import extract_jsonld_events, extract_next_data, fetch

log = logging.getLogger("scraper")

DATE_KEYS = ("start_date", "startDate", "dateTime", "start", "starts_at", "startAt", "start_time", "date")
END_KEYS = ("end_date", "endDate", "endTime", "end", "ends_at", "endAt", "end_time")
NAME_KEYS = ("name", "title")
URL_KEYS = ("url", "eventUrl", "link", "permalink", "event_url")


def _first(d: dict, keys):
    for k in keys:
        v = d.get(k)
        if isinstance(v, dict):
            v = v.get("local") or v.get("utc") or v.get("date")
        if v:
            return v
    return None


def harvest_eventlike(obj, source: str, base_url: str = "") -> list[Event]:
    """Varre qualquer JSON procurando objetos com cara de evento (nome + data + url)."""
    out: list[Event] = []
    stack = [obj]
    while stack:
        cur = stack.pop()
        if isinstance(cur, list):
            stack.extend(cur)
            continue
        if not isinstance(cur, dict):
            continue
        stack.extend(v for v in cur.values() if isinstance(v, (dict, list)))
        name = _first(cur, NAME_KEYS)
        start = _first(cur, DATE_KEYS)
        url = _first(cur, URL_KEYS)
        if not (isinstance(name, str) and start and isinstance(url, str)):
            continue
        if not re.search(r"\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{4}", str(start)) and not isinstance(start, (int, float)):
            continue
        loc = cur.get("location") or cur.get("venue") or cur.get("address") or {}
        if isinstance(loc, list):
            loc = loc[0] if loc else {}
        city = state = venue = None
        if isinstance(loc, dict):
            city = loc.get("city") or loc.get("addressLocality") or loc.get("localized_area_display")
            state = loc.get("state") or loc.get("region") or loc.get("addressRegion")
            venue = loc.get("name")
        online = str(cur.get("event_type") or cur.get("eventType") or cur.get("type") or "").upper()
        fmt = "online" if "ONLINE" in online or cur.get("is_online_event") or cur.get("isOnline") else "presencial"
        img = cur.get("image") or cur.get("images") or cur.get("featuredEventPhoto")
        if isinstance(img, dict):
            img = img.get("original") or img.get("url") or img.get("lg") or img.get("highResUrl") or img.get("baseUrl")
        if isinstance(img, list):
            img = img[0] if img and isinstance(img[0], str) else None
        desc = cur.get("description") or cur.get("summary") or ""
        org = cur.get("organizer") or cur.get("company") or cur.get("group") or {}
        out.append(Event(
            name=name, url=urljoin(base_url, url), source=source,
            start_date=start, end_date=_first(cur, END_KEYS),
            description=re.sub(r"<[^>]+>", " ", desc if isinstance(desc, str) else ""),
            city=city if isinstance(city, str) else None,
            state=state if isinstance(state, str) and len(state) == 2 else None,
            venue=venue if isinstance(venue, str) else None,
            format=fmt,
            organizer=(org.get("name") if isinstance(org, dict) else org if isinstance(org, str) else None),
            image=img if isinstance(img, str) else None,
        ))
    return out


# ------------------------------------------------------------------ Sympla
def sympla(terms: list[str], pages: int = 3) -> list[Event]:
    events: list[Event] = []
    for term in terms:
        got = 0
        for page in range(1, pages + 1):
            body = {
                "service": "/v4/search",
                "params": {
                    "only": "name,start_date,end_date,images,event_type,duration_type,location,id,url,company,type,organizer",
                    "sort": "date", "q": term, "page": page, "type": "normal", "limit": 50,
                },
            }
            r = fetch("https://www.sympla.com.br/api/v1/search", method="POST", json=body, retries=2)
            if not r:
                break
            try:
                data = r.json()
            except ValueError:
                break
            found = harvest_eventlike(data, "sympla", "https://www.sympla.com.br/")
            events += found
            got += len(found)
            if len(found) < 10:
                break
        if got == 0:  # plano B: página de busca pública
            r = fetch(f"https://www.sympla.com.br/eventos?s={quote_plus(term)}")
            if r:
                events += extract_jsonld_events(r.text, "sympla", r.url)
                nd = extract_next_data(r.text)
                if nd:
                    events += harvest_eventlike(nd, "sympla", "https://www.sympla.com.br/")
    return events


# ------------------------------------------------------------------ Eventbrite
def eventbrite(terms: list[str], pages: int = 2) -> list[Event]:
    events: list[Event] = []
    for term in terms:
        tslug = re.sub(r"\s+", "-", term.strip().lower())
        for page in range(1, pages + 1):
            url = f"https://www.eventbrite.com.br/d/brazil/{quote(tslug)}/?page={page}"
            r = fetch(url)
            if not r:
                break
            found = extract_jsonld_events(r.text, "eventbrite", url)
            m = re.search(r"window\.__SERVER_DATA__\s*=\s*(\{.*?\});\s*</script>", r.text, re.S)
            if m:
                import json
                try:
                    found += harvest_eventlike(json.loads(m.group(1)), "eventbrite")
                except ValueError:
                    pass
            events += found
            if not found:
                break
    return events


# ------------------------------------------------------------------ Meetup
def meetup(terms: list[str], cities: list[str]) -> list[Event]:
    events: list[Event] = []
    for city in cities:
        for term in terms:
            url = (f"https://www.meetup.com/find/?keywords={quote_plus(term)}"
                   f"&location=br--{quote(city)}&source=EVENTS")
            r = fetch(url, retries=2)
            if not r:
                continue
            nd = extract_next_data(r.text)
            found = extract_jsonld_events(r.text, "meetup", url)
            if nd:
                found += harvest_eventlike(nd, "meetup", "https://www.meetup.com/")
            for e in found:
                if not e.city:
                    e.city = city
            events += found
    return events


# ------------------------------------------------------------------ Even3 / Doity / genérico
def search_pages(source: str, url_template: str, terms: list[str]) -> list[Event]:
    events: list[Event] = []
    for term in terms:
        url = url_template.format(q=quote_plus(term))
        r = fetch(url, retries=2)
        if not r:
            continue
        events += extract_jsonld_events(r.text, source, url)
        nd = extract_next_data(r.text)
        if nd:
            events += harvest_eventlike(nd, source, url)
    return events


def extra_pages(urls: list[str]) -> list[Event]:
    """Páginas de agenda de organizadores (Cubo, Abstartups, Porto Digital...) com JSON-LD."""
    events: list[Event] = []
    for url in urls:
        r = fetch(url, retries=2)
        if r:
            events += extract_jsonld_events(r.text, "agenda", url)
    return events
