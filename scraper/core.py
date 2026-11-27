"""Modelos, normalização, classificação por tema e deduplicação de eventos."""
from __future__ import annotations

import hashlib
import html
import json
import re
import unicodedata
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timezone
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = ROOT / "config"
DATA_DIR = ROOT / "data"
SITE_DATA_DIR = ROOT / "docs" / "data"

UFS = {
    "AC": "Acre", "AL": "Alagoas", "AP": "Amapá", "AM": "Amazonas", "BA": "Bahia",
    "CE": "Ceará", "DF": "Distrito Federal", "ES": "Espírito Santo", "GO": "Goiás",
    "MA": "Maranhão", "MT": "Mato Grosso", "MS": "Mato Grosso do Sul", "MG": "Minas Gerais",
    "PA": "Pará", "PB": "Paraíba", "PR": "Paraná", "PE": "Pernambuco", "PI": "Piauí",
    "RJ": "Rio de Janeiro", "RN": "Rio Grande do Norte", "RS": "Rio Grande do Sul",
    "RO": "Rondônia", "RR": "Roraima", "SC": "Santa Catarina", "SP": "São Paulo",
    "SE": "Sergipe", "TO": "Tocantins",
}
REGIONS = {
    "Norte": ["AC", "AP", "AM", "PA", "RO", "RR", "TO"],
    "Nordeste": ["AL", "BA", "CE", "MA", "PB", "PE", "PI", "RN", "SE"],
    "Centro-Oeste": ["DF", "GO", "MT", "MS"],
    "Sudeste": ["ES", "MG", "RJ", "SP"],
    "Sul": ["PR", "RS", "SC"],
}
UF_TO_REGION = {uf: r for r, ufs in REGIONS.items() for uf in ufs}

# Capitais e polos de inovação -> UF (ajuda quando a fonte só informa a cidade)
CITY_TO_UF = {
    "sao paulo": "SP", "campinas": "SP", "sao jose dos campos": "SP", "ribeirao preto": "SP",
    "sorocaba": "SP", "santos": "SP", "sao carlos": "SP", "barueri": "SP", "santo andre": "SP",
    "rio de janeiro": "RJ", "niteroi": "RJ", "petropolis": "RJ",
    "belo horizonte": "MG", "uberlandia": "MG", "juiz de fora": "MG", "santa rita do sapucai": "MG",
    "vitoria": "ES", "vila velha": "ES",
    "curitiba": "PR", "londrina": "PR", "maringa": "PR", "foz do iguacu": "PR",
    "florianopolis": "SC", "joinville": "SC", "blumenau": "SC", "balneario camboriu": "SC", "chapeco": "SC",
    "porto alegre": "RS", "caxias do sul": "RS", "gramado": "RS", "pelotas": "RS", "sao leopoldo": "RS",
    "brasilia": "DF", "goiania": "GO", "cuiaba": "MT", "campo grande": "MS",
    "salvador": "BA", "recife": "PE", "fortaleza": "CE", "natal": "RN", "joao pessoa": "PB",
    "maceio": "AL", "aracaju": "SE", "teresina": "PI", "sao luis": "MA", "campina grande": "PB",
    "manaus": "AM", "belem": "PA", "palmas": "TO", "porto velho": "RO", "macapa": "AP",
    "boa vista": "RR", "rio branco": "AC",
}

ONLINE_WORDS = ("online", "on-line", "virtual", "remoto", "webinar", "live ", "ao vivo pela internet")


