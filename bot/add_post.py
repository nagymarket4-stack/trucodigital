"""Publica artículos escritos por el "cerebro local" (Claude Code programado en tu PC, sin coste de API).

Uso: python bot/add_post.py borrador1.json [borrador2.json ...]
Cada JSON sigue el esquema Article de generate.py más el campo "keyword".
Valida, rellena slug/fechas, guarda en content/posts y marca la keyword como usada.
"""
import datetime as dt
import json
import sys
from pathlib import Path

from pydantic import ValidationError

from common import (CONFIG, KEYWORDS_FILE, USED_KEYWORDS_FILE, load_posts, read_lines, save_post, slugify,
                    write_lines)
from generate import Article


def main() -> int:
    cats = CONFIG["categories"]
    existing = {p["slug"] for p in load_posts(include_drafts=True)}
    queue, used = read_lines(KEYWORDS_FILE), read_lines(USED_KEYWORDS_FILE)
    ok = 0
    for f in sys.argv[1:]:
        raw = json.loads(Path(f).read_text(encoding="utf-8"))
        keyword = raw.pop("keyword", "")
        try:
            art = Article.model_validate(raw)
        except ValidationError as err:
            print(f"✗ {f}: {err}")
            continue
        words = len((art.intro_markdown + " ".join(s.body_markdown for s in art.sections)).split())
        if words < CONFIG["generation"]["min_words"] * 0.8:
            print(f"✗ {f}: solo {words} palabras")
            continue
        slug = slugify(art.title)
        if slug in existing:
            print(f"✗ {f}: ya existe /{slug}/")
            continue
        now = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
        save_post({"slug": slug, "keyword": keyword, "date": now, "updated": now,
                   "draft": CONFIG["generation"]["require_review"], "words": words, **art.model_dump(),
                   "category": art.category if art.category in cats else next(iter(cats)),
                   "video": {"file": None, "youtube_id": None, "tiktok_publish_id": None}})
        existing.add(slug)
        if keyword in queue:
            queue.remove(keyword)
        if keyword and keyword not in used:
            used.append(keyword)
        ok += 1
        print(f"✓ /{slug}/ ({words} palabras)")
    write_lines(KEYWORDS_FILE, queue)
    write_lines(USED_KEYWORDS_FILE, used)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
