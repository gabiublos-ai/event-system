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
