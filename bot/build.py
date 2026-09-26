"""Construye la web estática en public/ a partir de content/posts/*.json.

SEO incluido: títulos/metas únicos, canonical, Open Graph, Twitter cards, JSON-LD
(Article, FAQPage, BreadcrumbList, VideoObject, WebSite, Organization), sitemap.xml,
robots.txt, RSS, enlazado interno por categoría y relacionados, ads.txt y páginas legales.
"""
import datetime as dt
import html
import json
import re
import shutil
from email.utils import format_datetime
from urllib.parse import urlparse

import markdown

from common import CONFIG, PUBLIC_DIR, ROOT, load_posts

SITE = CONFIG["site"]
CATS = CONFIG["categories"]
ADS = CONFIG["adsense"]
AN = CONFIG["analytics"]
BASE_URL = SITE["url"].rstrip("/")
BASE_PATH = urlparse(BASE_URL).path.rstrip("/")  # "" con dominio propio, "/repo" en github.io
YEAR = dt.date.today().year
PER_PAGE = 24

e = html.escape


def u(path: str) -> str:
    """Ruta relativa al sitio → ruta servida (respeta subcarpeta de GitHub Pages)."""
    return f"{BASE_PATH}{path}"


def absu(path: str) -> str:
    return f"{BASE_URL}{path}"


def md(text: str) -> str:
    out = markdown.markdown(text, extensions=["tables", "sane_lists"])
    # enlaces internos "/slug/" → respetar base path
    out = re.sub(r'href="/(?!/)', f'href="{BASE_PATH}/', out)
    # enlaces externos: nofollow noopener
    out = re.sub(r'<a href="(https?://[^"]+)"', r'<a href="\1" rel="nofollow noopener" target="_blank"', out)
    return out


def human_date(iso: str) -> str:
    d = dt.datetime.fromisoformat(iso)
    meses = "enero febrero marzo abril mayo junio julio agosto septiembre octubre noviembre diciembre".split()
    return f"{d.day} de {meses[d.month - 1]} de {d.year}"


