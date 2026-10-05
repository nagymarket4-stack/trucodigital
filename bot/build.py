"""Construye la web estática en public/ a partir de content/posts/*.json.

Diseño: portada tipo revista (hero con buscador, destacado, categorías, últimas guías, Shorts), tema claro/oscuro,
tipografía propia en woff2, tarjetas con imagen, artículo con barra de lectura, índice fijo y botones de compartir.
SEO: títulos/metas únicos, canonical, Open Graph, JSON-LD (Article, FAQPage, BreadcrumbList, VideoObject, WebSite,
Organization), sitemap con imágenes, robots.txt, RSS, enlazado interno, ads.txt, IndexNow y páginas legales.
"""
import datetime as dt
import hashlib
import html
import json
import re
import shutil
from collections import Counter
from email.utils import format_datetime
from urllib.parse import quote, urlparse

import markdown

from common import CONFIG, PUBLIC_DIR, ROOT, load_posts
from images import cover

SITE = CONFIG["site"]
CATS = CONFIG["categories"]
ADS = CONFIG["adsense"]
AN = CONFIG["analytics"]
AMZ = CONFIG.get("affiliate", {})
BASE_URL = SITE["url"].rstrip("/")
BASE_PATH = urlparse(BASE_URL).path.rstrip("/")  # "" con dominio propio, "/repo" en github.io
YEAR = dt.date.today().year
PER_PAGE = 24

# icono y color por categoría (se usan en chips, mosaicos y tarjetas)
CAT_STYLE = {
    "movil": ("📱", "#ff4d6d"), "whatsapp": ("💬", "#1fb855"), "inteligencia-artificial": ("🤖", "#7c5cff"),
    "apps": ("🧩", "#0ea5e9"), "seguridad": ("🔒", "#f59e0b"), "ordenador": ("💻", "#10b981"), "ahorro": ("💸", "#e11d8f"),
}

e = html.escape


def u(path: str) -> str:
    """Ruta relativa al sitio → ruta servida (respeta subcarpeta de GitHub Pages)."""
    return f"{BASE_PATH}{path}"


def absu(path: str) -> str:
    return f"{BASE_URL}{path}"


def md(text: str) -> str:
    out = markdown.markdown(text, extensions=["tables", "sane_lists"])
    out = re.sub(r'href="/(?!/)', f'href="{BASE_PATH}/', out)  # enlaces internos con base path
    out = re.sub(r'<a href="(https?://[^"]+)"', r'<a href="\1" rel="nofollow noopener" target="_blank"', out)
    return out.replace("<table>", '<div class="tbl"><table>').replace("</table>", "</table></div>")


def human_date(iso: str) -> str:
    d = dt.datetime.fromisoformat(iso)
    meses = "enero febrero marzo abril mayo junio julio agosto septiembre octubre noviembre diciembre".split()
    return f"{d.day} de {meses[d.month - 1]} de {d.year}"


def short_date(iso: str) -> str:
    d = dt.datetime.fromisoformat(iso)
    return f"{d.day} {'ene feb mar abr may jun jul ago sep oct nov dic'.split()[d.month - 1]}"


def minutes(p: dict) -> int:
    return max(2, round(p.get("words", 900) / 220))


def cat_style(key: str) -> tuple[str, str]:
    return CAT_STYLE.get(key, ("✨", "#ff4d6d"))


