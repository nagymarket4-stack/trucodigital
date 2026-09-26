"""Imagen destacada 1200x630 por artículo (Open Graph, Google Discover, tarjetas y cabecera)."""
import hashlib
import textwrap
from functools import lru_cache
from pathlib import Path

import requests
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from common import CONFIG, DATA_DIR, ROOT

FONTS = ROOT / "static" / "fonts"
EMOJI_DIR = DATA_DIR / "emoji"
IW, IH = 1200, 630
PALETTES = [  # (fondo arriba, fondo abajo, acento) — mismos tonos que las plantillas de vídeo
    ((40, 18, 100), (6, 6, 24), (0, 229, 255)),
    ((120, 20, 40), (24, 6, 14), (255, 200, 0)),
    ((6, 70, 70), (2, 16, 22), (124, 255, 178)),
    ((34, 34, 40), (8, 8, 10), (255, 59, 92)),
]


@lru_cache(maxsize=16)
def font(name: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONTS / f"{name}.ttf"), size)


def emoji(e: str) -> Image.Image | None:
    cps = "_".join(f"{ord(c):x}" for c in e if ord(c) not in (0xFE0F, 0x200D))
    if not cps:
        return None
    path = EMOJI_DIR / f"{cps}.png"
    if not path.exists():
        try:
            r = requests.get(f"https://fonts.gstatic.com/s/e/notoemoji/latest/{cps}/512.png", timeout=20)
            r.raise_for_status()
            EMOJI_DIR.mkdir(parents=True, exist_ok=True)
            path.write_bytes(r.content)
        except requests.RequestException:
            return None
    return Image.open(path).convert("RGBA")


def cover(post: dict, out: Path) -> None:
    seed = int(hashlib.md5(post["slug"].encode()).hexdigest()[:8], 16)
    top, bot, acc = PALETTES[seed % len(PALETTES)]
    img = Image.new("RGB", (IW, IH))
    d = ImageDraw.Draw(img)
    for y in range(IH):
        t = y / IH
        d.line([(0, y), (IW, y)], fill=tuple(int(a + (b - a) * t) for a, b in zip(top, bot)))
    glow = Image.new("RGBA", (IW, IH), (0, 0, 0, 0))
    ImageDraw.Draw(glow).ellipse([760, 80, 1260, 580], fill=acc + (110,))
    img = Image.alpha_composite(img.convert("RGBA"), glow.filter(ImageFilter.GaussianBlur(90)))
    d = ImageDraw.Draw(img)

    cat = CONFIG["categories"].get(post["category"], post["category"]).upper()
    fc = font("Poppins-ExtraBold", 26)
    cw = d.textlength(cat, font=fc)
    d.rounded_rectangle([64, 60, 64 + cw + 44, 112], radius=26, fill=acc)
    d.text((86, 66), cat, font=fc, fill=(12, 12, 12))

    title = post["title"]
    for size, width in ((68, 20), (60, 23), (52, 27), (46, 31)):
        lines = textwrap.wrap(title, width=width)
        if len(lines) <= 4:
            break
    ft = font("Poppins-ExtraBold", size)
    y = 150 + (4 - len(lines)) * size * 0.45
    for line in lines:
        d.text((64, y), line, font=ft, fill=(255, 255, 255), stroke_width=2, stroke_fill=(0, 0, 0))
        y += size * 1.2

    em = emoji(post.get("short", {}).get("hook_emoji") or "📱")
    if em:
        em = em.resize((300, 300), Image.LANCZOS).rotate(-8, resample=Image.BICUBIC, expand=True)
        img.alpha_composite(em, (IW - em.width - 50, (IH - em.height) // 2))

    fb = font("Poppins-ExtraBold", 30)
    d.text((64, IH - 70), CONFIG["site"]["name"], font=fb, fill=acc)
    out.parent.mkdir(parents=True, exist_ok=True)
    img.convert("RGB").save(out, "JPEG", quality=84, optimize=True, progressive=True)
