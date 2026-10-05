"""Control de calidad de todos los artículos: python bot/check_posts.py

Valida el esquema, longitud, título/meta SEO, enlaces internos rotos y enlaces internos ausentes.
Sale con código 1 si hay errores (no avisos).
"""
import re
import sys

from pydantic import ValidationError

from common import CONFIG, load_posts
from generate import Article

FIELDS = set(Article.model_fields)


def main() -> int:
    posts = load_posts(include_drafts=True)
    slugs = {p["slug"] for p in posts}
    errors = warnings = 0
    for p in posts:
        msgs = []
        try:
            Article.model_validate({k: v for k, v in p.items() if k in FIELDS})
        except ValidationError as err:
            msgs.append(f"ERROR esquema: {err.errors()[0]['loc']} {err.errors()[0]['msg']}")
        if p.get("words", 0) < CONFIG["generation"]["min_words"] * 0.8:
            msgs.append(f"ERROR corto: {p.get('words')} palabras")
        if len(p.get("seo_title", "")) > 65:
            msgs.append(f"aviso seo_title largo ({len(p['seo_title'])} car.)")
        if not 120 <= len(p.get("meta_description", "")) <= 160:
            msgs.append(f"aviso meta_description de {len(p.get('meta_description', ''))} car.")
        body = p.get("intro_markdown", "") + " ".join(s["body_markdown"] for s in p.get("sections", []))
        links = re.findall(r"\]\(/([a-z0-9-]+)/?\)", body)
        for slug in links:
            if slug not in slugs:
                msgs.append(f"ERROR enlace interno roto: /{slug}/")
        if not links and len(slugs) > 3:
            msgs.append("aviso sin enlaces internos")
        if msgs:
            print(f"\n/{p['slug']}/")
            for m in msgs:
                print(f"  - {m}")
                errors += m.startswith("ERROR")
                warnings += not m.startswith("ERROR")
    print(f"\n{len(posts)} artículos · {errors} errores · {warnings} avisos")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