def strip_accents(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn")


def norm(text: str | None) -> str:
    """minúsculas, sem acento, só letras/números, com espaços nas bordas (p/ casar ' ia ')."""
    t = strip_accents((text or "").lower())
    t = re.sub(r"[^a-z0-9.+\-]+", " ", t)
    return f" {t.strip()} "


@lru_cache(maxsize=None)
def _config(name: str) -> dict:
    return json.loads((CONFIG_DIR / name).read_text(encoding="utf-8"))


def load_themes() -> dict:
    return _config("themes.json")["themes"]


def load_types() -> dict:
    return _config("event_types.json")["types"]


def exclude_keywords() -> list[str]:
    return _config("themes.json").get("exclude_keywords", [])


def _match(kw: str, normalized_text: str, original: str = "") -> bool:
    if kw.startswith("re:"):  # regex sobre o texto original (diferencia maiúsculas/acentos)
        return bool(original) and re.search(kw[3:], original) is not None
    core = norm(kw).strip()
    if not core:
        return False
    # espaço explícito no início/fim da palavra-chave = exige palavra inteira
    whole = len(core) <= 4  # palavras curtas (pix, nft, fgv...) só casam como palavra inteira
    k = (" " if kw.startswith(" ") or whole else "") + core + (" " if kw.endswith(" ") or whole else "")
    return k in normalized_text


def keyword_hits(text: str, themes: dict | None = None) -> dict[str, set[str]]:
    """{tema: {palavras-chave encontradas}}"""
    themes = themes or load_themes()
    t = norm(text)
    out: dict[str, set[str]] = {}
    for key, cfg in themes.items():
        found = {norm(kw).strip() if not kw.startswith("re:") else kw for kw in cfg["keywords"] if _match(kw, t, text or "")}
        if found:
            out[key] = found
    return out


def classify(text: str, themes: dict | None = None) -> list[str]:
    return list(keyword_hits(text, themes))


def relevant_themes(name: str, description: str = "", themes: dict | None = None) -> list[str]:
    """Temas de um evento coletado automaticamente.

    - Palavra-chave no NOME do evento: aceito (a descrição pode somar outros temas).
    - Só na descrição: precisa de pelo menos 2 palavras-chave diferentes (evita
      eventos que só citam "IA" de passagem).
    O organizador NÃO entra, para não contaminar todos os eventos de uma mesma conta.
    """
    in_name = keyword_hits(name, themes)
    in_desc = keyword_hits(description, themes)
    if in_name:  # a descrição só acrescenta temas citados com pelo menos 2 palavras-chave diferentes
        return sorted(set(in_name) | {t for t, kws in in_desc.items() if len(kws) >= 2})
    distinct = set().union(*in_desc.values()) if in_desc else set()
    return sorted(in_desc) if len(distinct) >= 2 else []


def is_excluded(name: str) -> bool:
    t = norm(name)
    return any(_match(kw, t) for kw in exclude_keywords())


def classify_type(name: str, description: str = "", source: str = "") -> str:
    types = load_types()
    t = norm(name)
    for key, cfg in types.items():
        if any(_match(kw, t) for kw in cfg["keywords"]):
            return key
    if source == "meetup":
        return "meetup"
    return "evento"


def guess_uf(*parts: str | None) -> str | None:
    for p in parts:
        if not p:
            continue
        raw = p.strip()
        if raw.upper() in UFS:
            return raw.upper()
        n = norm(raw)
        m = re.search(r"[\s\-/,(]([a-z]{2})\s*\)?\s*$", n.rstrip() + " ")
        if m and m.group(1).upper() in UFS and len(n.strip()) > 2:
            return m.group(1).upper()
        for city, uf in CITY_TO_UF.items():
            if f" {city} " in n:
                return uf
        for uf, name in UFS.items():  # nome do estado por extenso ("para" é ambíguo)
            if uf != "PA" and f" {norm(name).strip()} " in n:
                return uf
    return None


def parse_date(value) -> str | None:
    if not value:
        return None
    if isinstance(value, (int, float)):  # epoch (s ou ms)
        v = value / 1000 if value > 1e11 else value
        return datetime.fromtimestamp(v, tz=timezone.utc).date().isoformat()
    s = str(value).strip()
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", s)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    m = re.match(r"(\d{1,2})/(\d{1,2})/(\d{4})", s)
    if m:
        return f"{m.group(3)}-{int(m.group(2)):02d}-{int(m.group(1)):02d}"
    return None


def slug(text: str) -> str:
    return re.sub(r"\s+", "-", norm(text).strip())[:80]


@dataclass
class Event:
    name: str
    url: str
    source: str
    start_date: str | None = None
    end_date: str | None = None
    description: str = ""
    city: str | None = None
    state: str | None = None
    venue: str | None = None
    format: str = "presencial"  # presencial | hibrido | online
    type: str | None = None
    organizer: str | None = None
    image: str | None = None
    price: str | None = None
    themes: list[str] = field(default_factory=list)
    recurrence: str = "ocasional"
    typical_month: int | None = None
    date_confirmed: bool = True
    id: str = ""
    region: str | None = None
    first_seen: str | None = None
    last_seen: str | None = None
    sources: list[str] = field(default_factory=list)

    def finalize(self, themes_cfg: dict | None = None) -> "Event":
        self.name = re.sub(r"\s+", " ", html.unescape(self.name or "").strip())
        self.description = re.sub(r"\s+", " ", html.unescape(self.description or "").strip())[:600]
        self.start_date = parse_date(self.start_date)
        self.end_date = parse_date(self.end_date) or self.start_date
        # plataformas às vezes mandam o fim das vendas como "fim do evento" (meses depois);
        # evento coletado com mais de 31 dias de duração vira evento de um dia só
        if self.source != "curadoria" and self.start_date and self.end_date and (
                date.fromisoformat(self.end_date) - date.fromisoformat(self.start_date)).days > 31:
            self.end_date = self.start_date
        if self.end_date and self.start_date and self.end_date < self.start_date:
            self.end_date = self.start_date
        if not self.state:
            self.state = guess_uf(self.city, self.venue)
        if self.state:
            self.state = self.state.upper()
            self.region = UF_TO_REGION.get(self.state)
        if self.source == "curadoria":  # temas definidos à mão + o que o nome indicar
            self.themes = sorted(set(self.themes) | set(classify(self.name, themes_cfg)))
        else:
            self.themes = sorted(set(self.themes) | set(relevant_themes(self.name, self.description, themes_cfg)))
        if self.type not in load_types():
            self.type = classify_type(self.name, self.description, self.source)
        if self.format == "presencial" and any(w in norm(f"{self.name} {self.venue or ''}") for w in ONLINE_WORDS):
            self.format = "online"
        if self.format == "online":  # evento online não pertence a um estado (não aparece no filtro de UF nem no mapa)
            self.city = self.state = self.region = self.venue = None
        if not self.typical_month and self.start_date:
            self.typical_month = int(self.start_date[5:7])
        if self.source not in self.sources:
            self.sources.append(self.source)
        self.id = self.make_id()
        return self

    def make_id(self) -> str:
        key = f"{dedupe_key(self.name)}|{(self.start_date or '')[:7]}"
        return hashlib.sha1(key.encode()).hexdigest()[:12]

    def to_dict(self) -> dict:
        return asdict(self)


STOP_NAME = re.compile(r"\b(20\d{2}|edicao|edição|\d+a|\d+º|\d+ª|ed)\b")


def dedupe_key(name: str) -> str:
    n = norm(name)
    n = STOP_NAME.sub(" ", n)
    return re.sub(r"\s+", " ", n).strip()


def is_brazil(event: Event) -> bool:
    if event.state in UFS:
        return True
    if event.format == "online":
        return True  # online em plataformas BR (filtradas na origem)
    return False


def merge(old: dict, new: dict) -> dict:
    """Junta duas versões do mesmo evento preferindo campos preenchidos e datas confirmadas."""
    out = dict(old)
    for k, v in new.items():
        if k in ("first_seen",):
            continue
        if k == "sources":
            out["sources"] = sorted(set(old.get("sources", [])) | set(v or []))
        elif k == "themes":
            out["themes"] = sorted(set(old.get("themes", [])) | set(v or []))
        elif k == "description":
            if len(v or "") > len(old.get("description") or ""):
                out[k] = v
        elif k in ("start_date", "end_date"):
            if v and (not old.get(k) or new.get("date_confirmed")):
                out[k] = v
        elif v not in (None, "", []):
            if old.get(k) in (None, "", []) or k in ("last_seen", "date_confirmed"):
                out[k] = v
    return out


def today() -> date:
    return date.today()