CSS = """
:root{--bg:#fbfaf7;--fg:#1d1d1f;--muted:#5f6368;--card:#fff;--line:#e7e3da;--accent:#e4572e;--accent-2:#1f6feb;--soft:#fff3ee}
@media (prefers-color-scheme:dark){:root{--bg:#121214;--fg:#ececec;--muted:#a3a3a8;--card:#1b1b1f;--line:#2c2c31;--accent:#ff7a50;--accent-2:#6aa6ff;--soft:#2a1d18}}
*{box-sizing:border-box}html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--bg);color:var(--fg);font:17px/1.7 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
a{color:var(--accent-2)}img{max-width:100%;height:auto}
.wrap{max-width:1100px;margin:0 auto;padding:0 16px}
header.top{border-bottom:1px solid var(--line);background:var(--card);position:sticky;top:0;z-index:5}
header.top .wrap{display:flex;align-items:center;gap:18px;min-height:60px;flex-wrap:wrap}
.logo{font-weight:800;font-size:22px;color:var(--fg);text-decoration:none;letter-spacing:-.5px}.logo b{color:var(--accent)}
nav.cats{display:flex;gap:14px;overflow-x:auto;font-size:14px;scrollbar-width:none}nav.cats a{color:var(--muted);text-decoration:none;white-space:nowrap}
nav.cats a:hover{color:var(--accent)}
.hero{padding:40px 0 16px}.hero h1{font-size:clamp(28px,4vw,42px);line-height:1.15;margin:0 0 8px;letter-spacing:-1px}.hero p{color:var(--muted);margin:0}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:18px;padding:24px 0 40px}
.card{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:20px;display:flex;flex-direction:column;gap:8px;transition:transform .15s}
.card:hover{transform:translateY(-2px)}.card a.t{color:var(--fg);text-decoration:none;font-weight:700;font-size:19px;line-height:1.3}
.card p{margin:0;color:var(--muted);font-size:15px}.pill{display:inline-block;font-size:12px;font-weight:700;text-transform:uppercase;letter-spacing:.6px;color:var(--accent);text-decoration:none}
.meta{font-size:13px;color:var(--muted)}
.layout{display:grid;grid-template-columns:minmax(0,1fr) 300px;gap:40px;padding:28px 0 60px}
@media (max-width:900px){.layout{grid-template-columns:1fr}}
article h1{font-size:clamp(28px,4vw,40px);line-height:1.15;letter-spacing:-1px;margin:8px 0 12px}
article h2{font-size:26px;line-height:1.25;margin:40px 0 10px;letter-spacing:-.4px}article h3{font-size:20px;margin:28px 0 6px}
article table{border-collapse:collapse;width:100%;display:block;overflow-x:auto;font-size:15px}
article th,article td{border:1px solid var(--line);padding:8px 10px;text-align:left}
.tldr{background:var(--soft);border-left:4px solid var(--accent);border-radius:10px;padding:14px 20px;margin:20px 0}
.tldr ul{margin:6px 0 0;padding-left:20px}
.toc{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px 20px;font-size:15px}
.toc ol{margin:6px 0 0;padding-left:20px}
details{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:12px 16px;margin:10px 0}
summary{font-weight:700;cursor:pointer}
.video{position:relative;aspect-ratio:9/16;max-width:340px;margin:24px auto;border-radius:14px;overflow:hidden;background:#000}
.video iframe{position:absolute;inset:0;width:100%;height:100%;border:0}
aside .box{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:18px;margin-bottom:18px;position:sticky;top:80px}
aside ul{padding-left:18px;margin:0}aside li{margin:8px 0;font-size:15px;line-height:1.4}
.ad{margin:28px 0;min-height:90px}
blockquote{margin:16px 0;padding:12px 18px;border-left:4px solid #f0b429;background:var(--card);border-radius:8px}blockquote p{margin:0}
.crumbs{font-size:13px;color:var(--muted)}.crumbs a{color:var(--muted)}
.pager{display:flex;gap:10px;justify-content:center;padding-bottom:40px}.pager a{padding:8px 14px;border:1px solid var(--line);border-radius:8px;text-decoration:none}
footer{border-top:1px solid var(--line);padding:28px 0;font-size:14px;color:var(--muted)}footer a{color:var(--muted);margin-right:14px}
.social{display:flex;gap:10px;margin-top:10px}.social a{background:var(--accent);color:#fff;padding:8px 14px;border-radius:999px;text-decoration:none;font-weight:700;font-size:14px}
"""


def head(title: str, desc: str, path: str, *, og_type="website", jsonld: list | None = None,
         noindex=False, extra="") -> str:
    canonical = absu(path)
    tags = [
        '<meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width,initial-scale=1">',
        f"<title>{e(title)}</title>",
        f'<meta name="description" content="{e(desc)}">',
        f'<link rel="canonical" href="{canonical}">',
        f'<meta name="robots" content="{"noindex,follow" if noindex else "index,follow,max-image-preview:large"}">',
        f'<meta property="og:site_name" content="{e(SITE["name"])}">',
        f'<meta property="og:locale" content="{SITE["locale"]}">',
        f'<meta property="og:type" content="{og_type}">',
        f'<meta property="og:title" content="{e(title)}">',
        f'<meta property="og:description" content="{e(desc)}">',
        f'<meta property="og:url" content="{canonical}">',
        '<meta name="twitter:card" content="summary_large_image">',
        f'<link rel="alternate" type="application/rss+xml" title="{e(SITE["name"])}" href="{u("/feed.xml")}">',
        f'<link rel="icon" href="{u("/favicon.svg")}" type="image/svg+xml">',
        f"<style>{CSS}</style>",
    ]
    if AN.get("google_site_verification"):
        tags.append(f'<meta name="google-site-verification" content="{e(AN["google_site_verification"])}">')
    if ADS.get("client_id"):
        tags.append(f'<meta name="google-adsense-account" content="{ADS["client_id"]}">')
        tags.append(f'<script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client={ADS["client_id"]}" crossorigin="anonymous"></script>')
    if AN.get("ga4_id"):
        g = AN["ga4_id"]
        tags.append(f'<script async src="https://www.googletagmanager.com/gtag/js?id={g}"></script>'
                    f"<script>window.dataLayer=window.dataLayer||[];function gtag(){{dataLayer.push(arguments)}}"
                    f"gtag('js',new Date());gtag('config','{g}');</script>")
    for obj in jsonld or []:
        tags.append(f'<script type="application/ld+json">{json.dumps(obj, ensure_ascii=False)}</script>')
    return "\n".join(tags) + extra


