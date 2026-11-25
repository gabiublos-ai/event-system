from scraper.core import Event, classify, guess_uf, parse_date
from scraper.main import build
from scraper.sources.common import extract_jsonld_events
from scraper.sources.platforms import harvest_eventlike


def test_classify_themes():
    assert "ia" in classify("Summit de Inteligência Artificial Generativa")
    assert "bitcoin" in classify("Meetup Bitcoin e Lightning Network")
    assert set(classify("Demo Day da aceleradora de fintechs")) >= {"demo_day", "aceleradoras", "fintech"}
    assert classify("Show de rock com banda cover") == []


def test_guess_uf():
    assert guess_uf("Florianópolis") == "SC"
    assert guess_uf("Recife - PE") == "PE"
    assert guess_uf("Centro de Convenções, Minas Gerais") == "MG"
    assert guess_uf("Espaço para eventos") is None


def test_parse_date():
    assert parse_date("2027-03-10T09:00:00-03:00") == "2027-03-10"
    assert parse_date("05/08/2027") == "2027-08-05"


def test_jsonld():
    html = """<script type="application/ld+json">{"@context":"https://schema.org","@type":"ItemList",
    "itemListElement":[{"@type":"ListItem","item":{"@type":"BusinessEvent","name":"Fintech Summit",
    "startDate":"2030-05-01","url":"https://x.com/e","location":{"@type":"Place","name":"Expo",
    "address":{"addressLocality":"São Paulo","addressRegion":"SP"}}}}]}</script>"""
    evs = extract_jsonld_events(html, "t")
    assert len(evs) == 1 and evs[0].state == "SP" and evs[0].name == "Fintech Summit"


def test_harvest_and_dedupe(tmp_path, monkeypatch):
    import scraper.main as m
    monkeypatch.setattr(m, "SITE_DATA_DIR", tmp_path)
    data = {"data": [
        {"name": "Startup Day 2030", "start_date": "2030-01-10 10:00", "url": "/e/1",
         "location": {"city": "Curitiba", "state": "PR"}},
        {"name": "Startup Day", "start_date": "2030-01-10", "url": "https://other/e",
         "location": {"city": "Curitiba"}, "description": "Evento de startups com pitch"},
    ]}
    evs = harvest_eventlike(data, "sympla", "https://www.sympla.com.br/")
    assert len(evs) == 2
    from scraper.core import load_themes
    out = build(evs, load_themes(), 30)
    assert len([e for e in out if "startup day" in e["name"].lower()]) == 1


def test_event_finalize_region():
    e = Event(name="Healthtech Conference", url="u", source="t", city="Manaus", start_date="2030-02-01").finalize()
    assert e.state == "AM" and e.region == "Norte" and "healthtech" in e.themes


def test_free_search_dates():
    from datetime import date
    from scraper.sources.free_search import find_dates
    ref = date(2026, 11, 25)
    assert find_dates("Acontece de 10 a 12 de maio de 2027 no Recife", ref)[0] == ("2027-05-10", "2027-05-12")
    assert find_dates("Dia 3 de março, em SP", ref)[0] == ("2027-03-03", "2027-03-03")
    assert find_dates("Inscrições até 15/04/2027", ref)[0] == ("2027-04-15", "2027-04-15")
    assert find_dates("Edição passada: 5 de maio de 2025", ref) == []
    assert find_dates("1 de marketing digital", ref) == []


def test_free_search_parsers_and_heuristic():
    from scraper.core import load_themes
    from scraper.sources.free_search import extract_from_page, parse_bing_rss, parse_duckduckgo
    ddg = ('<div class="result"><a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fevento.com.br%2F'
           '&rut=x">Fintech Day</a><a class="result__snippet">Evento</a></div>')
    assert parse_duckduckgo(ddg) == [("https://evento.com.br/", "Fintech Day Evento")]
    rss = "<rss><channel><item><title>T</title><link>https://a.com/e</link></item></channel></rss>"
    assert parse_bing_rss(rss) == [("https://a.com/e", "T ")]
    html = """<html><head><title>Fintech Summit Nordeste 2027 | Site</title>
    <meta name="description" content="O maior evento de fintech do Nordeste. Recife - PE, 8 e 9 de junho de 2027."></head>
    <body>Inscrições abertas</body></html>"""
    ev = extract_from_page(html, "https://fs.com.br", load_themes())[0].finalize()
    assert ev.name == "Fintech Summit Nordeste 2027" and ev.state == "PE" and ev.start_date == "2027-06-08"
    assert "fintech" in ev.themes
    news = html.replace("<head>", '<head><meta property="og:type" content="article">')
    assert extract_from_page(news, "https://n.com", load_themes()) == []
