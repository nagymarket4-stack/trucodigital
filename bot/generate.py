"""Genera N artículos al día con Claude a partir de la cola de palabras clave.

Cada artículo incluye además el guion de un YouTube Short / TikTok.
Si la cola baja del mínimo, Claude propone nuevas keywords long-tail.
"""
import datetime as dt
import os
import sys

import anthropic
from pydantic import BaseModel

from common import (CONFIG, KEYWORDS_FILE, USED_KEYWORDS_FILE, load_posts,
                    read_lines, save_post, slugify, write_lines)

client: anthropic.Anthropic | None = None  # se crea en main() solo si hay clave
GEN = CONFIG["generation"]
SITE = CONFIG["site"]
CATEGORIES = CONFIG["categories"]


class Section(BaseModel):
    heading: str
    body_markdown: str


class FAQ(BaseModel):
    question: str
    answer: str


class ShortLine(BaseModel):
    text: str
    emoji: str
    ui_path: list[str]
    broll_query: str


class ShortScript(BaseModel):
    title: str
    hook: str
    hook_emoji: str
    hook_broll_query: str
    lines: list[ShortLine]
    cta: str
    cta_emoji: str
    hashtags: list[str]


class Product(BaseModel):
    name: str
    reason: str
    search_query: str


class Article(BaseModel):
    title: str
    seo_title: str
    meta_description: str
    category: str
    intro_markdown: str
    key_takeaways: list[str]
    sections: list[Section]
    faq: list[FAQ]
    tags: list[str]
    products: list[Product]
    short: ShortScript


class KeywordIdeas(BaseModel):
    keywords: list[str]


SYSTEM = f"""Eres el redactor jefe de {SITE['name']} ({SITE['tagline']}).
Temática: {CONFIG['niche']}.
Público: {CONFIG['audience']}.

Escribes en español neutro-de-España, claro, cercano y útil. Tu objetivo es que el lector resuelva
su problema de verdad: pasos numerados concretos, nombres reales de menús y ajustes, diferencias
entre Android e iPhone cuando aplique, advertencias y errores comunes.

Reglas de calidad (obligatorias; el sitio se monetiza con Google AdSense y debe cumplir sus políticas
y las de contenido útil de Google):
- Nada de relleno, frases vacías ni repetir la keyword artificialmente.
- No inventes estadísticas, estudios, precios exactos ni citas. Si algo depende de la versión o del
  modelo, dilo.
- No prometas cosas ilegales ni enseñes a espiar a terceros, piratear o saltarse seguridad ajena.
- Formato markdown: listas, pasos numerados, **negritas** para lo clave, tablas cuando ayuden.
- No uses encabezados H1 dentro del markdown; los H2 los pongo yo con `heading`. Puedes usar ### dentro.
- Enlaza internamente (formato markdown [texto](/slug/)) a 1-3 artículos relacionados de la lista
  que te dé, solo si son realmente relevantes. Nunca inventes URLs internas.

GUION DEL SHORT (YouTube Shorts / TikTok, vertical, 25-45 s narrado por voz sintética):
- hook: máx. 10 palabras. Debe parar el scroll en el primer segundo: una pregunta que duela, un error
  común o una promesa concreta ("¿Móvil lleno? El culpable no son tus fotos."). Nada de "Hola" ni "Hoy te enseño".
- lines: 4-7 pasos, cada text de máx. 12 palabras, en imperativo, concretos y en orden. Ritmo rápido.
  Sin emojis ni símbolos dentro de text (se leen en voz alta). Escribe los números con cifras.
- emoji: un único emoji que represente visualmente el paso (⚙️ ajustes, 💬 WhatsApp, 🔋 batería, 🔒 seguridad...).
- ui_path: si el paso consiste en navegar menús, la ruta tal y como aparece en pantalla, 2-4 elementos cortos
  (["Ajustes", "Batería", "Ahorro de energía"]). Si no es navegación, lista vacía. Úsalo en al menos 2 pasos.
- broll_query: 2-4 palabras EN INGLÉS para buscar vídeo de stock que ilustre el paso ("woman using smartphone").
- cta: invita a la guía completa del enlace del perfil y a seguir la cuenta, máx. 14 palabras.
- title: máx. 70 caracteres + 1 emoji al final, curiosidad sin mentir.

PRODUCTOS (products): 0-3 productos físicos que de verdad ayuden a resolver el problema del artículo
(cargador, power bank, tarjeta microSD, router wifi mesh, funda...). name genérico sin marca inventada,
reason en 1 frase útil y search_query de 2-5 palabras para buscar en Amazon España. Si no encaja ninguno, lista vacía."""