def header_html() -> str:
    links = "".join(f'<a href="{u(f"/categoria/{k}/")}">{e(v)}</a>' for k, v in CATS.items())
    name = SITE["name"]
    logo = f'{e(name[:5])}<b>{e(name[5:])}</b>' if len(name) > 5 else e(name)
    return f'<header class="top"><div class="wrap"><a class="logo" href="{u("/")}">{logo}</a><nav class="cats">{links}</nav></div></header>'


def footer_html() -> str:
    social = ""
    if SITE.get("youtube_channel_url"):
        social += f'<a href="{SITE["youtube_channel_url"]}" rel="noopener" target="_blank">YouTube</a>'
    if SITE.get("tiktok_url"):
        social += f'<a href="{SITE["tiktok_url"]}" rel="noopener" target="_blank">TikTok</a>'
    pages = [("/sobre-nosotros/", "Sobre nosotros"), ("/contacto/", "Contacto"), ("/aviso-legal/", "Aviso legal"),
             ("/privacidad/", "Privacidad"), ("/cookies/", "Cookies")]
    links = "".join(f'<a href="{u(p)}">{t}</a>' for p, t in pages)
    return (f'<footer><div class="wrap"><p>{links}</p>'
            f'{f"<div class=social>{social}</div>" if social else ""}'
            f"<p>© {YEAR} {e(SITE['name'])}. {e(SITE['tagline'])}.</p></div></footer>")


def page(head_html: str, body: str) -> str:
    return (f'<!doctype html><html lang="{SITE["language"]}"><head>{head_html}</head>'
            f"<body>{header_html()}<main>{body}</main>{footer_html()}</body></html>")


def ad_unit() -> str:
    if not (ADS.get("client_id") and ADS.get("in_article_slot")):
        return ""
    return (f'<div class="ad"><ins class="adsbygoogle" style="display:block;text-align:center" data-ad-layout="in-article" '
            f'data-ad-format="fluid" data-ad-client="{ADS["client_id"]}" data-ad-slot="{ADS["in_article_slot"]}"></ins>'
            "<script>(adsbygoogle=window.adsbygoogle||[]).push({});</script></div>")


def write(path: str, content: str) -> None:
    out = PUBLIC_DIR / path.lstrip("/")
    if path.endswith("/"):
        out = out / "index.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(content, encoding="utf-8")


def card(p: dict) -> str:
    return (f'<div class="card"><a class="pill" href="{u(f"/categoria/{p["category"]}/")}">{e(CATS.get(p["category"], p["category"]))}</a>'
            f'<a class="t" href="{u(f"/{p["slug"]}/")}">{e(p["title"])}</a>'
            f'<p>{e(p["meta_description"])}</p><span class="meta">{human_date(p["date"])}</span></div>')


def org_ld() -> dict:
    same = [x for x in (SITE.get("youtube_channel_url"), SITE.get("tiktok_url")) if x]
    return {"@type": "Organization", "name": SITE["name"], "url": BASE_URL + "/", "sameAs": same,
            "logo": absu("/favicon.svg")}