CSS = """
@font-face{font-family:Poppins;font-weight:800;font-display:swap;src:url(FONT_XB) format("woff2")}
@font-face{font-family:Poppins;font-weight:600;font-display:swap;src:url(FONT_SB) format("woff2")}
:root{--bg:#f6f6fb;--bg2:#ffffff;--fg:#0f1222;--muted:#5b6078;--card:#fff;--line:#e5e6ef;--brand:#ff4d6d;--brand2:#7c5cff;
--link:#5b4cf0;--soft:#fff0f3;--shadow:0 1px 2px rgba(16,18,40,.04),0 8px 24px rgba(16,18,40,.06);--hdr:rgba(255,255,255,.78)}
:root[data-theme=dark]{--bg:#0b0c14;--bg2:#10111c;--fg:#eef0ff;--muted:#a3a7c2;--card:#151728;--line:#262a42;--link:#a99bff;
--soft:#2a1420;--shadow:0 1px 2px rgba(0,0,0,.3),0 10px 30px rgba(0,0,0,.35);--hdr:rgba(11,12,20,.75)}
@media (prefers-color-scheme:dark){:root:not([data-theme=light]){--bg:#0b0c14;--bg2:#10111c;--fg:#eef0ff;--muted:#a3a7c2;
--card:#151728;--line:#262a42;--link:#a99bff;--soft:#2a1420;--shadow:0 1px 2px rgba(0,0,0,.3),0 10px 30px rgba(0,0,0,.35);--hdr:rgba(11,12,20,.75)}}
*{box-sizing:border-box}html{-webkit-text-size-adjust:100%;scroll-behavior:smooth;scroll-padding-top:84px}
body{margin:0;background:var(--bg);color:var(--fg);font:17px/1.7 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;-webkit-font-smoothing:antialiased}
h1,h2,h3,.logo,.btn,.chip,.eyebrow{font-family:Poppins,system-ui,sans-serif}
h1,h2,h3{letter-spacing:-.02em;line-height:1.18;font-weight:800}
a{color:var(--link)}img{max-width:100%;height:auto;display:block}
.wrap{max-width:1180px;margin:0 auto;padding:0 16px}
.sr{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0)}
/* cabecera */
.top{position:sticky;top:0;z-index:20;background:var(--hdr);backdrop-filter:saturate(1.6) blur(14px);-webkit-backdrop-filter:saturate(1.6) blur(14px);border-bottom:1px solid var(--line)}
.top .wrap{display:flex;align-items:center;gap:20px;height:64px}
.logo{display:flex;align-items:center;gap:10px;font-weight:800;font-size:21px;color:var(--fg);text-decoration:none;letter-spacing:-.03em;white-space:nowrap}
.logo img{width:34px;height:34px;filter:drop-shadow(0 6px 12px rgba(255,77,109,.35))}.logo i{width:34px;height:34px;border-radius:10px;background:linear-gradient(135deg,var(--brand),var(--brand2));display:grid;place-items:center;color:#fff;font-style:normal;font-size:19px;box-shadow:0 6px 16px rgba(255,77,109,.35)}
.logo b{background:linear-gradient(90deg,var(--brand),var(--brand2));-webkit-background-clip:text;background-clip:text;color:transparent}
.nav{display:flex;gap:4px;overflow-x:auto;scrollbar-width:none;flex:1}.nav::-webkit-scrollbar{display:none}
.nav a{color:var(--muted);text-decoration:none;white-space:nowrap;font-size:14.5px;font-weight:600;padding:7px 12px;border-radius:999px}
.nav a:hover,.nav a[aria-current]{color:var(--fg);background:var(--card)}
.tools{display:flex;gap:6px;margin-left:auto}
.icon{width:40px;height:40px;border-radius:12px;border:1px solid var(--line);background:var(--card);color:var(--fg);display:grid;place-items:center;cursor:pointer;text-decoration:none;font-size:17px}
.icon:hover{border-color:var(--brand)}
@media (max-width:860px){.top .wrap{height:auto;flex-wrap:wrap;padding-top:10px;padding-bottom:8px;gap:8px 12px}.nav{order:3;flex-basis:100%;margin:0 -16px;padding:0 12px}}
/* botones y chips */
.btn{display:inline-flex;align-items:center;gap:8px;font-weight:700;font-size:15px;padding:12px 20px;border-radius:14px;text-decoration:none;border:0;cursor:pointer;background:linear-gradient(135deg,var(--brand),var(--brand2));color:#fff;box-shadow:0 8px 22px rgba(124,92,255,.28)}
.btn.ghost{background:var(--card);color:var(--fg);border:1px solid var(--line);box-shadow:none}
.chip{display:inline-flex;align-items:center;gap:6px;font-size:12.5px;font-weight:700;padding:5px 11px;border-radius:999px;text-decoration:none;color:#fff;background:var(--c,#ff4d6d);letter-spacing:.01em;line-height:1.3}
.in>.chip,.row .chip{align-self:flex-start}
.chip.soft{background:color-mix(in srgb,var(--c) 14%,transparent);color:var(--c)}
.eyebrow{display:inline-flex;align-items:center;gap:8px;font-size:13px;font-weight:700;padding:6px 14px;border-radius:999px;background:var(--card);border:1px solid var(--line);color:var(--muted)}
.eyebrow .dot{width:8px;height:8px;border-radius:50%;background:#1fb855;box-shadow:0 0 0 4px rgba(31,184,85,.18)}
/* hero */
.hero{position:relative;overflow:hidden;padding:64px 0 40px;border-bottom:1px solid var(--line);background:
radial-gradient(600px 300px at 12% 0%,rgba(255,77,109,.16),transparent 70%),radial-gradient(700px 360px at 95% 10%,rgba(124,92,255,.18),transparent 70%),var(--bg2)}
.hero h1{font-size:clamp(34px,5.6vw,62px);margin:18px 0 14px;max-width:760px}
.hgrid{display:grid;grid-template-columns:1.25fr .9fr;gap:40px;align-items:center}
.art{position:relative;height:440px}
.art img{position:absolute;width:78%;border-radius:18px;box-shadow:0 24px 60px rgba(16,18,40,.28);border:4px solid var(--card)}
.art img:nth-child(1){right:0;top:0;transform:rotate(5deg)}
.art img:nth-child(2){left:0;top:120px;transform:rotate(-5deg)}
.art img:nth-child(3){right:6%;top:250px;transform:rotate(2deg)}
.art .badge{position:absolute;z-index:3;background:var(--card);border:1px solid var(--line);border-radius:14px;padding:10px 14px;
font:700 14px Poppins,system-ui;box-shadow:var(--shadow);animation:float 5s ease-in-out infinite}
.art .b1{left:-4%;top:40px}.art .b2{right:-2%;top:200px;animation-delay:-2s}.art .b3{left:10%;bottom:6px;animation-delay:-3.5s}
@keyframes float{50%{transform:translateY(-8px)}}
@media (prefers-reduced-motion:reduce){.art .badge{animation:none}}
@media (max-width:980px){.hgrid{grid-template-columns:1fr}.art{display:none}}
.hero h1 span{background:linear-gradient(90deg,var(--brand),var(--brand2));-webkit-background-clip:text;background-clip:text;color:transparent}
.hero p.lead{font-size:clamp(17px,2vw,20px);color:var(--muted);max-width:640px;margin:0 0 26px}
.sbox{display:flex;gap:8px;max-width:620px;background:var(--card);border:1px solid var(--line);border-radius:18px;padding:7px;box-shadow:var(--shadow)}
.sbox input{flex:1;min-width:0;border:0;background:transparent;color:var(--fg);font-size:17px;padding:10px 12px;outline:none}
.pop{display:flex;flex-wrap:wrap;gap:8px;margin-top:18px;font-size:14px;color:var(--muted);align-items:center}
.pop a{color:var(--fg);text-decoration:none;background:var(--card);border:1px solid var(--line);padding:5px 12px;border-radius:999px;font-weight:600;font-size:13.5px}
.pop a:hover{border-color:var(--brand)}
.stats{display:flex;gap:28px;margin-top:34px;flex-wrap:wrap}.stats b{display:block;font:800 26px Poppins,system-ui;letter-spacing:-.02em}.stats span{font-size:13.5px;color:var(--muted)}
/* secciones */
section.block{padding:52px 0 8px}
.sh{display:flex;align-items:end;justify-content:space-between;gap:16px;margin-bottom:22px}
.sh h2{font-size:clamp(24px,3vw,32px);margin:0}.sh p{margin:4px 0 0;color:var(--muted);font-size:15px}
.sh a{font-weight:700;font-size:14.5px;text-decoration:none;white-space:nowrap}
/* destacado */
.feat{display:grid;grid-template-columns:1.35fr 1fr;gap:22px}
@media (max-width:900px){.feat{grid-template-columns:1fr}}
.big{position:relative;border-radius:22px;overflow:hidden;background:var(--card);box-shadow:var(--shadow);border:1px solid var(--line);display:flex;flex-direction:column}
.big img{aspect-ratio:1200/630;width:100%;object-fit:cover}
.big .in{padding:22px 24px 24px}.big h3{font-size:clamp(22px,2.6vw,30px);margin:12px 0 10px}.big h3 a{color:var(--fg);text-decoration:none}
.big p{color:var(--muted);margin:0 0 12px}
.list{display:flex;flex-direction:column;gap:14px}
.row{display:grid;grid-template-columns:132px 1fr;gap:14px;align-items:center;background:var(--card);border:1px solid var(--line);border-radius:18px;padding:10px;box-shadow:var(--shadow);text-decoration:none;color:var(--fg);transition:transform .15s,border-color .15s}
.row:hover{transform:translateY(-2px);border-color:color-mix(in srgb,var(--brand) 40%,var(--line))}
.row img{border-radius:12px;aspect-ratio:1200/630;object-fit:cover;width:100%}
.row h3{font-size:16px;margin:6px 0 2px;line-height:1.3}
/* categorías */
.cats{display:grid;grid-template-columns:repeat(auto-fill,minmax(160px,1fr));gap:12px}
.tile{position:relative;display:flex;flex-direction:column;gap:6px;padding:18px;border-radius:18px;text-decoration:none;color:var(--fg);background:var(--card);border:1px solid var(--line);overflow:hidden;transition:transform .15s}
.tile:before{content:"";position:absolute;inset:auto -30px -30px auto;width:110px;height:110px;border-radius:50%;background:var(--c);opacity:.14}
.tile:hover{transform:translateY(-3px);border-color:var(--c)}
.tile .em{font-size:28px}.tile b{font:700 16px Poppins,system-ui}.tile span{font-size:13px;color:var(--muted)}
/* tarjetas */
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(290px,1fr));gap:22px}
.card{display:flex;flex-direction:column;background:var(--card);border:1px solid var(--line);border-radius:20px;overflow:hidden;box-shadow:var(--shadow);transition:transform .18s,border-color .18s}
.card:hover{transform:translateY(-4px);border-color:color-mix(in srgb,var(--brand) 35%,var(--line))}
.card .th{position:relative;display:block}.card .th img{aspect-ratio:1200/630;width:100%;object-fit:cover}
.card .th .chip{position:absolute;z-index:2;left:12px;top:12px;box-shadow:0 4px 12px rgba(0,0,0,.2)}
.card .in{padding:16px 18px 18px;display:flex;flex-direction:column;gap:8px;flex:1}
.card h3{font-size:18.5px;margin:0;line-height:1.3}.card h3 a{color:var(--fg);text-decoration:none}
.card h3 a:after{content:"";position:absolute;inset:0}.card{position:relative}
.card p{margin:0;color:var(--muted);font-size:15px;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.meta{font-size:13px;color:var(--muted);display:flex;gap:10px;align-items:center;margin-top:auto}
/* shorts */
.shorts{display:grid;grid-auto-flow:column;grid-auto-columns:minmax(180px,210px);gap:14px;overflow-x:auto;padding-bottom:10px;scroll-snap-type:x mandatory}
.short{position:relative;aspect-ratio:9/16;border-radius:18px;overflow:hidden;background:#000;scroll-snap-align:start;color:#fff;text-decoration:none}
.short img{width:100%;height:100%;object-fit:cover;opacity:.85}
.short span{position:absolute;inset:auto 0 0 0;padding:40px 14px 14px;font:700 14.5px/1.3 Poppins,system-ui;background:linear-gradient(transparent,rgba(0,0,0,.85))}
.short:before{content:"▶";position:absolute;top:12px;right:12px;width:34px;height:34px;border-radius:50%;background:rgba(255,255,255,.9);color:#111;display:grid;place-items:center;font-size:13px;z-index:1}
/* banda cta */
.band{margin:56px 0 0;border-radius:26px;padding:40px 32px;background:linear-gradient(135deg,var(--brand),var(--brand2));color:#fff;display:flex;gap:24px;align-items:center;justify-content:space-between;flex-wrap:wrap;position:relative;overflow:hidden}
.band h2{margin:0 0 6px;font-size:clamp(24px,3vw,34px)}.band p{margin:0;opacity:.92;max-width:560px}
.band .btn{background:#fff;color:#111;box-shadow:none}.band .btn.ghost{background:rgba(255,255,255,.16);color:#fff;border-color:rgba(255,255,255,.35)}
/* listados */
.phead{padding:44px 0 28px;border-bottom:1px solid var(--line);background:radial-gradient(600px 240px at 0% 0%,color-mix(in srgb,var(--c,#ff4d6d) 16%,transparent),transparent 70%),var(--bg2);margin-bottom:34px}
.phead h1{font-size:clamp(30px,4.4vw,48px);margin:12px 0 8px}.phead p{color:var(--muted);margin:0;max-width:640px}
.pager{display:flex;gap:10px;justify-content:center;padding:36px 0}.pager a{padding:10px 16px;border:1px solid var(--line);border-radius:12px;text-decoration:none;background:var(--card);font-weight:700}
/* artículo */
.progress{position:fixed;top:0;left:0;height:3px;width:0;z-index:30;background:linear-gradient(90deg,var(--brand),var(--brand2))}
.ahead{padding:36px 0 8px;max-width:860px}
.crumbs{font-size:13.5px;color:var(--muted);display:flex;gap:6px;flex-wrap:wrap}.crumbs a{color:var(--muted);text-decoration:none}
.ahead h1{font-size:clamp(30px,4.6vw,50px);margin:14px 0 16px}
.byline{display:flex;align-items:center;gap:12px;font-size:14px;color:var(--muted);flex-wrap:wrap}
.byline .av{width:38px;height:38px;border-radius:12px;background:linear-gradient(135deg,var(--brand),var(--brand2));display:grid;place-items:center;color:#fff;font:800 17px Poppins,system-ui}
.byline b{color:var(--fg)}
.hero-img{width:100%;aspect-ratio:1200/630;object-fit:cover;border-radius:22px;margin:26px 0 8px;box-shadow:var(--shadow)}
.layout{display:grid;grid-template-columns:minmax(0,740px) 300px;gap:56px;justify-content:space-between;padding:10px 0 70px}
@media (max-width:1000px){.layout{grid-template-columns:1fr}.layout aside{order:2}}
.prose{font-size:18px;line-height:1.78}.prose h2{font-size:clamp(23px,2.6vw,29px);margin:48px 0 12px}.prose h3{font-size:20px;margin:30px 0 8px}
.prose li{margin:6px 0}.prose img{border-radius:14px}
.prose blockquote{margin:20px 0;padding:14px 20px;border-left:4px solid #f5a524;background:color-mix(in srgb,#f5a524 10%,var(--card));border-radius:12px}.prose blockquote p{margin:0}
.tbl{overflow-x:auto;margin:18px 0;border:1px solid var(--line);border-radius:14px}
.prose table{border-collapse:collapse;width:100%;font-size:15.5px;line-height:1.5}
.prose th{background:color-mix(in srgb,var(--brand2) 10%,var(--card));text-align:left}
.prose th,.prose td{padding:10px 14px;border-bottom:1px solid var(--line)}.prose tr:last-child td{border-bottom:0}
.tldr{background:linear-gradient(135deg,color-mix(in srgb,var(--brand) 9%,var(--card)),color-mix(in srgb,var(--brand2) 9%,var(--card)));border:1px solid var(--line);border-radius:18px;padding:18px 22px;margin:26px 0}
.tldr strong{font-family:Poppins,system-ui}.tldr ul{margin:8px 0 0;padding-left:20px}.tldr li{margin:6px 0}
.share{display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin:26px 0}
.share span{font-weight:700;font-size:14px;margin-right:4px}
.share a,.share button{font:600 13.5px system-ui;padding:8px 13px;border-radius:12px;border:1px solid var(--line);background:var(--card);color:var(--fg);text-decoration:none;cursor:pointer}
.share a:hover,.share button:hover{border-color:var(--brand)}
details{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:14px 18px;margin:10px 0}
summary{font-weight:700;cursor:pointer;font-size:16.5px}details p{margin:10px 0 0}
.video{position:relative;aspect-ratio:9/16;max-width:320px;margin:26px auto;border-radius:18px;overflow:hidden;background:#000;box-shadow:var(--shadow)}
.video iframe{position:absolute;inset:0;width:100%;height:100%;border:0}
.side{position:sticky;top:88px;display:flex;flex-direction:column;gap:18px}
.box{background:var(--card);border:1px solid var(--line);border-radius:18px;padding:18px 20px;box-shadow:var(--shadow)}
.box h4{margin:0 0 10px;font:700 15px Poppins,system-ui}
.toc ol{margin:0;padding-left:18px;font-size:14.5px;line-height:1.45}.toc li{margin:8px 0}.toc a{color:var(--muted);text-decoration:none}
.toc a.on{color:var(--fg);font-weight:700}
.mini{display:flex;flex-direction:column;gap:12px}.mini a{display:grid;grid-template-columns:78px 1fr;gap:10px;align-items:center;color:var(--fg);text-decoration:none;font-size:14px;font-weight:600;line-height:1.35}
.mini img{border-radius:8px;aspect-ratio:1200/630;object-fit:cover}
.shop{background:var(--card);border:2px solid color-mix(in srgb,#ff9900 60%,var(--line));border-radius:18px;padding:18px 22px;margin:34px 0}
.shop h2{margin:0 0 8px!important;font-size:21px!important}.shop li{margin:10px 0}
.shop a.buy{display:inline-block;background:#ff9900;color:#111;font-weight:700;padding:5px 12px;border-radius:9px;text-decoration:none;font-size:14px;margin-left:6px}
.shop small{color:var(--muted)}
.follow{display:flex;gap:10px;flex-wrap:wrap;align-items:center;background:var(--soft);border-radius:16px;padding:16px 20px;margin:26px 0}
.ad{margin:30px 0;min-height:100px}
/* buscador */
#q{width:100%;font-size:19px;padding:16px 18px;border-radius:16px;border:1px solid var(--line);background:var(--card);color:var(--fg);box-shadow:var(--shadow);outline:none}
#q:focus{border-color:var(--brand2)}
/* pie */
footer{margin-top:70px;border-top:1px solid var(--line);background:var(--bg2);padding:48px 0 30px;font-size:14.5px;color:var(--muted)}
.fgrid{display:grid;grid-template-columns:1.6fr 1fr 1fr 1fr;gap:28px}
@media (max-width:800px){.fgrid{grid-template-columns:1fr 1fr}}
footer h4{color:var(--fg);font:700 14px Poppins,system-ui;margin:0 0 12px}footer ul{list-style:none;margin:0;padding:0}footer li{margin:7px 0}
footer a{color:var(--muted);text-decoration:none}footer a:hover{color:var(--fg)}
.legal{border-top:1px solid var(--line);margin-top:34px;padding-top:20px;display:flex;justify-content:space-between;flex-wrap:wrap;gap:10px}
.page{max-width:780px;padding:40px 16px 20px}.page h1{font-size:clamp(30px,4vw,44px)}
"""

