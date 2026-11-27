from scraper.core import Event, classify, guess_uf, parse_date
from scraper.main import build
from scraper.sources.common import extract_jsonld_events
from scraper.sources.platforms import harvest_eventlike


def test_ai_case_sensitive():
    from scraper.core import relevant_themes, is_excluded
    assert "ia" in relevant_themes("Data & AI in Practice")
    assert relevant_themes("E AÍ, POPULAÇÃO! Sampler de danças") == [] or is_excluded("E AÍ, POPULAÇÃO! Sampler de danças")
    assert is_excluded("AI DE MIM QUE SOU ROMANTICA")


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


def test_relevance_and_exclusions():
    from scraper.core import is_excluded, relevant_themes
    assert is_excluded("Passeando de Trem Café da Tarde + Degustação Especial")
    assert is_excluded("Curso de Tráfego Pago + IA")
    assert not is_excluded("Fintech Summit 2027")
    assert relevant_themes("Ideathon Osasco") == ["startups"]
    # só uma palavra solta na descrição não basta
    assert relevant_themes("Encontro de Gestores", "Vamos falar de IA também") == []
    assert "ia" in relevant_themes("Encontro", "Inteligência artificial generativa e machine learning")


def test_event_type():
    from scraper.core import classify_type
    assert classify_type("Congresso Brasileiro de Fintechs") == "congresso"
    assert classify_type("Feira Hospitalar 2027") == "feira"
    assert classify_type("Curso de IA para Negócios") == "curso"
    assert classify_type("Workshop de Pitch") == "workshop"
    assert classify_type("Demo Day Aceleradora X") == "demo_day"
    assert classify_type("Algo sem pista", source="meetup") == "meetup"
    assert classify_type("Algo sem pista") == "evento"
    assert Event(name="Web Summit Rio", url="u", source="t", city="Rio de Janeiro").finalize().type == "summit"


def test_price_and_summary():
    from scraper.sources.common import price_from_offers
    from scraper.sources.enrich import parse_page, summarize
    assert price_from_offers({"price": "0"}) == "Gratuito"
    assert price_from_offers([{"price": 50}, {"price": 1250.5}]) == "R$ 50 a R$ 1.250,50"
    assert price_from_offers({"lowPrice": 0, "highPrice": 90}) == "Gratuito a R$ 90"
    html = ('<script type="application/ld+json">{"@type":"Event","name":"X","description":"<p>Um summit sobre IA.</p>",'
            '"offers":{"@type":"AggregateOffer","lowPrice":"120.00","highPrice":"300.00"}}</script>')
    info = parse_page(html)
    assert info == {"description": "Um summit sobre IA.", "price": "R$ 120 a R$ 300"}
    meta = '<meta property="og:description" content="Evento gratuito sobre fintech.">'
    assert parse_page(meta)["price"] == "Gratuito"
    s = summarize("Primeira frase do evento com bastante conteúdo para passar do mínimo. " * 6)
    assert s.endswith(".") and len(s) <= 240


def test_enrich_sympla_meetup():
    import json as _j
    from scraper.sources.enrich import parse_page
    def nd(obj):
        return f'<script id="__NEXT_DATA__" type="application/json">{_j.dumps(obj)}</script>'
    sym = nd({"props": {"pageProps": {"hydrationData": {"eventHydration": {"event": {
        "paymentEventType": "paid", "strippedDetail": "Curso prático de IA para negócios."}}}}}})
    assert parse_page(sym) == {"description": "Curso prático de IA para negócios.", "price": "Pago (valor no site)"}
    sym2 = nd({"props": {"pageProps": {"hydrationData": {"eventHydration": {"event": {
        "paymentEventType": "paid", "strippedDetail": "Startup com R$ 2 milhões captados. Lote 1: R$ 97,00. Lote 2: R$ 147"}}}}}})
    assert parse_page(sym2)["price"] == "A partir de R$ 97"
    free = nd({"props": {"pageProps": {"hydrationData": {"eventHydration": {"event": {"paymentEventType": "unpaid"}}}}}})
    assert parse_page(free)["price"] == "Gratuito"
    meet = nd({"props": {"pageProps": {"event": {"feeSettings": None}}}})
    assert parse_page(meet)["price"] == "Gratuito"
    meet2 = nd({"props": {"pageProps": {"event": {"feeSettings": {"amount": 30, "currency": "BRL"}}}}})
    assert parse_page(meet2)["price"] == "R$ 30"
    from scraper.sources.common import price_from_offers
    assert price_from_offers([{"price": -1}]) is None