def build_article(p: dict, posts: list[dict]) -> None:
    path = f"/{p['slug']}/"
    cat = CATS.get(p["category"], p["category"])
    ids = [re.sub(r"[^a-z0-9]+", "-", s["heading"].lower()).strip("-") or f"s{i}" for i, s in enumerate(p["sections"])]
    toc = "".join(f'<li><a href="#{i}">{e(s["heading"])}</a></li>' for i, s in zip(ids, p["sections"]))
    body_parts = []
    for n, (sid, s) in enumerate(zip(ids, p["sections"])):
        body_parts.append(f'<h2 id="{sid}">{e(s["heading"])}</h2>{md(s["body_markdown"])}')
        if n in (1, 4):
            body_parts.append(ad_unit())
    vid = p.get("video", {}).get("youtube_id")
    video_html = (f'<div class="video"><iframe loading="lazy" src="https://www.youtube-nocookie.com/embed/{vid}" '
                  f'title="{e(p["short"]["title"])}" allowfullscreen></iframe></div>') if vid else ""
    faq_html = "".join(f"<details><summary>{e(f['question'])}</summary>{md(f['answer'])}</details>" for f in p["faq"])
    takeaways = "".join(f"<li>{e(t)}</li>" for t in p["key_takeaways"])

    related = [x for x in posts if x["slug"] != p["slug"] and x["category"] == p["category"]][:6]
    if len(related) < 6:
        related += [x for x in posts if x["slug"] != p["slug"] and x not in related][: 6 - len(related)]
    rel_html = "".join(f'<li><a href="{u(f"/{x["slug"]}/")}">{e(x["title"])}</a></li>' for x in related)

    ld = [
        {"@context": "https://schema.org", "@type": "Article", "headline": p["title"][:110],
         "description": p["meta_description"], "datePublished": p["date"], "dateModified": p.get("updated", p["date"]),
         "inLanguage": SITE["language"], "mainEntityOfPage": absu(path), "keywords": ", ".join(p["tags"]),
         "author": {"@type": "Organization", "name": SITE["author"], "url": absu("/sobre-nosotros/")},
         "publisher": org_ld()},
        {"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [
            {"@type": "Question", "name": f["question"], "acceptedAnswer": {"@type": "Answer", "text": f["answer"]}}
            for f in p["faq"]]},
        {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Inicio", "item": BASE_URL + "/"},
            {"@type": "ListItem", "position": 2, "name": cat, "item": absu(f"/categoria/{p['category']}/")},
            {"@type": "ListItem", "position": 3, "name": p["title"], "item": absu(path)}]},
    ]
    if vid:
        ld.append({"@context": "https://schema.org", "@type": "VideoObject", "name": p["short"]["title"],
                   "description": p["meta_description"], "uploadDate": p["date"],
                   "thumbnailUrl": f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg",
                   "embedUrl": f"https://www.youtube.com/embed/{vid}"})

    body = f"""<div class="wrap layout"><article>
<div class="crumbs"><a href="{u('/')}">Inicio</a> › <a href="{u(f'/categoria/{p["category"]}/')}">{e(cat)}</a></div>
<h1>{e(p['title'])}</h1>
<div class="meta">Por {e(SITE['author'])} · Actualizado el {human_date(p.get('updated', p['date']))} · {max(1, p.get('words', 900) // 220)} min de lectura</div>
{md(p['intro_markdown'])}
<div class="tldr"><strong>En resumen</strong><ul>{takeaways}</ul></div>
{video_html}
<nav class="toc"><strong>Contenido</strong><ol>{toc}</ol></nav>
{''.join(body_parts)}
<h2 id="preguntas-frecuentes">Preguntas frecuentes</h2>{faq_html}
{ad_unit()}
</article>
<aside>{f'<div class="box"><strong>Te puede interesar</strong><ul>{rel_html}</ul></div>' if rel_html else ""}</aside></div>"""
    write(path, page(head(p["seo_title"], p["meta_description"], path, og_type="article", jsonld=ld,
                          extra=f'<meta property="article:published_time" content="{p["date"]}">'), body))