THEME_JS = ("<script>try{var t=localStorage.getItem('theme');if(t)document.documentElement.dataset.theme=t}catch(e){}"
            "</script>")
UI_JS = """<script>
document.getElementById('tt').onclick=function(){var r=document.documentElement,
d=r.dataset.theme?r.dataset.theme==='dark':matchMedia('(prefers-color-scheme:dark)').matches;
r.dataset.theme=d?'light':'dark';try{localStorage.setItem('theme',r.dataset.theme)}catch(e){}};
var pb=document.querySelector('.progress');if(pb){addEventListener('scroll',function(){var h=document.documentElement;
pb.style.width=(h.scrollTop/(h.scrollHeight-h.clientHeight)*100)+'%'},{passive:true});
var links=[].slice.call(document.querySelectorAll('.toc a'));if('IntersectionObserver'in window&&links.length){
var io=new IntersectionObserver(function(es){es.forEach(function(x){if(x.isIntersecting){links.forEach(function(l){
l.classList.toggle('on',l.getAttribute('href')==='#'+x.target.id)})}})},{rootMargin:'-80px 0px -70% 0px'});
links.forEach(function(l){var t=document.getElementById(l.getAttribute('href').slice(1));if(t)io.observe(t)})}}
var cp=document.getElementById('cp');if(cp)cp.onclick=function(){navigator.clipboard.writeText(location.href).then(function(){cp.textContent='¡Copiado!'})};
</script>"""


