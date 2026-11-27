"""Portais de notícias de startups e inovação (Startups.com.br, Forbes, Exame, StartSe...).

Dois tipos de conteúdo viram eventos:
1. Listas de agenda ("Agenda 2026: 35 eventos de tecnologia...") — cada item da lista
   (título + parágrafo com data e local) vira um evento, com o link oficial quando houver.
2. Matérias sobre um evento ("ACE Summit aposta em... 2027") — nome do evento tirado do
   título, data e local tirados do texto.

As páginas abertas ficam em cache (data/news_cache.json) para não reler a mesma matéria.
Configuração (lista de portais, feeds e páginas): config/sources.json -> "news".
"""
from __future__ import annotations

import json
import logging
import re
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from scraper.core import DATA_DIR, Event, guess_uf, norm, relevant_themes
from scraper.sources.common import extract_jsonld_events, fetch
from scraper.sources.free_search import find_dates

log = logging.getLogger("scraper")
CACHE_FILE = DATA_DIR / "news_cache.json"

EVENT_HINT = re.compile(
    r"\b(evento|eventos|agenda|summit|congresso|feira|confer[eê]ncia|festival|f[oó]rum|semana|week|"
    r"demo ?day|hackathon|meetup|expo|edi[cç][aã]o|inscri[cç][oõ]es|ingressos|"
    r"event|events|conference|pitch competition|tickets|registration)\b", re.I)
LIST_HINT = re.compile(r"\b(agenda|calend[aá]rio|eventos (de|para)|\d+ eventos|principais eventos)\b", re.I)
EVENT_WORD = (r"Summit|Week|Conference|Confer[eê]ncia|Day|Festival|Fest|Expo|F[oó]rum|Forum|Congresso|Congress|"
              r"Feira|Meetup|Hackathon|Experience|Connect|Show|Talks|Awards|Arena|Hub|Weekend|Lab|Tour")
TRAIL = r"(?:\s+(?:Rio|Brasil|Brazil|Latam|LATAM|Latin America|Am[eé]rica Latina|Bras[ií]lia|Nordeste|Sul|SP|RJ|MG|RS|SC|PR|BH|POA|20\d\d))*"
NAME_AFTER = re.compile(
    rf"((?:[A-Z0-9ÁÉÍÓÚÂÊÔÃÕÇ][\w&.'’+-]*\s){{0,5}}(?:{EVENT_WORD}){TRAIL})")
MONTH_HEAD = re.compile(r"^(janeiro|fevereiro|mar[cç]o|abril|maio|junho|julho|agosto|setembro|outubro|novembro|dezembro)"
                        r"(\s+(de\s+)?20\d\d)?$", re.I)
BAD_LINK_HOSTS = ("google.", "facebook.", "instagram.", "linkedin.", "twitter.", "x.com", "youtube.", "wa.me", "t.me",
                  "tinyurl.", "bit.ly", "intranet", "whatsapp", "apple.com", "spotify.")
NAME_BEFORE = re.compile(
    r"((?:Congresso|Feira|F[oó]rum|Festival|Semana|Encontro|Confer[eê]ncia|Simp[oó]sio|Jornada)"
    r"(?:\s+(?:de|do|da|dos|das|e|&|[A-Z0-9ÁÉÍÓÚÂÊÔÃÕÇ][\w&.'’+-]*)){1,7})")
STOP_HEAD = re.compile(r"^(leia (tamb[eé]m|mais)|compartilh|veja (tamb[eé]m|mais)|newsletter|assine|"
                       r"publicidade|coment[aá]rios|relacionad|mais lidas|siga|sobre o autor|tags?)\b", re.I)


# ------------------------------------------------------------------ descoberta de matérias
def links_from_feed(xml: str) -> list[tuple[str, str]]:
    try:
        root = ET.fromstring(xml)
    except ET.ParseError:
        return []
    out = []
    for item in root.iter():
        tag = item.tag.split("}")[-1]
        if tag not in ("item", "entry"):
            continue
        title = link = ""
        for ch in item:
            t = ch.tag.split("}")[-1]
            if t == "title":
                title = (ch.text or "").strip()
            elif t == "link":
                link = (ch.text or ch.get("href") or "").strip()
        if link.startswith("http"):
            out.append((link, title))
    return out


def links_from_page(html: str, base: str) -> list[tuple[str, str]]:
    host = urlparse(base).netloc.replace("www.", "")
    out, seen = [], set()
    for a in BeautifulSoup(html, "html.parser").find_all("a", href=True):
        url = urljoin(base, a["href"]).split("#")[0]
        title = a.get_text(" ", strip=True)
        if url in seen or host not in urlparse(url).netloc or len(title) < 15:
            continue
        seen.add(url)
        out.append((url, title))
    return out