def build_listing(path: str, title: str, h1: str, desc: str, items: list[dict], jsonld=None) -> None:
    pages = [items[i:i + PER_PAGE] for i in range(0, len(items), PER_PAGE)] or [[]]
    for n, chunk in enumerate(pages, start=1):
        ppath = path if n == 1 else f"{path}pagina/{n}/"
        pager = ""
        if len(pages) > 1:
            prev = (f'<a href="{u(path if n == 2 else f"{path}pagina/{n-1}/")}">← Anteriores</a>') if n > 1 else ""
            nxt = f'<a href="{u(f"{path}pagina/{n+1}/")}">Más artículos →</a>' if n < len(pages) else ""
            pager = f'<div class="pager">{prev}{nxt}</div>'
        body = (f'<div class="wrap"><section class="hero"><h1>{e(h1)}</h1><p>{e(desc)}</p></section>'
                f'<div class="grid">{"".join(card(p) for p in chunk)}</div>{pager}</div>')
        t = title if n == 1 else f"{title} – página {n}"
        write(ppath, page(head(t, desc, ppath, jsonld=jsonld if n == 1 else None), body))


def build_static_pages() -> None:
    s = SITE
    pages = {
        "/sobre-nosotros/": ("Sobre nosotros", f"""<p><strong>{e(s['name'])}</strong> nace con una idea sencilla: que cualquier persona,
sea o no experta, pueda sacar partido a su móvil, su ordenador y las nuevas herramientas de inteligencia artificial.</p>
<p>Publicamos guías paso a paso sobre {e(CONFIG['niche'])}. Cada guía se elabora con ayuda de herramientas de
inteligencia artificial y se revisa siguiendo una línea editorial que prioriza la utilidad, la claridad y la seguridad del lector.
Si detectas un error o algo ha cambiado tras una actualización, escríbenos y lo corregimos.</p>
<p>También puedes seguirnos en nuestros vídeos cortos con trucos diarios.</p>"""),
        "/contacto/": ("Contacto", f"""<p>¿Dudas, sugerencias de temas o correcciones? Escríbenos a
<a href="mailto:{e(s['contact_email'])}">{e(s['contact_email'])}</a>. Respondemos en 48-72 horas laborables.</p>"""),
        "/aviso-legal/": ("Aviso legal", f"""<p>En cumplimiento de la Ley 34/2002 (LSSI-CE) se informa: titular del sitio
<strong>{e(s['owner_legal_name'])}</strong>, NIF {e(s['owner_nif'])}, correo {e(s['contact_email'])}.</p>
<p>Los contenidos son informativos. {e(s['name'])} no se responsabiliza de los daños derivados del uso de la información;
sigue siempre las instrucciones oficiales del fabricante de tu dispositivo. Los enlaces externos pertenecen a sus titulares.</p>
<p>Las marcas mencionadas (WhatsApp, Android, iPhone, Windows, etc.) pertenecen a sus propietarios y se citan solo con fines informativos.</p>"""),
        "/privacidad/": ("Política de privacidad", f"""<p>Responsable: {e(s['owner_legal_name'])} ({e(s['contact_email'])}).</p>
<p>Este sitio no pide registro. Si nos escribes por email, usamos tus datos solo para responderte (base legal: consentimiento).</p>
<p><strong>Publicidad:</strong> usamos Google AdSense. Google y sus socios pueden usar cookies para mostrar anuncios según tus
visitas a este y otros sitios. Puedes desactivar la publicidad personalizada en
<a href="https://adssettings.google.com" rel="nofollow noopener">Configuración de anuncios de Google</a>. Más información en
<a href="https://policies.google.com/technologies/ads" rel="nofollow noopener">cómo usa Google las cookies en publicidad</a>.</p>
<p><strong>Analítica:</strong> podemos usar Google Analytics para medir visitas de forma agregada.</p>
<p>Puedes ejercer tus derechos de acceso, rectificación, supresión, oposición, limitación y portabilidad escribiendo al correo
indicado, y reclamar ante la Agencia Española de Protección de Datos (aepd.es).</p>"""),
        "/cookies/": ("Política de cookies", """<p>Usamos cookies propias técnicas y de terceros (Google AdSense y Google Analytics)
para mostrar publicidad y medir audiencia. En tu primera visita te mostramos un aviso de consentimiento gestionado por una
plataforma certificada por Google (CMP) donde puedes aceptar, rechazar o configurar las cookies no necesarias.</p>
<p>Puedes cambiar tu elección en cualquier momento borrando las cookies del navegador o desde el enlace de preferencias del aviso.</p>"""),
    }
    for path, (title, content) in pages.items():
        write(path, page(head(f"{title} | {s['name']}", f"{title} de {s['name']}.", path),
                         f'<div class="wrap" style="max-width:780px;padding:32px 16px 60px"><h1>{title}</h1>{content}</div>'))


