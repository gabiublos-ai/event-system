# 📡 Radar de Eventos BR

Sistema que mapeia automaticamente eventos, feiras, congressos, meetups e demo days — recorrentes e ocasionais — em **todo o Brasil**, sobre:

🤖 IA · 🚀 Startups · ⚡ Aceleradoras · 🎓 Escolas de Negócio (G4, Link, StartSe…) · 🎤 Demo Days · 💳 Fintech · 🩺 Health Tech · 🪙 Cripto · ₿ Bitcoin · 🥗 Food Tech

Atualiza sozinho **todos os dias às 9h (horário de Brasília)** e publica um site interativo.

## O que o site faz

- Busca instantânea (atalho `/`), filtros por tema, região/estado, período, formato e recorrência
- 4 visualizações: **Cards**, **Lista** (agrupada por mês), **Calendário** e **Mapa** do Brasil por estado
- Selo **Novo** para eventos que entraram no radar nos últimos 7 dias
- ⭐ Favoritos (ficam salvos no navegador)
- Adicionar ao Google Agenda, baixar `.ics` (um evento ou todos os filtrados) e exportar **CSV** (abre no Excel)
- Filtros ficam na URL — dá para compartilhar um link já filtrado (ex.: `#t=fintech&uf=R:Nordeste`)
- Tema claro/escuro, funciona no celular

## Como funciona a coleta

| Fonte | Como |
|---|---|
| Sympla | API de busca + página de busca (plano B) |
| Eventbrite | Páginas de busca Brasil (JSON-LD) |
| Meetup | Busca por tema em 14 capitais/polos |
| Even3, Doity | Páginas de busca (JSON-LD) |
| Busca na web com IA (Claude) | Pesquisa por tema × região em sites oficiais, hubs, aceleradoras e portais. Gira as combinações a cada dia para cobrir tudo ao longo da semana |
| Curadoria | `data/seed_events.json` — grandes eventos recorrentes, editável à mão |

Depois o robô:
1. classifica cada evento nos 10 temas por palavras‑chave (`config/themes.json`);
2. descobre a UF/região pela cidade;
3. remove duplicados (mesmo nome + mês) juntando as informações das várias fontes;
4. mantém eventos já vistos mesmo que uma fonte falhe num dia; descarta os que terminaram há mais de 30 dias;
5. grava `docs/data/events.json` e publica o site.

> Nenhuma automação garante 100% de cobertura — as plataformas mudam o HTML e alguns eventos só aparecem em redes sociais. Por isso o sistema combina várias fontes, IA e curadoria, e tem o botão **Sugerir evento**.

## Colocando no ar (uma vez só)

1. **Ativar o GitHub Pages:** no repositório, `Settings → Pages → Build and deployment → Source: GitHub Actions`.
2. **(Recomendado) Ativar a busca com IA:** `Settings → Secrets and variables → Actions → New repository secret`, nome `ANTHROPIC_API_KEY`, com uma chave da [Claude Console](https://console.anthropic.com/).
   - Por padrão faz 10 buscas por dia (≈ 4 dias para varrer os 10 temas × 4 regiões). Para mudar, crie a *variable* `AI_MAX_CALLS`. Cada busca custa alguns centavos de dólar; acompanhe o gasto na Console.
3. Fazer merge desta branch na `main`. O workflow `.github/workflows/update-events.yml` roda todo dia às 9h; para rodar na hora: aba **Actions → Atualizar eventos → Run workflow**.

O site fica em `https://<usuario>.github.io/<repositorio>/`.

> O GitHub pode atrasar execuções agendadas em alguns minutos em horários de pico.

## Fácil de mexer

| Quero… | Edite |
|---|---|
| Adicionar/remover palavras‑chave ou um tema novo | `config/themes.json` (cor, emoji, termos de busca e palavras‑chave) |
| Cadastrar um evento à mão | `data/seed_events.json` |
| Esconder um evento que entrou por engano | coloque o nome em `data/blocklist.json` |
| Ligar/desligar fontes, cidades do Meetup, páginas de agenda extras | `config/sources.json` |
| Mudar textos/cores do site | `docs/index.html`, `docs/styles.css` (variáveis no topo) |
| Mudar o horário | linha `cron` em `.github/workflows/update-events.yml` (em UTC: 9h BRT = 12h UTC) |

Tudo pode ser editado pelo próprio site do GitHub (ícone de lápis) — ao salvar, o site é republicado.

Formato de um evento em `data/seed_events.json`:

```json
{
  "name": "Nome do evento",
  "themes": ["startups", "ia"],
  "description": "Resumo em 1–2 frases.",
  "city": "Recife", "state": "PE", "venue": "Local",
  "start_date": "2027-05-10", "end_date": "2027-05-12",
  "recurrence": "anual", "typical_month": 5,
  "format": "presencial", "type": "conferencia",
  "organizer": "Quem organiza", "url": "https://site-oficial",
  "date_confirmed": true
}
```

Temas válidos: `ia, startups, aceleradoras, escolas_negocio, demo_day, fintech, healthtech, cripto, bitcoin, foodtech`. Sem data anunciada? Use `null` em `start_date`/`end_date` e informe `typical_month`.

## Rodando localmente

```bash
pip install -r requirements.txt
```

```bash
python -m scraper.main            # coleta completa (precisa de internet)
```

```bash
python -m scraper.main --offline  # só reprocessa curadoria + dados existentes
```

```bash
python -m http.server -d docs 8000   # abra http://localhost:8000
```

```bash
python -m pytest -q tests
```

## Estrutura

```
config/            temas, palavras-chave e fontes (JSON)
data/              curadoria manual e blocklist
scraper/           robô de coleta (Python)
  sources/         um coletor por plataforma + descoberta com IA
docs/              site estático (HTML/CSS/JS puro, sem build)
  data/events.json base gerada automaticamente
.github/workflows/ agendamento diário + publicação no GitHub Pages
```
