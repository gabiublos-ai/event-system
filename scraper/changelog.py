"""Gera docs/data/changelog.json para a aba Admin do site.

- Melhorias: commits do repositório feitos por pessoas (não pelo robô), com título e detalhes.
- Atualizações automáticas: data/update_history.json (registrado a cada execução do robô)
  + commits antigos do robô ("Atualiza eventos ...") anteriores ao histórico.
Uso: python -m scraper.changelog
"""
from __future__ import annotations

import json
import re
import subprocess
from datetime import datetime, timezone

from scraper.core import DATA_DIR, SITE_DATA_DIR

BOT = "radar-bot"
SEP, END = "\x1f", "\x1e"
SKIP_LINE = re.compile(r"^(co-authored-by|claude-session|signed-off-by):", re.I)


def git_log() -> list[dict]:
    try:
        out = subprocess.run(
            ["git", "log", f"--format=%H{SEP}%an{SEP}%aI{SEP}%s{SEP}%b{END}"],
            capture_output=True, text=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError):
        return []
    commits = []
    for raw in out.split(END):
        parts = raw.strip("\n").split(SEP)
        if len(parts) < 5:
            continue
        sha, author, date, subject, body = parts
        details = []
        for line in body.splitlines():
            line = line.rstrip()
            if not line.strip() or SKIP_LINE.match(line.strip()):
                continue
            bullet = re.match(r"^\s*[-*•]\s+", line)
            text = re.sub(r"^\s*[-*•]\s+", "", line).strip()
            if details and not bullet:
                details[-1] += " " + text  # continuação da linha anterior
            else:
                details.append(text)
        commits.append({"sha": sha[:7], "author": author, "at": date, "title": subject, "details": details})
    return commits


def utc(iso: str) -> str:
    try:
        return datetime.fromisoformat(iso).astimezone(timezone.utc).isoformat(timespec="minutes")
    except ValueError:
        return iso


def main() -> None:
    commits = git_log()
    improvements = [
        {"at": utc(c["at"]), "title": c["title"], "details": c["details"], "sha": c["sha"]}
        for c in commits if c["author"] != BOT
    ]
    try:
        hist = json.loads((DATA_DIR / "update_history.json").read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        hist = []
    updates = [{**h, "at": utc(h["at"])} for h in hist]
    first = min((h["at"] for h in updates), default="9999")
    for c in commits:  # execuções antigas do robô, de antes do histórico detalhado
        if c["author"] == BOT and utc(c["at"]) < first:
            updates.append({"at": utc(c["at"]), "trigger": "registro", "mode": "coleta", "title": c["title"]})
    updates.sort(key=lambda u: u["at"], reverse=True)
    SITE_DATA_DIR.mkdir(parents=True, exist_ok=True)
    (SITE_DATA_DIR / "changelog.json").write_text(json.dumps(
        {"improvements": improvements, "updates": updates[:400]}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"changelog: {len(improvements)} melhorias, {len(updates)} atualizações")


if __name__ == "__main__":
    main()