def build_feeds(posts: list[dict]) -> None:
    today = dt.date.today().isoformat()
    urls = [(BASE_URL + "/", today, "daily")]
    urls += [(absu(f"/categoria/{k}/"), today, "daily") for k in CATS]
    urls += [(absu(f"/{p['slug']}/"), p.get("updated", p["date"])[:10], "monthly") for p in posts]
    urls += [(absu(p), "2026-01-01", "yearly") for p in ("/sobre-nosotros/", "/contacto/")]
    sm = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    sm += [f"<url><loc>{e(l)}</loc><lastmod>{m}</lastmod><changefreq>{c}</changefreq></url>" for l, m, c in urls]
    sm.append("</urlset>")
    (PUBLIC_DIR / "sitemap.xml").write_text("\n".join(sm), encoding="utf-8")

    items = "".join(
        f"<item><title>{e(p['title'])}</title><link>{absu(f'/{p['slug']}/')}</link>"
        f"<guid>{absu(f'/{p['slug']}/')}</guid><pubDate>{format_datetime(dt.datetime.fromisoformat(p['date']))}</pubDate>"
        f"<description>{e(p['meta_description'])}</description></item>" for p in posts[:50])
    rss = (f'<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel><title>{e(SITE["name"])}</title>'
           f"<link>{BASE_URL}/</link><description>{e(SITE['tagline'])}</description><language>{SITE['language']}</language>{items}</channel></rss>")
    (PUBLIC_DIR / "feed.xml").write_text(rss, encoding="utf-8")

    # robots.txt debe estar en la raíz del dominio; en github.io/repo solo sirve con dominio propio
    (PUBLIC_DIR / "robots.txt").write_text(f"User-agent: *\nAllow: /\n\nSitemap: {BASE_URL}/sitemap.xml\n", encoding="utf-8")
    if ADS.get("client_id"):
        pub = ADS["client_id"].replace("ca-", "")
        (PUBLIC_DIR / "ads.txt").write_text(f"google.com, {pub}, DIRECT, f08c47fec0942fa0\n", encoding="utf-8")


def main() -> None:
    if PUBLIC_DIR.exists():
        shutil.rmtree(PUBLIC_DIR)
    PUBLIC_DIR.mkdir()
    static = ROOT / "static"
    if static.exists():
        shutil.copytree(static, PUBLIC_DIR, dirs_exist_ok=True)

    posts = load_posts()
    for p in posts:
        build_article(p, posts)

    site_ld = [{"@context": "https://schema.org", "@type": "WebSite", "name": SITE["name"], "url": BASE_URL + "/",
                "inLanguage": SITE["language"]}, {"@context": "https://schema.org", **org_ld()}]
    build_listing("/", f"{SITE['name']} – {SITE['tagline']}", SITE["tagline"],
                  "Guías paso a paso para resolver problemas reales con tu móvil, tu ordenador y la inteligencia artificial.",
                  posts, jsonld=site_ld)
    for key, name in CATS.items():
        items = [p for p in posts if p["category"] == key]
        build_listing(f"/categoria/{key}/", f"{name}: trucos y guías | {SITE['name']}", name,
                      f"Todas nuestras guías de {name.lower()} explicadas paso a paso.", items)
    build_static_pages()
    build_feeds(posts)
    write("/404.html", page(head("Página no encontrada", "Esta página no existe.", "/404.html", noindex=True),
                            f'<div class="wrap hero"><h1>Vaya, esta página no existe</h1><p><a href="{u("/")}">Volver al inicio</a></p></div>'))
    (PUBLIC_DIR / ".nojekyll").write_text("", encoding="utf-8")
    print(f"Web generada: {len(posts)} artículos → {PUBLIC_DIR}")


if __name__ == "__main__":
    main()