def test_geocode_offline(tmp_path, monkeypatch):
    import scraper.geo as g
    monkeypatch.setattr(g, "CACHE_FILE", tmp_path / "geo.json")
    evs = [{"city": "Campinas", "state": "SP"}, {"city": "Cidade Desconhecida", "state": "PE"},
           {"city": None, "state": None, "format": "online"}]
    g.geocode_events(evs, online=False)
    assert evs[0]["lat"] == -22.906 and evs[0]["geo_precision"] == "cidade"
    assert (evs[1]["lat"], evs[1]["lon"]) == g.CAPITALS["PE"] and evs[1]["geo_precision"] == "estado"
    assert evs[2]["lat"] is None


def test_news_listicle_and_article():
    from datetime import date
    from scraper.core import load_themes
    from scraper.sources.news import event_name_from_title, links_from_feed, parse_article
    ref = date(2026, 11, 27)
    html = """<html><body><article><div class="entry-content">
      <p>Confira os principais eventos de inovação do ano. """ + "Texto. " * 60 + """</p>
      <h2>1. VTEX Day 2027</h2>
      <p>Quando: 10 e 11 de março de 2027. Onde: São Paulo (SP).</p>
      <p>Maior evento de comércio digital e inteligência artificial da América Latina. <a href="https://vtexday.com">Site</a></p>
      <h2>2. Gramado Summit</h2>
      <p>De 5 a 7 de maio de 2027, em Gramado (RS). Evento de inovação e startups com mais de 500 palestras.</p>
      <h2>3. Evento sem data</h2><p>Em Recife, sem data definida.</p>
      <h2>Leia também</h2><p>Outra matéria em 10 de março de 2027 em SP.</p>
    </div></article></body></html>"""
    evs = parse_article(html, "https://startups.com.br/eventos/agenda-2027/", "Agenda 2027: 30 eventos de inovação",
                        load_themes(), ["startups"], ref)
    names = {e.name: e for e in evs}
    assert set(names) == {"VTEX Day 2027", "Gramado Summit"}
    assert names["VTEX Day 2027"].url == "https://vtexday.com" and names["VTEX Day 2027"].state == "SP"
    assert names["Gramado Summit"].start_date == "2027-05-05" and names["Gramado Summit"].state == "RS"
    assert event_name_from_title("ACE Summit aposta em conexões para destravar negócios em 2027") == "ACE Summit"
    assert event_name_from_title("Congresso Brasileiro de Fintechs abre inscrições") == "Congresso Brasileiro de Fintechs"
    art = """<html><head><meta property="og:description" content="Evento reúne startups e investidores."></head>
      <body><article>""" + "Contexto. " * 40 + """O ACE Summit acontece em 18 de março de 2027, em São Paulo (SP).</article></body></html>"""
    one = parse_article(art, "https://startups.com.br/x", "ACE Summit aposta em conexões para destravar negócios em 2027",
                        load_themes(), ["startups"], ref)
    assert len(one) == 1 and one[0].name == "ACE Summit" and one[0].start_date == "2027-03-18"
    rss = "<rss><channel><item><title>Web Summit Rio 2027 confirma datas</title><link>https://x.com/a</link></item></channel></rss>"
    assert links_from_feed(rss) == [("https://x.com/a", "Web Summit Rio 2027 confirma datas")]


def test_news_quality_rules():
    from datetime import date
    from scraper.core import load_themes
    from scraper.sources.news import event_name_from_title, parse_article
    assert event_name_from_title("Web Summit Fundador da empresa fala sobre IA") == "Web Summit"
    assert event_name_from_title("Startup Summit 2025: Além do óbvio") == "Startup Summit 2025"
    html = """<article><div class="entry-content">""" + "<p>" + "Intro. " * 80 + """</p>
      <h2>Março</h2><p>Dia 10 de março, em São Paulo (SP), acontece o evento X de startups.</p>
      <h2>Startup Day 2026 (SP)</h2><p>Dia 22 de março, em São Paulo (SP). Evento de startups do Sebrae.</p>
      <h3>VTEX Day</h3><p>Dia 10 de março de 2027, em São Paulo (SP). Inteligência artificial e varejo.</p>
      <h3>Outro</h3><p>Dia 5 de abril, em São Paulo (SP). Encontro de startups <a href="https://www.google.com/preferences?x">x</a></p>
    </div></article>"""
    evs = parse_article(html, "https://startups.com.br/agenda-2026/", "Agenda 2026: eventos de inovação", load_themes(), ["startups"])
    names = [e.name for e in evs]
    assert "Março" not in names and not any("Startup Day" in n for n in names)  # mês e edição passada saem
    assert "VTEX Day" in names
    assert all("google." not in e.url for e in evs)