# ------------------------------------------------------------------ extração
def _content(soup: BeautifulSoup):
    for sel in ("article .entry-content", ".entry-content", ".post-content", ".article-content", ".article-body",
                "[itemprop=articleBody]", ".content-text", "article", "main"):
        el = soup.select_one(sel)
        if el and len(el.get_text(" ", strip=True)) > 300:
            return el
    return soup.body or soup


def _clean_name(text: str) -> str:
    text = re.sub(r"^\s*(\d{1,3}\s*[.)º°\-–—:]\s*|#\d+\s*)", "", text).strip(" -–—:|")
    text = re.sub(r"\s*\((?:[A-Z]{2}|online|on-line|h[ií]brido)\)\s*$", "", text, flags=re.I)
    text = re.split(r"\s+[|–—]\s+|:\s+(?=[a-záéíóú])", text)[0]
    return re.sub(r"\s+", " ", text).strip()


def _official_link(block_links: list[str], page_url: str) -> str | None:
    host = urlparse(page_url).netloc.replace("www.", "")
    for href in block_links:
        h = urlparse(href).netloc.replace("www.", "")
        if href.startswith("http") and h and "." in h and host not in h and not any(s in href for s in BAD_LINK_HOSTS):
            return href
    return None


def parse_listicle(html: str, url: str, themes_cfg: dict, default_themes: list[str], ref: date | None = None) -> list[Event]:
    """Cada subtítulo (h2/h3/h4 ou parágrafo em negrito) + texto seguinte = um evento."""
    soup = BeautifulSoup(html, "html.parser")
    body = _content(soup)
    heads = [h for h in body.find_all(["h2", "h3", "h4"])]
    if len(heads) < 3:  # algumas matérias usam <p><strong>Nome</strong></p>
        heads = [p for p in body.find_all("p") if p.find(["strong", "b"]) and
                 len(p.get_text(strip=True)) <= 90 and p.find(["strong", "b"]).get_text(strip=True) == p.get_text(strip=True)]
    events = []
    for h in heads:
        name = _clean_name(h.get_text(" ", strip=True))
        if not (3 <= len(name) <= 90) or STOP_HEAD.match(name) or MONTH_HEAD.match(name):
            continue
        texts, links = [], []
        for sib in h.find_next_siblings():
            if sib.name in ("h2", "h3", "h4") or (sib in heads):
                break
            texts.append(sib.get_text(" ", strip=True))
            links += [urljoin(url, a["href"]) for a in sib.find_all("a", href=True)]
            if sum(len(t) for t in texts) > 1500:
                break
        block = " ".join(texts)
        if not block:
            continue
        dates = _dates_for(name, block, ref)
        if not dates:
            continue
        uf = guess_uf(block[:600]) or guess_uf(name)
        online = bool(re.search(r"\b(online|virtual|remoto)\b", block[:600], re.I))
        if not uf and not online:
            continue
        th = relevant_themes(name, block, themes_cfg) or list(default_themes)
        if not th:
            continue
        desc = next((t for t in texts if len(t) > 60 and not re.match(r"^(quando|onde|data|local)\b", t, re.I)), "")
        events.append(Event(
            name=name, url=_official_link(links, url) or url, source="imprensa",
            start_date=dates[0][0], end_date=dates[0][1], description=desc[:400],
            state=uf, format="online" if online and not uf else "presencial",
            themes=th, date_confirmed=False,
        ))
    return events


def _dates_for(name: str, text: str, ref: date | None) -> list[tuple[str, str]]:
    """Datas futuras do texto; datas sem ano usam o ano de referência (ano da matéria).
    Se o nome traz um ano (ex.: 'Web Summit Rio 2027'), a data precisa ser desse ano."""
    today = date.today()
    ds = [d for d in find_dates(text, ref) if d[0] >= today.isoformat()]
    m = re.search(r"\b(20\d\d)\b", name)
    if m:
        ds = [d for d in ds if d[0].startswith(m.group(1))]
    return ds


def _ref_from(title: str, url: str) -> date | None:
    years = re.findall(r"\b(20\d\d)\b", f"{title} {url}")
    return date(int(max(years)), 1, 1) if years else None


def event_name_from_title(title: str) -> str | None:
    for rx in (NAME_BEFORE, NAME_AFTER):
        m = rx.search(title or "")
        if m:
            name = re.sub(r"(\s+(de|do|da|dos|das|e|&))+$", "", m.group(1).strip(" -–—:,."))
            words = name.split()
            if 2 <= len(words) <= 10 and not name.lower().startswith(("o ", "a ", "os ", "as ", "um ", "uma ")):
                return name
    return None