def head(title: str, desc: str, path: str, *, og_type="website", jsonld: list | None = None,
         noindex=False, extra="", image: str | None = None) -> str:
    canonical = absu(path)
    image = image or absu("/img/og-default.jpg")
    css = CSS.replace("FONT_XB", u("/webfonts/Poppins-ExtraBold.woff2")).replace("FONT_SB", u("/webfonts/Poppins-SemiBold.woff2"))
    tags = [
        '<meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width,initial-scale=1">',
        f"<title>{e(title)}</title>",
        f'<meta name="description" content="{e(desc)}">',
        f'<link rel="canonical" href="{canonical}">',
        f'<meta name="robots" content="{"noindex,follow" if noindex else "index,follow,max-image-preview:large"}">',
        '<meta name="theme-color" content="#ff4d6d">',
        f'<meta property="og:site_name" content="{e(SITE["name"])}">',
        f'<meta property="og:locale" content="{SITE["locale"]}">',
        f'<meta property="og:type" content="{og_type}">',
        f'<meta property="og:title" content="{e(title)}">',
        f'<meta property="og:description" content="{e(desc)}">',
        f'<meta property="og:url" content="{canonical}">',
        f'<meta property="og:image" content="{image}">',
        '<meta property="og:image:width" content="1200"><meta property="og:image:height" content="630">',
        '<meta name="twitter:card" content="summary_large_image">',
        f'<meta name="twitter:image" content="{image}">',
        f'<link rel="alternate" type="application/rss+xml" title="{e(SITE["name"])}" href="{u("/feed.xml")}">',
        f'<link rel="icon" href="{u("/favicon.svg")}" type="image/svg+xml">',
        f'<link rel="manifest" href="{u("/manifest.webmanifest")}">',
        f'<link rel="apple-touch-icon" href="{u("/apple-touch-icon.png")}">',
        f'<link rel="preload" href="{u("/webfonts/Poppins-ExtraBold.woff2")}" as="font" type="font/woff2" crossorigin>',
        THEME_JS,
        f"<style>{css}</style>",
    ]
    if AN.get("google_site_verification"):
        tags.append(f'<meta name="google-site-verification" content="{e(AN["google_site_verification"])}">')
    if AN.get("bing_site_verification"):
        tags.append(f'<meta name="msvalidate.01" content="{e(AN["bing_site_verification"])}">')
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


def logo_html() -> str:
    name = SITE["name"]
    split = 5 if len(name) > 5 else len(name)
    return f'<a class="logo" href="{u("/")}"><img src="{u("/favicon.svg")}" alt="" width="34" height="34"><span>{e(name[:split])}<b>{e(name[split:])}</b></span></a>'