def generate_article(keyword: str, existing: list[dict]) -> Article | None:
    related = "\n".join(f"- /{p['slug']}/ — {p['title']}" for p in existing[:150]) or "(aún no hay)"
    prompt = f"""Escribe el artículo definitivo para la búsqueda: "{keyword}"

Longitud del cuerpo: mínimo {GEN['min_words']} palabras, entre 5 y 8 secciones.
Categoría: elige exactamente una de estas claves: {', '.join(CATEGORIES)}.
seo_title: máx. 60 caracteres, con la keyword al principio.
meta_description: 140-155 caracteres, con beneficio claro.
key_takeaways: 3-5 puntos de resumen.
faq: 3-5 preguntas reales que la gente busca sobre el tema.
tags: 3-6 etiquetas cortas en minúscula.
short.hashtags: 3-5 hashtags sin '#', en minúscula.

Artículos ya publicados para enlazado interno:
{related}"""
    with client.messages.stream(
        model=GEN["model"],
        max_tokens=32000,
        thinking={"type": "adaptive"},
        output_config={"effort": "medium"},
        output_format=Article,
        system=SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    ) as stream:
        msg = stream.get_final_message()
    if msg.stop_reason != "end_turn" or msg.parsed_output is None:
        print(f"  ! stop_reason={msg.stop_reason}, se descarta")
        return None
    return msg.parsed_output


def word_count(article: Article) -> int:
    body = article.intro_markdown + " ".join(s.body_markdown for s in article.sections)
    return len(body.split())


def refill_keywords(queue: list[str], used: list[str], existing: list[dict]) -> list[str]:
    known = "\n".join(queue + used)
    msg = client.messages.parse(
        model=GEN["model"],
        max_tokens=16000,
        output_config={"effort": "medium"},
        output_format=KeywordIdeas,
        system=SYSTEM,
        messages=[{"role": "user", "content": f"""Propón 40 búsquedas long-tail nuevas (3-9 palabras) que
personas reales escriben en Google sobre la temática, con intención informativa y buena probabilidad
de posicionar para un sitio nuevo (evita términos ultra competidos y de una sola palabra). Prioriza
problemas concretos y 'cómo hacer X'. Varía categorías: {', '.join(CATEGORIES.values())}.
No repitas ni parafrasees ninguna de estas:
{known}"""}],
    )
    if msg.parsed_output is None:
        print("! No se pudieron generar keywords nuevas")
        return queue
    ideas = msg.parsed_output.keywords
    seen = {k.lower() for k in queue + used}
    fresh = [k.strip() for k in ideas if k.strip() and k.strip().lower() not in seen]
    print(f"Cola recargada con {len(fresh)} keywords nuevas")
    return queue + fresh


def main() -> int:
    global client
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("Sin ANTHROPIC_API_KEY: se omite la generación (el cerebro local puede subir artículos por git)")
        return 0
    client = anthropic.Anthropic()
    n = int(sys.argv[1]) if len(sys.argv) > 1 else GEN["articles_per_day"]
    queue = read_lines(KEYWORDS_FILE)
    used = read_lines(USED_KEYWORDS_FILE)
    existing = load_posts(include_drafts=True)
    existing_slugs = {p["slug"] for p in existing}

    if len(queue) < GEN["keyword_queue_min"] + n:
        queue = refill_keywords(queue, used, existing)

    created = 0
    attempts = 0
    while created < n and queue and attempts < n * 2:
        attempts += 1
        keyword = queue.pop(0)
        used.append(keyword)
        print(f"[{created + 1}/{n}] {keyword}")
        try:
            art = generate_article(keyword, existing)
        except (anthropic.APIStatusError, anthropic.APIConnectionError, ValueError) as e:
            print(f"  ! error: {e}")
            continue
        if art is None:
            continue
        words = word_count(art)
        if words < GEN["min_words"] * 0.8:
            print(f"  ! demasiado corto ({words} palabras), se descarta")
            continue
        slug = slugify(art.title)
        if slug in existing_slugs:
            slug = f"{slug}-{dt.date.today():%Y%m%d}"
        category = art.category if art.category in CATEGORIES else next(iter(CATEGORIES))
        now = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
        post = {
            "slug": slug,
            "keyword": keyword,
            "date": now,
            "updated": now,
            "draft": GEN["require_review"],
            "words": words,
            **art.model_dump(),
            "category": category,
            "video": {"file": None, "youtube_id": None, "tiktok_publish_id": None},
        }
        save_post(post)
        existing.insert(0, post)
        existing_slugs.add(slug)
        created += 1
        print(f"  ok -> /{slug}/ ({words} palabras)")

    write_lines(KEYWORDS_FILE, queue)
    write_lines(USED_KEYWORDS_FILE, used)
    print(f"Artículos creados: {created}")
    return 0 if created else 1


if __name__ == "__main__":
    sys.exit(main())
