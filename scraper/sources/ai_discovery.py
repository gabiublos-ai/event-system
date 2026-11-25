"""Descoberta de eventos com Claude + busca na web.

Cobre o que os coletores das plataformas não pegam: sites próprios de grandes
eventos, agendas de hubs/aceleradoras, eventos regionais, anúncios em portais.
Só roda se a variável ANTHROPIC_API_KEY estiver definida (secret no GitHub).
"""
from __future__ import annotations

import json
import logging
import os
from datetime import date

from scraper.core import UFS, Event

log = logging.getLogger("scraper")

MODEL = os.environ.get("CLAUDE_MODEL", "claude-opus-5-5")

EVENT_SCHEMA = {
    "type": "object",
    "properties": {
        "events": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "description": {"type": "string"},
                    "start_date": {"type": ["string", "null"], "description": "YYYY-MM-DD"},
                    "end_date": {"type": ["string", "null"], "description": "YYYY-MM-DD"},
                    "city": {"type": ["string", "null"]},
                    "state": {"type": ["string", "null"], "description": "UF com 2 letras"},
                    "venue": {"type": ["string", "null"]},
                    "format": {"type": "string", "enum": ["presencial", "hibrido", "online"]},
                    "type": {"type": "string", "enum": ["conferencia", "feira", "congresso", "summit", "meetup",
                                                         "demo_day", "festival", "hackathon", "workshop"]},
                    "recurrence": {"type": "string", "enum": ["anual", "semestral", "trimestral", "mensal", "ocasional"]},
                    "organizer": {"type": ["string", "null"]},
                    "url": {"type": "string"},
                    "themes": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["name", "description", "start_date", "end_date", "city", "state", "venue", "format",
                             "type", "recurrence", "organizer", "url", "themes"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["events"],
    "additionalProperties": False,
}

# Fatias de busca: tema x região, para que cada chamada foque em algo específico.
REGION_HINTS = {
    "Sudeste": "São Paulo, Rio de Janeiro, Belo Horizonte, Campinas, Vitória",
    "Sul": "Porto Alegre, Florianópolis, Curitiba, Gramado, Joinville",
    "Nordeste": "Recife, Fortaleza, Salvador, Natal, João Pessoa, Maceió, São Luís",
    "Norte e Centro-Oeste": "Manaus, Belém, Brasília, Goiânia, Cuiabá, Campo Grande, Palmas",
}


def _prompt(theme_label: str, theme_terms: list[str], region: str, cities: str, theme_keys: list[str]) -> str:
    return f"""Hoje é {date.today().isoformat()}. Você é um pesquisador que mapeia eventos no Brasil.

Pesquise na web eventos, feiras, congressos, summits, meetups, demo days e hackathons sobre
**{theme_label}** (termos relacionados: {', '.join(theme_terms)}) que acontecem na região {region}
do Brasil (ex.: {cities}) nos próximos 12 meses, incluindo eventos recorrentes (anuais, mensais)
e ocasionais. Procure em sites oficiais, Sympla, Eventbrite, Meetup, Even3, Doity, agendas de
hubs de inovação, aceleradoras, associações e portais de notícias.

Regras:
- Inclua apenas eventos reais que você encontrou em uma fonte; nunca invente.
- `url` deve ser a página oficial ou de inscrição do evento.
- Datas no formato YYYY-MM-DD. Se a data da próxima edição não foi anunciada, use null.
- `state` é a UF de 2 letras. Eventos 100% online: format "online" e state null.
- `themes`: escolha entre {theme_keys}.
- Descrição curta em português (1–2 frases).
- Traga o máximo de eventos distintos que conseguir (idealmente 15 ou mais)."""


def discover(themes_cfg: dict, max_calls: int | None = None) -> list[Event]:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        log.info("ANTHROPIC_API_KEY não definida — pulando descoberta com IA.")
        return []
    try:
        import anthropic
    except ImportError:
        log.warning("pacote anthropic não instalado — pulando descoberta com IA.")
        return []

    client = anthropic.Anthropic()
    max_calls = max_calls or int(os.environ.get("AI_MAX_CALLS", "10"))
    keys = list(themes_cfg.keys())
    jobs = [(k, r) for k in keys for r in REGION_HINTS]
    # rotação diária: cada dia começa por uma fatia diferente, cobrindo tudo ao longo da semana
    offset = date.today().toordinal() % len(jobs)
    jobs = (jobs[offset:] + jobs[:offset])[:max_calls]

    events: list[Event] = []
    for theme_key, region in jobs:
        cfg = themes_cfg[theme_key]
        prompt = _prompt(cfg["label"], cfg["search_terms"], region, REGION_HINTS[region], keys)
        try:
            found = _run(client, anthropic, prompt)
        except Exception as e:  # noqa: BLE001 - uma fatia com erro não derruba as outras
            log.warning("IA %s/%s falhou: %s", theme_key, region, e)
            continue
        for d in found:
            st = (d.get("state") or "").upper() or None
            events.append(Event(
                name=d["name"], url=d["url"], source="ia_web",
                start_date=d.get("start_date"), end_date=d.get("end_date"),
                description=d.get("description") or "", city=d.get("city"),
                state=st if st in UFS else None, venue=d.get("venue"),
                format=d.get("format") or "presencial", type=d.get("type"),
                organizer=d.get("organizer"), recurrence=d.get("recurrence") or "ocasional",
                themes=[t for t in d.get("themes", []) if t in themes_cfg] or [theme_key],
                date_confirmed=bool(d.get("start_date")),
            ))
        log.info("IA %s/%s: %d eventos", theme_key, region, len(found))
    return events


def _run(client, anthropic, prompt: str) -> list[dict]:
    messages = [{"role": "user", "content": prompt}]
    for _ in range(5):  # retoma turnos pausados pela busca (pause_turn)
        with client.beta.messages.stream(
            model=MODEL,
            max_tokens=32000,
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            output_config={"effort": "medium", "format": {"type": "json_schema", "schema": EVENT_SCHEMA}},
            tools=[{"type": "web_search_20260209", "name": "web_search", "max_uses": 8,
                    "user_location": {"type": "approximate", "country": "BR"}}],
            messages=messages,
        ) as stream:
            resp = stream.get_final_message()
        if resp.stop_reason == "pause_turn":
            messages = [messages[0], {"role": "assistant", "content": resp.content}]
            continue
        if resp.stop_reason == "refusal":
            return []
        text = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text").strip()
        if not text:
            return []
        try:
            return json.loads(text).get("events", [])
        except json.JSONDecodeError:
            start, end = text.find("{"), text.rfind("}")
            if start >= 0 and end > start:
                return json.loads(text[start:end + 1]).get("events", [])
            return []
    return []