def header_html(active: str = "") -> str:
    links = "".join(f'<a href="{u(f"/categoria/{k}/")}"{" aria-current=page" if k == active else ""}>{e(v)}</a>'
                    for k, v in CATS.items())
    return (f'<header class="top"><div class="wrap">{logo_html()}<nav class="nav" aria-label="Categorías">{links}</nav>'
            f'<div class="tools"><a class="icon" href="{u("/buscar/")}" aria-label="Buscar">🔎</a>'
            '<button class="icon" id="tt" aria-label="Cambiar tema claro u oscuro">🌓</button></div></div></header>')


def socials() -> list[tuple[str, str]]:
    return [(n, url) for n, url in (("▶ YouTube", SITE.get("youtube_channel_url")), ("♪ TikTok", SITE.get("tiktok_url"))) if url]


def footer_html() -> str:
    cats = "".join(f'<li><a href="{u(f"/categoria/{k}/")}">{cat_style(k)[0]} {e(v)}</a></li>' for k, v in CATS.items())
    site = "".join(f'<li><a href="{u(p)}">{t}</a></li>' for p, t in
                   (("/sobre-nosotros/", "Sobre nosotros"), ("/contacto/", "Contacto"), ("/buscar/", "Buscar"),
                    ("/feed.xml", "RSS")))
    follow = "".join(f'<li><a href="{url}" rel="noopener" target="_blank">{n}</a></li>' for n, url in socials()) \
        or '<li>Vídeos cortos muy pronto</li>'
    legal = "".join(f'<a href="{u(p)}">{t}</a> · ' for p, t in
                    (("/aviso-legal/", "Aviso legal"), ("/privacidad/", "Privacidad"), ("/cookies/", "Cookies"),
                     ("/terminos/", "Términos"))).rstrip(" · ")
    return (f'<footer><div class="wrap"><div class="fgrid"><div>{logo_html()}<p style="max-width:340px">{e(SITE["tagline"])}. '
            'Guías paso a paso, claras y actualizadas, para resolver problemas reales en minutos.</p></div>'
            f'<div><h4>Categorías</h4><ul>{cats}</ul></div><div><h4>El sitio</h4><ul>{site}</ul></div>'
            f'<div><h4>Síguenos</h4><ul>{follow}</ul></div></div>'
            f'<div class="legal"><span>© {YEAR} {e(SITE["name"])}</span><span>{legal}</span></div></div></footer>')


def page(head_html: str, body: str, active: str = "") -> str:
    return (f'<!doctype html><html lang="{SITE["language"]}"><head>{head_html}</head>'
            f"<body>{header_html(active)}<main>{body}</main>{footer_html()}{UI_JS}</body></html>")


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


def chip(key: str, soft: bool = False) -> str:
    em, c = cat_style(key)
    return (f'<a class="chip{" soft" if soft else ""}" style="--c:{c}" href="{u(f"/categoria/{key}/")}">'
            f'{em} {e(CATS.get(key, key))}</a>')


def img_tag(p: dict, eager: bool = False, full: bool = False) -> str:
    load = 'fetchpriority="high"' if eager else 'loading="lazy" decoding="async"'
    src = u(f"/img/{p['slug']}.jpg") if full else u(f"/img/t/{p['slug']}.jpg")
    return f'<img src="{src}" alt="{e(p["title"])}" width="1200" height="630" {load}>'


def card(p: dict) -> str:
    return (f'<article class="card"><span class="th">{img_tag(p)}{chip(p["category"])}</span>'
            f'<div class="in"><h3><a href="{u(f"/{p["slug"]}/")}">{e(p["title"])}</a></h3>'
            f'<p>{e(p["meta_description"])}</p>'
            f'<div class="meta"><span>{short_date(p["date"])}</span>·<span>{minutes(p)} min</span></div></div></article>')


def org_ld() -> dict:
    same = [url for _, url in socials()]
    return {"@type": "Organization", "name": SITE["name"], "url": BASE_URL + "/", "sameAs": same,
            "logo": absu("/logo-512.png")}


