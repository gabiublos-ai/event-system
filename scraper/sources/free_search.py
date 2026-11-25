"""Busca na web SEM CUSTO (não precisa de chave de API).

1. Pesquisa no DuckDuckGo (HTML) e no Bing (RSS) combinações de tema x tipo de evento x região.
2. Abre cada página encontrada e extrai o evento:
   - primeiro pelo JSON-LD (schema.org/Event), que é o dado mais confiável;
   - senão, por heurística: título da página + datas em português ("10 a 12 de maio de 2027")
     + cidade/UF + palavras-chave dos temas.
3. Guarda as URLs já visitadas em data/search_cache.json para não reabrir as mesmas páginas
   todo dia (revisita depois de N dias).
"""
from __future__ import annotations

import json
import logging
import os
import re
import time
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from urllib.parse import parse_qs, unquote, urlparse

from bs4 import BeautifulSoup

from scraper.core import DATA_DIR, Event, classify, guess_uf, norm, strip_accents
from scraper.sources.common import extract_jsonld_events, fetch

log = logging.getLogger("scraper")

CACHE_FILE = DATA_DIR / "search_cache.json"

SKIP_DOMAINS = (
    "facebook.com", "instagram.com", "linkedin.com", "youtube.com", "youtu.be", "twitter.com", "x.com",
    "tiktok.com", "wikipedia.org", "reddit.com", "pinterest.", "spotify.com", "apple.com", "google.",
    "bing.com", "duckduckgo.com", "amazon.", "mercadolivre", "reclameaqui", "glassdoor", "indeed.",
    "github.com", "medium.com/tag", "/tag/", "/tags/", "/categoria/", "/category/",
)

EVENT_WORDS = ["evento", "congresso", "summit", "conferência", "feira", "meetup", "demo day", "hackathon", "festival"]
REGION_WORDS = ["", "São Paulo", "Rio de Janeiro", "Belo Horizonte", "Porto Alegre", "Florianópolis", "Curitiba",
                "Recife", "Fortaleza", "Salvador", "Brasília", "Goiânia", "Manaus", "Belém", "Nordeste", "Norte"]

MONTHS = {
    "janeiro": 1, "fevereiro": 2, "marco": 3, "abril": 4, "maio": 5, "junho": 6, "julho": 7,
    "agosto": 8, "setembro": 9, "outubro": 10, "novembro": 11, "dezembro": 12,
    "jan": 1, "fev": 2, "mar": 3, "abr": 4, "mai": 5, "jun": 6, "jul": 7, "ago": 8, "set": 9,
    "out": 10, "nov": 11, "dez": 12,
}
_M = "|".join(sorted(MONTHS, key=len, reverse=True))
# "10 a 12 de maio de 2027", "10 e 11 de maio", "10 de maio de 2027", "10-12 maio 2027"
RX_TEXT = re.compile(
    rf"\b(\d{{1,2}})(?:\s*(?:a|e|-|–|ate)\s*(\d{{1,2}}))?\s*(?:de\s+)?({_M})\.?(?:\s*(?:de\s+)?(20\d\d))?\b")
# "10/05/2027" ou "10 a 12/05/2027"
RX_NUM = re.compile(r"\b(\d{1,2})(?:\s*(?:a|e|-|–)\s*(\d{1,2}))?/(\d{1,2})/(20\d\d)\b")


# ------------------------------------------------------------------ datas em português
def find_dates(text: str, ref: date | None = None) -> list[tuple[str, str]]:
    """Devolve (início, fim) ISO de todas as datas futuras encontradas, na ordem do texto."""
    ref = ref or date.today()
    t = strip_accents((text or "").lower())
    out: list[tuple[int, str, str]] = []
    for m in RX_TEXT.finditer(t):
        d1, d2, mon, yr = m.group(1), m.group(2), MONTHS[m.group(3)], m.group(4)
        year = int(yr) if yr else (ref.year if mon >= ref.month else ref.year + 1)
        out += _mk(m.start(), year, mon, int(d1), int(d2) if d2 else None)
    for m in RX_NUM.finditer(t):
        out += _mk(m.start(), int(m.group(4)), int(m.group(3)), int(m.group(1)),
                   int(m.group(2)) if m.group(2) else None)
    out.sort()
    lo, hi = ref.isoformat(), (ref + timedelta(days=550)).isoformat()
    return [(s, e) for _, s, e in out if lo <= s <= hi]


def _mk(pos, y, mon, d1, d2):
    try:
        s = date(y, mon, d1)
        e = date(y, mon, d2) if d2 and d2 >= d1 else s
        return [(pos, s.isoformat(), e.isoformat())]
    except ValueError:
        return []


# ------------------------------------------------------------------ buscadores
def search_duckduckgo(query: str) -> list[str]:
    r = fetch("https://html.duckduckgo.com/html/", method="POST", data={"q": query, "kl": "br-pt"}, retries=2)
    return parse_duckduckgo(r.text) if r else []


def parse_duckduckgo(html: str) -> list[str]:
    urls = []
    for a in BeautifulSoup(html, "html.parser").select("a.result__a, a.result-link"):
        href = a.get("href", "")
        if "uddg=" in href:
            href = unquote(parse_qs(urlparse(href).query).get("uddg", [""])[0])
        if href.startswith("http"):
            urls.append(href)
    return urls


def search_bing(query: str) -> list[str]:
    r = fetch("https://www.bing.com/search", params={"q": query, "format": "rss", "cc": "BR", "setlang": "pt-BR",
                                                     "count": "30"}, retries=2)
    return parse_bing_rss(r.text) if r else []