def parse_article(html: str, url: str, title: str, themes_cfg: dict, default_themes: list[str],
                  ref: date | None = None) -> list[Event]:
    evs = extract_jsonld_events(html, "imprensa", url)
    if evs:
        return evs
    ref = ref or _ref_from(title, url)
    if LIST_HINT.search(title or ""):
        return parse_listicle(html, url, themes_cfg, default_themes, ref)
    name = event_name_from_title(title)
    if not name:
        return []
    soup = BeautifulSoup(html, "html.parser")
    text = _content(soup).get_text(" ", strip=True)[:8000]
    # a data tem que estar perto de onde o texto cita o evento
    core = re.sub(r"\s+20\d\d$", "", name)
    idx = text.lower().find(core.lower())
    if idx < 0:
        return []
    window = text[max(0, idx - 150): idx + 700]
    dates = _dates_for(name, window, ref)
    if not dates:
        return []
    uf = guess_uf(window) or guess_uf(text[:3000])
    if not uf:
        return []
    th = relevant_themes(name, text[:2000], themes_cfg) or list(default_themes)
    links = [urljoin(url, a["href"]) for a in _content(soup).find_all("a", href=True)]
    m = soup.find("meta", attrs={"property": "og:description"}) or soup.find("meta", attrs={"name": "description"})
    return [Event(
        name=name, url=_official_link(links, url) or url, source="imprensa",
        start_date=dates[0][0], end_date=dates[0][1], description=(m.get("content") if m else "") or "",
        state=uf, themes=th, date_confirmed=False,
    )] if th else []


# ------------------------------------------------------------------ orquestração
def collect(themes_cfg: dict, cfg: dict) -> list[Event]:
    try:
        cache = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        cache = {}
    revisit = (date.today() - timedelta(days=int(cfg.get("revisit_days", 20)))).isoformat()
    max_articles = int(cfg.get("max_articles_per_day", 150))

    candidates: list[tuple[str, str, list[str]]] = []
    for portal in cfg.get("portals", []):
        default_th = portal.get("default_themes", [])
        found: list[tuple[str, str]] = []
        for feed in portal.get("feeds", []):
            r = fetch(feed, retries=1, timeout=15)
            if r:
                found += links_from_feed(r.text)
        for page in portal.get("pages", []):
            r = fetch(page, retries=1, timeout=15)
            if r:
                found += links_from_page(r.text, r.url)
        for art in portal.get("articles", []):  # matérias fixas (ex.: agenda anual)
            found.append((art, "agenda de eventos"))
        kept = [(u, t, default_th) for u, t in found if EVENT_HINT.search(t) or "/evento" in u or "/agenda" in u]
        log.info("imprensa %-22s %3d links, %3d sobre eventos", portal.get("name", "?"), len(found), len(kept))
        candidates += kept

    todo, seen = [], set()
    events: list[Event] = []
    for u, t, th in candidates:
        c = cache.get(u)
        if isinstance(c, dict) and c.get("date", "") > revisit:  # já lida: reaproveita os eventos extraídos
            if u not in seen:
                events += [Event(**{k: v for k, v in d.items() if k in Event.__dataclass_fields__}) for d in c.get("events", [])]
            seen.add(u)
            continue
        if u in seen:
            continue
        seen.add(u)
        todo.append((u, t, th))
    todo = todo[:max_articles]

    def work(item):
        u, t, th = item
        r = fetch(u, retries=1, timeout=15)
        if not r:
            return []
        try:
            soup_title = BeautifulSoup(r.text[:20000], "html.parser").title
            title = t if len(t) > 15 else (soup_title.get_text(strip=True) if soup_title else t)
            return parse_article(r.text, r.url, title, themes_cfg, th)
        except Exception as e:  # noqa: BLE001
            log.debug("imprensa: falha em %s: %s", u, e)
            return []

    with ThreadPoolExecutor(max_workers=6) as pool:
        for (u, _, _), evs in zip(todo, pool.map(work, todo)):
            cache[u] = {"date": date.today().isoformat(), "events": [
                {k: getattr(e, k) for k in ("name", "url", "source", "start_date", "end_date", "description",
                                            "state", "city", "format", "themes", "date_confirmed")} for e in evs]}
            events += evs
    old = (date.today() - timedelta(days=120)).isoformat()
    cache = {u: c for u, c in cache.items() if isinstance(c, dict) and c.get("date", "") > old}
    CACHE_FILE.write_text(json.dumps(cache, ensure_ascii=False, indent=0, sort_keys=True), encoding="utf-8")
    log.info("imprensa: %d matérias abertas, %d eventos extraídos", len(todo), len(events))
    return events


def cached_events() -> list[Event]:
    """Eventos já extraídos das matérias (usado quando o robô roda sem acessar a internet)."""
    try:
        cache = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return []
    out = []
    for c in cache.values():
        if isinstance(c, dict):
            out += [Event(**{k: v for k, v in d.items() if k in Event.__dataclass_fields__}) for d in c.get("events", [])]
    return out
