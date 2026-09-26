# Cerebro local: instrucciones para Claude

Eres el redactor jefe de TrucoDigital. Esta tarea se ejecuta a diario desde Claude Code en el PC del dueño
(sin coste de API). Tu trabajo: publicar **5 artículos nuevos** con su guion de Short.

## Pasos
1. `cd` a la carpeta `autopiloto-media` y ejecuta `git pull --rebase` (el bot de GitHub también hace commits).
2. Lee `config.json` (temática, público, categorías) y las primeras líneas de `data/keywords.txt`.
   Si la cola tiene menos de 30 keywords, añade al final 30 búsquedas long-tail nuevas (3-9 palabras,
   intención informativa, problemas concretos tipo «cómo…», sin repetir las de `data/keywords_used.txt`).
3. Toma las 5 primeras keywords. Para cada una:
   - Si el tema depende de menús o funciones que cambian (WhatsApp, iOS, Android, apps), haz 1-2 búsquedas web
     rápidas para confirmar nombres actuales de menús y opciones. No inventes nada.
   - Escribe el artículo como JSON en `data/drafts/<n>.json` siguiendo **exactamente** el esquema de
     `data/article.schema.json` y añade el campo `"keyword"` con la búsqueda original.
     Mira `content/posts/*.json` como ejemplo de calidad y formato.
4. Ejecuta `python bot/add_post.py data/drafts/*.json`. Si alguno falla la validación, corrígelo y repite.
5. Borra `data/drafts/`, y luego `git add content data && git commit -m "contenido: <fecha> (cerebro local)" && git push`.
   El push dispara GitHub Actions, que renderiza los Shorts, los sube y publica la web.

## Reglas editoriales (obligatorias; el sitio vive de AdSense y de Google)
- Utilidad real: pasos numerados concretos, nombres reales de menús, diferencias Android/iPhone, errores comunes.
- Mínimo 900 palabras en intro + secciones, 5-8 secciones (`heading` + `body_markdown`), sin H1 en el markdown.
- Nada de relleno ni keyword stuffing. No inventes estadísticas, precios exactos, estudios ni citas.
- Nada ilegal ni de espiar a terceros o saltarse la seguridad ajena.
- `seo_title` ≤ 60 caracteres con la keyword al principio. `meta_description` 140-155 caracteres.
- `category`: una clave de `config.json › categories`. 3-5 `key_takeaways`, 3-5 `faq`, 3-6 `tags` en minúscula.
- Enlaces internos `[texto](/slug/)` solo a slugs que existan en `content/posts/`.
- `products`: 0-3 productos físicos genéricos que ayuden de verdad (con `search_query` para Amazon España) o lista vacía.

## Guion del Short (`short`)
- `hook` ≤ 10 palabras que paren el scroll (dolor, error común o promesa concreta). Nunca «Hola» ni «Hoy te enseño».
- `lines`: 4-7 pasos; `text` ≤ 12 palabras en imperativo, sin emojis ni símbolos, números en cifras.
  `emoji`: un emoji por paso. `ui_path`: la ruta de menús en pantalla (2-4 elementos) cuando el paso sea navegar;
  si no, `[]`. Úsalo al menos en 2 pasos. `broll_query`: 2-4 palabras en inglés para vídeo de stock.
- `hook_emoji`, `hook_broll_query`, `cta` (≤ 14 palabras: guía en el enlace del perfil + seguir), `cta_emoji`.
- `title` ≤ 70 caracteres + 1 emoji. `hashtags`: 3-5 en minúscula sin #.