def parse_bing_rss(xml: str) -> list[str]:
    try:
        root = ET.fromstring(xml)
    except ET.ParseError:
        return []
    return [i.findtext("link") for i in root.iter("item") if (i.findtext("link") or "").startswith("http")]


ENGINES = {"duckduckgo": search_duckduckgo, "bing": search_bing}


# ------------------------------------------------------------------ extração de uma página
def extract_from_page(html: str, url: str, themes_cfg: dict) -> list[Event]:
    events = extract_jsonld_events(html, "busca_web", url)
    if events:
        for e in events:
            if not e.url or not e.url.startswith("http"):
                e.url = url
        return events
    return [e] if (e := heuristic_event(html, url, themes_cfg)) else []


def heuristic_event(html: str, url: str, themes_cfg: dict) -> Event | None:
    soup = BeautifulSoup(html, "html.parser")
    og = lambda p: (soup.find("meta", property=p) or {}).get("content")  # noqa: E731
    og_type = (og("og:type") or "").lower()
    if og_type == "article":  # notícia/blog: a data e o título não são do evento
        return None
    title = og("og:title") or (soup.title.string if soup.title and soup.title.string else "")
    title = re.split(r"\s+[|–—]\s+|\s+-\s+(?=[^-]*$)", title.strip())[0].strip()
    if not title or len(title) < 5 or len(title) > 140:
        return None
    desc = og("og:description") or (soup.find("meta", attrs={"name": "description"}) or {}).get("content") or ""
    for tag in soup(["script", "style", "nav", "footer", "noscript"]):
        tag.decompose()
    body = soup.get_text(" ", strip=True)[:8000]

    blob = f"{title} {desc}"
    themes = classify(blob, themes_cfg)
    if not themes:
        return None
    nb = norm(blob)
    if not any(norm(w).strip() in nb for w in EVENT_WORDS + ["edicao", "inscricoes", "ingressos", "palestrantes"]):
        return None
    dates = find_dates(f"{desc} {body}")
    if not dates:
        return None
    uf = guess_uf(desc, title) or guess_uf(body[:3000])
    online = any(w in norm(blob) for w in (" online ", " virtual ", " webinar "))
    if not uf and not online:
        return None
    start, end = dates[0]
    return Event(
        name=title, url=url, source="busca_web", start_date=start, end_date=end,
        description=desc, state=uf, format="online" if online and not uf else "presencial",
        themes=themes, date_confirmed=False,
    )


# ------------------------------------------------------------------ orquestração
def _queries(themes_cfg: dict, n: int) -> list[str]:
    year = date.today().year
    qs = []
    for cfg in themes_cfg.values():
        for term in cfg["search_terms"]:
            for ev in EVENT_WORDS:
                for reg in REGION_WORDS:
                    for yr in (year, year + 1):
                        qs.append(" ".join(x for x in (ev, term, reg, str(yr)) if x))
    # rotação diária: cada dia pega uma fatia diferente e espalhada das combinações
    step = 7919  # primo, embaralha sem aleatoriedade
    off = date.today().toordinal() * n
    return [qs[(off + i) * step % len(qs)] for i in range(min(n, len(qs)))]


def _load_cache() -> dict:
    try:
        return json.loads(CACHE_FILE.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _skip(url: str) -> bool:
    u = url.lower()
    return any(s in u for s in SKIP_DOMAINS) or u.endswith((".pdf", ".jpg", ".png", ".mp4"))


def discover(themes_cfg: dict, cfg: dict) -> list[Event]:
    n_queries = int(os.environ.get("FREE_SEARCH_QUERIES", cfg.get("queries_per_day", 60)))
    max_pages = int(cfg.get("max_pages_per_day", 250))
    revisit = int(cfg.get("revisit_days", 14))
    engines = [ENGINES[e] for e in cfg.get("engines", list(ENGINES)) if e in ENGINES]

    cache = _load_cache()
    today = date.today().isoformat()
    limit = (date.today() - timedelta(days=revisit)).isoformat()

    candidates: list[str] = []
    for q in _queries(themes_cfg, n_queries):
        for engine in engines:
            try:
                candidates += engine(q)
            except Exception as e:  # noqa: BLE001
                log.warning("busca '%s' falhou: %s", q, e)
            time.sleep(1.5)  # educado com os buscadores
    seen, todo = set(), []
    for u in candidates:
        u = u.split("#")[0]
        if u in seen or _skip(u) or cache.get(u, "") > limit:
            continue
        seen.add(u)
        todo.append(u)
    todo = todo[:max_pages]
    log.info("busca grátis: %d resultados, %d páginas novas para abrir", len(candidates), len(todo))

    def work(url):
        r = fetch(url, retries=1, timeout=20)
        if not r or "html" not in r.headers.get("content-type", "html"):
            return []
        try:
            return extract_from_page(r.text, r.url, themes_cfg)
        except Exception as e:  # noqa: BLE001
            log.debug("falha extraindo %s: %s", url, e)
            return []

    events: list[Event] = []
    with ThreadPoolExecutor(max_workers=8) as pool:
        for url, found in zip(todo, pool.map(work, todo)):
            cache[url] = today
            events += found
    # cache enxuto: só o que ainda está na janela de revisita
    cache = {u: d for u, d in cache.items() if d > limit}
    CACHE_FILE.write_text(json.dumps(cache, ensure_ascii=False, indent=0, sort_keys=True), encoding="utf-8")
    return events