def share_html(p: dict) -> str:
    url = quote(absu(f"/{p['slug']}/"), safe="")
    txt = quote(p["title"], safe="")
    links = [("WhatsApp", f"https://wa.me/?text={txt}%20{url}"), ("Telegram", f"https://t.me/share/url?url={url}&amp;text={txt}"),
             ("X", f"https://x.com/intent/post?url={url}&amp;text={txt}"), ("Facebook", f"https://www.facebook.com/sharer/sharer.php?u={url}")]
    a = "".join(f'<a href="{h}" target="_blank" rel="noopener nofollow">{n}</a>' for n, h in links)
    return f'<div class="share"><span>Compartir:</span>{a}<button id="cp" type="button">Copiar enlace</button></div>'


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
    img_url = absu(f"/img/{p['slug']}.jpg")
    shop_html = ""
    if p.get("products") and AMZ.get("amazon_tag"):
        items = "".join(
            f'<li><strong>{e(x["name"])}</strong>: {e(x["reason"])} '
            f'<a class="buy" rel="sponsored nofollow noopener" target="_blank" '
            f'href="https://www.amazon.es/s?k={quote(x["search_query"])}&amp;tag={e(AMZ["amazon_tag"])}">Ver precios</a></li>'
            for x in p["products"])
        shop_html = (f'<section class="shop"><h2>🛒 Lo que te puede ayudar</h2><ul>{items}</ul>'
                     '<small>Enlaces de afiliado: si compras, recibimos una pequeña comisión sin coste para ti.</small></section>')
    follow = "".join(f'<a class="btn ghost" href="{url}" rel="noopener" target="_blank">{n}</a>' for n, url in socials())
    follow_html = f'<div class="follow"><strong>¿Prefieres verlo en 30 segundos?</strong>{follow}</div>' if follow else ""
    faq_html = "".join(f"<details><summary>{e(f['question'])}</summary>{md(f['answer'])}</details>" for f in p["faq"])
    takeaways = "".join(f"<li>{e(t)}</li>" for t in p["key_takeaways"])

    related = [x for x in posts if x["slug"] != p["slug"] and x["category"] == p["category"]][:5]
    if len(related) < 5:
        related += [x for x in posts if x["slug"] != p["slug"] and x not in related][: 5 - len(related)]
    rel_side = "".join(f'<a href="{u(f"/{x["slug"]}/")}">{img_tag(x)}<span>{e(x["title"])}</span></a>' for x in related)
    rel_grid = "".join(card(x) for x in related[:3])

    ld = [
        {"@context": "https://schema.org", "@type": "Article", "headline": p["title"][:110],
         "description": p["meta_description"], "datePublished": p["date"], "dateModified": p.get("updated", p["date"]),
         "inLanguage": SITE["language"], "mainEntityOfPage": absu(path), "keywords": ", ".join(p["tags"]),
         "author": {"@type": "Organization", "name": SITE["author"], "url": absu("/sobre-nosotros/")},
         "image": [img_url], "publisher": org_ld()},
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

    body = f"""<div class="progress"></div><div class="wrap">
<header class="ahead"><nav class="crumbs"><a href="{u('/')}">Inicio</a>›<a href="{u(f'/categoria/{p["category"]}/')}">{e(cat)}</a></nav>
<h1>{e(p['title'])}</h1>
<div class="byline"><span class="av">{e(SITE['name'][0])}</span><span><b>{e(SITE['author'])}</b><br>
Actualizado el {human_date(p.get('updated', p['date']))} · {minutes(p)} min de lectura</span>{chip(p['category'], soft=True)}</div></header>
<div class="layout"><article class="prose">
<img class="hero-img" src="{u(f"/img/{p['slug']}.jpg")}" alt="{e(p['title'])}" width="1200" height="630" fetchpriority="high">
{md(p['intro_markdown'])}
<div class="tldr"><strong>⚡ En resumen</strong><ul>{takeaways}</ul></div>
{video_html}
{''.join(body_parts)}
{shop_html}
<h2 id="preguntas-frecuentes">Preguntas frecuentes</h2>{faq_html}
{share_html(p)}
{follow_html}
{ad_unit()}
</article>
<aside><div class="side"><nav class="box toc" aria-label="Índice"><h4>En esta guía</h4><ol>{toc}<li><a href="#preguntas-frecuentes">Preguntas frecuentes</a></li></ol></nav>
{f'<div class="box"><h4>Te puede interesar</h4><div class="mini">{rel_side}</div></div>' if rel_side else ''}</div></aside></div>
{f'<section class="block" style="padding-top:0"><div class="sh"><h2>Sigue aprendiendo</h2></div><div class="grid">{rel_grid}</div></section>' if rel_grid else ''}
</div>"""
    write(path, page(head(p["seo_title"], p["meta_description"], path, og_type="article", jsonld=ld, image=img_url,
                          extra=f'<meta property="article:published_time" content="{p["date"]}">'), body, p["category"]))


def build_home(posts: list[dict], jsonld: list) -> None:
    counts = Counter(p["category"] for p in posts)
    tags = [t for t, _ in Counter(t for p in posts for t in p.get("tags", [])).most_common(7)]
    pop = "".join(f'<a href="{u("/buscar/")}?q={quote(t)}">{e(t)}</a>' for t in tags)
    art = "".join(img_tag(x, eager=True) for x in posts[:3])
    art_html = (f'<div class="art" aria-hidden="true">{art}<span class="badge b1">⚡ Trucos en 30 s</span>'
                f'<span class="badge b2">✅ Paso a paso</span><span class="badge b3">📱 Android · iPhone · PC</span></div>'
                if len(posts) >= 3 else "")
    hero = f"""<section class="hero"><div class="wrap hgrid"><div>
<span class="eyebrow"><span class="dot"></span>Guías nuevas cada día · {len(posts)} publicadas</span>
<h1>Domina tu móvil, tus apps y la <span>inteligencia artificial</span> en minutos</h1>
<p class="lead">Trucos y guías paso a paso, sin tecnicismos, para resolver problemas reales con tu Android, tu iPhone o tu ordenador.</p>
<form class="sbox" action="{u('/buscar/')}" role="search"><label class="sr" for="hq">Buscar</label>
<input id="hq" name="q" type="search" placeholder="¿Qué quieres solucionar? Ej.: batería, WhatsApp…"><button class="btn" type="submit">Buscar</button></form>
{f'<div class="pop"><span>Popular:</span>{pop}</div>' if pop else ''}
<div class="stats"><div><b>{len(posts)}+</b><span>guías paso a paso</span></div><div><b>5</b><span>nuevas cada día</span></div>
<div><b>{len(CATS)}</b><span>temas</span></div><div><b>100%</b><span>gratis</span></div></div></div>{art_html}</div></section>"""

    feat = ""
    if posts:
        f0, rest = posts[0], posts[1:4]
        rows = "".join(f'<a class="row" href="{u(f"/{x["slug"]}/")}">{img_tag(x)}<div>{chip(x["category"], soft=True).replace("<a ", "<span ").replace("</a>", "</span>")}'
                       f'<h3>{e(x["title"])}</h3><div class="meta">{minutes(x)} min de lectura</div></div></a>' for x in rest)
        feat = f"""<section class="block"><div class="wrap"><div class="sh"><div><h2>Lo más nuevo</h2><p>Recién salido del horno, revisado y listo para usar.</p></div></div>
<div class="feat"><article class="big card"><span class="th">{img_tag(f0, full=True)}</span><div class="in">{chip(f0['category'])}
<h3><a href="{u(f"/{f0['slug']}/")}">{e(f0['title'])}</a></h3><p>{e(f0['meta_description'])}</p>
<div class="meta">{human_date(f0['date'])} · {minutes(f0)} min de lectura</div></div></article>
<div class="list">{rows}</div></div></div></section>"""

    tiles = "".join(f'<a class="tile" style="--c:{cat_style(k)[1]}" href="{u(f"/categoria/{k}/")}"><span class="em">{cat_style(k)[0]}</span>'
                    f'<b>{e(v)}</b><span>{counts.get(k, 0)} guías</span></a>' for k, v in CATS.items())
    cats = f"""<section class="block"><div class="wrap"><div class="sh"><div><h2>Explora por tema</h2><p>Todo lo que necesitas, ordenado.</p></div></div>
<div class="cats">{tiles}</div></div></section>"""

    vids = [p for p in posts if p.get("video", {}).get("youtube_id")][:12]
    shorts = ""
    if vids:
        items = "".join(f'<a class="short" href="https://www.youtube.com/shorts/{p["video"]["youtube_id"]}" target="_blank" rel="noopener">'
                        f'<img src="https://i.ytimg.com/vi/{p["video"]["youtube_id"]}/oar2.jpg" alt="" loading="lazy">'
                        f'<span>{e(p["short"]["title"])}</span></a>' for p in vids)
        shorts = f"""<section class="block"><div class="wrap"><div class="sh"><div><h2>Trucos en 30 segundos</h2><p>Nuestros vídeos cortos, directos al grano.</p></div></div>
<div class="shorts">{items}</div></div></section>"""

    latest = posts[4:16] if len(posts) > 7 else posts
    grid = f"""<section class="block"><div class="wrap"><div class="sh"><div><h2>Últimas guías</h2><p>Soluciones claras a los problemas de cada día.</p></div>
{f'<a href="{u("/pagina/2/")}">Ver todas →</a>' if len(posts) > 16 else ''}</div><div class="grid">{''.join(card(p) for p in latest)}</div></div></section>"""

    buttons = "".join(f'<a class="btn ghost" href="{url}" target="_blank" rel="noopener">{n}</a>' for n, url in socials())
    band = f"""<div class="wrap"><div class="band"><div><h2>Un truco nuevo cada día</h2><p>Guarda {e(SITE['name'])} en favoritos o síguenos:
cada mañana publicamos nuevas guías y vídeos cortos con lo que de verdad funciona.</p></div>
<div style="display:flex;gap:10px;flex-wrap:wrap">{buttons}<a class="btn" href="{u('/feed.xml')}">Suscribirme (RSS)</a></div></div></div>"""

    body = hero + feat + cats + shorts + grid + band
    write("/", page(head(f"{SITE['name']}: {SITE['tagline']}",
                         "Guías paso a paso para resolver problemas reales con tu móvil, WhatsApp, tus apps, tu ordenador y la inteligencia artificial.",
                         "/", jsonld=jsonld), body))
    # archivo paginado completo (/pagina/2/…)
    pages = [posts[i:i + PER_PAGE] for i in range(0, len(posts), PER_PAGE)]
    for n, chunk in enumerate(pages[1:], start=2):
        build_listing_page(f"/pagina/{n}/", f"Todas las guías – página {n} | {SITE['name']}", "Todas las guías", "", chunk,
                           prev=u("/") if n == 2 else u(f"/pagina/{n - 1}/"),
                           nxt=u(f"/pagina/{n + 1}/") if n < len(pages) else None)


def build_listing_page(path: str, title: str, h1: str, desc: str, items: list[dict], prev=None, nxt=None,
                       key: str = "", jsonld=None) -> None:
    em, c = cat_style(key) if key else ("📚", "#7c5cff")
    pager = ""
    if prev or nxt:
        pager = (f'<div class="pager">{f"<a href={prev!r}>← Anteriores</a>" if prev else ""}'
                 f'{f"<a href={nxt!r}>Más guías →</a>" if nxt else ""}</div>')
    grid = "".join(card(p) for p in items) or "<p>Muy pronto publicaremos guías en esta sección.</p>"
    body = (f'<section class="phead" style="--c:{c}"><div class="wrap"><span class="chip" style="--c:{c}">{em} {len(items)} guías</span>'
            f'<h1>{e(h1)}</h1><p>{e(desc)}</p></div></section><div class="wrap"><div class="grid">{grid}</div>{pager}</div>')
    write(path, page(head(title, desc or title, path, jsonld=jsonld), body, key))


def build_category(key: str, name: str, items: list[dict]) -> None:
    base = f"/categoria/{key}/"
    pages = [items[i:i + PER_PAGE] for i in range(0, len(items), PER_PAGE)] or [[]]
    for n, chunk in enumerate(pages, start=1):
        path = base if n == 1 else f"{base}pagina/{n}/"
        prev = None if n == 1 else u(base if n == 2 else f"{base}pagina/{n - 1}/")
        nxt = u(f"{base}pagina/{n + 1}/") if n < len(pages) else None
        build_listing_page(path, f"{name}: trucos y guías paso a paso | {SITE['name']}" + (f" – página {n}" if n > 1 else ""),
                           name, f"Todas nuestras guías de {name.lower()}, explicadas paso a paso y sin tecnicismos.",
                           chunk, prev, nxt, key)


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
<strong>{e(s['owner_legal_name'])}</strong>{f", NIF {e(s['owner_nif'])}" if s.get('owner_nif') else ""}, correo de contacto
<a href="mailto:{e(s['contact_email'])}">{e(s['contact_email'])}</a>.</p>
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
<p>La preferencia de tema claro u oscuro se guarda solo en tu navegador (almacenamiento local) y no se usa para rastrearte.</p>
<p>Puedes cambiar tu elección en cualquier momento borrando las cookies del navegador o desde el enlace de preferencias del aviso.</p>"""),
    }
    pages["/terminos/"] = ("Términos de servicio", f"""<p>Al usar {e(s['name'])} ({e(BASE_URL)}) y sus canales en redes
sociales aceptas estos términos. Si no estás de acuerdo, no utilices el sitio.</p>
<p><strong>Contenido.</strong> Publicamos guías y vídeos informativos sobre tecnología. Se elaboran con ayuda de herramientas de
inteligencia artificial y se revisan con criterios editoriales, pero pueden contener errores o quedar desactualizados. Úsalos bajo tu
responsabilidad y consulta siempre la información oficial del fabricante.</p>
<p><strong>Propiedad intelectual.</strong> Los textos, imágenes y vídeos son de {e(s['name'])} salvo que se indique lo contrario.
Puedes compartir enlaces libremente; no está permitido copiar el contenido completo sin permiso.</p>
<p><strong>Integraciones con plataformas.</strong> Usamos las API oficiales de YouTube y TikTok únicamente para publicar nuestros
propios vídeos en nuestras cuentas. No accedemos a datos de otros usuarios ni los almacenamos.</p>
<p><strong>Enlaces y afiliación.</strong> Algunos enlaces pueden ser de afiliado; se indican como tales.</p>
<p><strong>Cambios y contacto.</strong> Podemos actualizar estos términos. Para cualquier consulta:
<a href="mailto:{e(s['contact_email'])}">{e(s['contact_email'])}</a>. Legislación aplicable: española.</p>""")
    for path, (title, content) in pages.items():
        write(path, page(head(f"{title} | {s['name']}", f"{title} de {s['name']}.", path),
                         f'<div class="wrap page prose"><h1>{title}</h1>{content}</div>'))


def build_feeds(posts: list[dict]) -> None:
    today = dt.date.today().isoformat()
    urls = [(BASE_URL + "/", today, "daily")]
    urls += [(absu(f"/categoria/{k}/"), today, "daily") for k in CATS]
    urls += [(absu(f"/{p['slug']}/"), p.get("updated", p["date"])[:10], "monthly") for p in posts]
    urls += [(absu(p), "2026-01-01", "yearly") for p in ("/sobre-nosotros/", "/contacto/")]
    imgs = {absu(f"/{p['slug']}/"): absu(f"/img/{p['slug']}.jpg") for p in posts}
    sm = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" '
          'xmlns:image="http://www.google.com/schemas/sitemap-image/1.1">']
    sm += [f"<url><loc>{e(l)}</loc><lastmod>{m}</lastmod><changefreq>{c}</changefreq>"
           + (f"<image:image><image:loc>{imgs[l]}</image:loc></image:image>" if l in imgs else "") + "</url>"
           for l, m, c in urls]
    sm.append("</urlset>")
    (PUBLIC_DIR / "sitemap.xml").write_text("\n".join(sm), encoding="utf-8")

    items = "".join(
        f"<item><title>{e(p['title'])}</title><link>{absu(f'/{p['slug']}/')}</link>"
        f"<guid>{absu(f'/{p['slug']}/')}</guid><pubDate>{format_datetime(dt.datetime.fromisoformat(p['date']))}</pubDate>"
        f"<description>{e(p['meta_description'])}</description></item>" for p in posts[:50])
    rss = (f'<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel><title>{e(SITE["name"])}</title>'
           f"<link>{BASE_URL}/</link><description>{e(SITE['tagline'])}</description><language>{SITE['language']}</language>{items}</channel></rss>")
    (PUBLIC_DIR / "feed.xml").write_text(rss, encoding="utf-8")

    (PUBLIC_DIR / "robots.txt").write_text(f"User-agent: *\nAllow: /\n\nSitemap: {BASE_URL}/sitemap.xml\n", encoding="utf-8")
    if ADS.get("client_id"):
        pub = ADS["client_id"].replace("ca-", "")
        (PUBLIC_DIR / "ads.txt").write_text(f"google.com, {pub}, DIRECT, f08c47fec0942fa0\n", encoding="utf-8")
    host = urlparse(BASE_URL).hostname or ""
    if host and not host.endswith("github.io") and host not in ("localhost", "127.0.0.1"):
        (PUBLIC_DIR / "CNAME").write_text(host + "\n", encoding="utf-8")  # dominio propio en GitHub Pages
    manifest = {"name": SITE["name"], "short_name": SITE["name"], "start_url": u("/"), "display": "standalone",
                "background_color": "#0b0c14", "theme_color": "#ff4d6d", "lang": SITE["language"],
                "icons": [{"src": u("/favicon.svg"), "sizes": "any", "type": "image/svg+xml"},
                          {"src": u("/logo-512.png"), "sizes": "512x512", "type": "image/png"}]}
    (PUBLIC_DIR / "manifest.webmanifest").write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")


def indexnow_key() -> str:
    return hashlib.sha256(BASE_URL.encode()).hexdigest()[:32]


SEARCH_JS = """<script>
const norm=s=>s.toLowerCase().normalize('NFD').replace(/[\\u0300-\\u036f]/g,'');
let data=[];const q=document.getElementById('q'),out=document.getElementById('res'),n=document.getElementById('n');
const esc=s=>s.replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
function run(){const v=norm(q.value.trim());if(!v){out.innerHTML='';n.textContent='';return}
const terms=v.split(/\\s+/);const hits=data.map(p=>{const h=norm(p.t+' '+p.k+' '+p.d);let s=0;
for(const t of terms){if(!h.includes(t))return null;s+=norm(p.t).includes(t)?3:1}return[s,p]}).filter(Boolean)
.sort((a,b)=>b[0]-a[0]).slice(0,30);n.textContent=hits.length+' resultado'+(hits.length===1?'':'s');
out.innerHTML=hits.length?hits.map(([,p])=>'<article class="card"><span class="th"><img src="'+p.i+'" alt="" loading="lazy" width="1200" height="630"></span><div class="in"><h3><a href="'+p.u+'">'+esc(p.t)+'</a></h3><p>'+esc(p.d)+'</p></div></article>').join(''):'<p>Sin resultados. Prueba con otras palabras.</p>';
history.replaceState(null,'','?q='+encodeURIComponent(q.value.trim()))}
fetch('SEARCH_URL').then(r=>r.json()).then(d=>{data=d;const p=new URLSearchParams(location.search).get('q');if(p){q.value=p}run()});
q.addEventListener('input',run);
</script>"""


def build_search(posts: list[dict]) -> None:
    index = [{"t": p["title"], "d": p["meta_description"], "u": u(f"/{p['slug']}/"), "i": u(f"/img/t/{p['slug']}.jpg"),
              "k": " ".join(p.get("tags", []) + [p.get("keyword", "")])} for p in posts]
    (PUBLIC_DIR / "search.json").write_text(json.dumps(index, ensure_ascii=False), encoding="utf-8")
    body = ('<section class="phead"><div class="wrap"><h1>¿Qué quieres solucionar?</h1>'
            '<input id="q" type="search" placeholder="Ej.: batería, WhatsApp, wifi…" autofocus aria-label="Buscar">'
            '<p id="n" style="margin-top:12px"></p></div></section>'
            f'<div class="wrap"><div class="grid" id="res"></div></div>{SEARCH_JS.replace("SEARCH_URL", u("/search.json"))}')
    write("/buscar/", page(head(f"Buscar | {SITE['name']}", "Busca entre todas nuestras guías.", "/buscar/",
                                noindex=True), body))


def main() -> None:
    if PUBLIC_DIR.exists():
        shutil.rmtree(PUBLIC_DIR)
    PUBLIC_DIR.mkdir()
    static = ROOT / "static"
    if static.exists():
        shutil.copytree(static, PUBLIC_DIR, dirs_exist_ok=True, ignore=shutil.ignore_patterns("fonts"))

    posts = load_posts()
    for p in posts:
        cover(p, PUBLIC_DIR / "img" / f"{p['slug']}.jpg")
        cover(p, PUBLIC_DIR / "img" / "t" / f"{p['slug']}.jpg", thumb=True)
        build_article(p, posts)
    cover({"slug": "og-default", "title": f"{SITE['name']}: {SITE['tagline']}", "category": next(iter(CATS)),
           "short": {"hook_emoji": "📱"}}, PUBLIC_DIR / "img" / "og-default.jpg")
    build_search(posts)
    key = indexnow_key()
    (PUBLIC_DIR / f"{key}.txt").write_text(key, encoding="utf-8")

    site_ld = [{"@context": "https://schema.org", "@type": "WebSite", "name": SITE["name"], "url": BASE_URL + "/",
                "inLanguage": SITE["language"], "potentialAction": {
                    "@type": "SearchAction", "target": absu("/buscar/") + "?q={search_term_string}",
                    "query-input": "required name=search_term_string"}}, {"@context": "https://schema.org", **org_ld()}]
    build_home(posts, site_ld)
    for k, name in CATS.items():
        build_category(k, name, [p for p in posts if p["category"] == k])
    build_static_pages()
    build_feeds(posts)
    write("/404.html", page(head("Página no encontrada", "Esta página no existe.", "/404.html", noindex=True),
                            f'<section class="hero"><div class="wrap"><h1>Vaya, esta página <span>no existe</span></h1>'
                            f'<p class="lead">Puede que la guía haya cambiado de dirección. Prueba a buscarla:</p>'
                            f'<form class="sbox" action="{u("/buscar/")}"><input name="q" type="search" placeholder="Buscar guías…">'
                            f'<button class="btn">Buscar</button></form></div></section>'))
    cb = ('<div class="wrap page"><h1>Autorización de TikTok</h1><p id="m">Leyendo el código…</p>'
          '<input id="c" readonly style="width:100%;font:15px monospace;padding:12px;border-radius:12px;border:1px solid var(--line);'
          'background:var(--card);color:var(--fg)"><p><button class="btn" id="b" type="button">Copiar código</button></p></div>'
          "<script>var p=new URLSearchParams(location.search),c=p.get('code'),m=document.getElementById('m');"
          "if(c){document.getElementById('c').value=c;m.textContent='Copia este código y pégalo en la terminal:'}"
          "else{m.textContent='No hay código: '+(p.get('error_description')||p.get('error')||'abre el enlace de autorización.')}"
          "document.getElementById('b').onclick=function(){navigator.clipboard.writeText(c||'');this.textContent='¡Copiado!'}</script>")
    write("/tiktok/callback/", page(head("Autorización TikTok", "Página técnica.", "/tiktok/callback/", noindex=True), cb))
    (PUBLIC_DIR / ".nojekyll").write_text("", encoding="utf-8")
    print(f"Web generada: {len(posts)} artículos → {PUBLIC_DIR}")


if __name__ == "__main__":
    main()
