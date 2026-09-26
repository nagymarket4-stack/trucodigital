"""Genera la identidad visual de TrucoDigital en brand/ (ejecutar: python brand/make_brand.py)."""
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parent
FONTS = ROOT.parent / "static" / "fonts"
PINK, VIOLET, YELLOW = (255, 77, 109), (124, 92, 255), (255, 214, 10)
DARK = (11, 12, 20)


def font(name, size):
    return ImageFont.truetype(str(FONTS / f"{name}.ttf"), size)


def gradient(w, h, c1, c2, diagonal=True):
    """Degradado lineal (diagonal por defecto) de c1 a c2."""
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    t = (xx / w + yy / h) / 2 if diagonal else xx / w
    t = t[..., None]
    arr = np.array(c1, np.float32) * (1 - t) + np.array(c2, np.float32) * t
    return Image.fromarray(arr.astype(np.uint8), "RGB")


def bolt(d, cx, cy, s, fill):
    """Rayo estilizado centrado en (cx, cy), tamaño s."""
    pts = [(0.15, -0.5), (-0.28, 0.08), (-0.02, 0.08), (-0.15, 0.5), (0.28, -0.08), (0.02, -0.08)]
    d.polygon([(cx + x * s, cy + y * s) for x, y in pts], fill=fill)


def icon(size=1024, radius_ratio=0.24, shadow=False):
    """Icono: squircle con degradado, «T» blanca y rayo amarillo."""
    ss = 4  # supermuestreo para bordes suaves
    S = size * ss
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    grad = gradient(S, S, PINK, VIOLET).convert("RGBA")
    mask = Image.new("L", (S, S), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, S - 1, S - 1], radius=int(S * radius_ratio), fill=255)
    img.paste(grad, (0, 0), mask)
    # brillo superior sutil
    gloss = Image.new("L", (S, S), 0)
    ImageDraw.Draw(gloss).ellipse([-S * 0.3, -S * 0.8, S * 1.3, S * 0.42], fill=28)
    gloss = Image.composite(gloss, Image.new("L", (S, S), 0), mask)
    img = Image.composite(Image.new("RGBA", (S, S), (255, 255, 255, 255)), img, gloss)
    d = ImageDraw.Draw(img)
    f = font("Poppins-ExtraBold", int(S * 0.74))
    b = d.textbbox((0, 0), "T", font=f)
    tw, th = b[2] - b[0], b[3] - b[1]
    x, y = (S - tw) / 2 - b[0] - S * 0.03, (S - th) / 2 - b[1] + S * 0.02
    sh = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    ImageDraw.Draw(sh).text((x, y + S * 0.025), "T", font=f, fill=(60, 20, 90, 120))
    img = Image.alpha_composite(img, sh.filter(ImageFilter.GaussianBlur(S * 0.02)))  # sombra difusa
    d = ImageDraw.Draw(img)
    d.text((x, y), "T", font=f, fill=(255, 255, 255, 255))
    bolt(d, S * 0.74, S * 0.29, S * 0.30, YELLOW)
    out = img.resize((size, size), Image.LANCZOS)
    if shadow:
        pad = int(size * 0.12)
        canvas = Image.new("RGBA", (size + pad * 2, size + pad * 2), (0, 0, 0, 0))
        sh = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
        ImageDraw.Draw(sh).rounded_rectangle([pad, pad + pad // 3, pad + size, pad + size + pad // 3],
                                             radius=int(size * radius_ratio), fill=(124, 92, 255, 110))
        canvas = Image.alpha_composite(canvas, sh.filter(ImageFilter.GaussianBlur(pad // 2)))
        canvas.alpha_composite(out, (pad, pad))
        return canvas
    return out


def wordmark(height=200, dark_bg=False):
    """Logo horizontal: icono + «Truco» + «Digital» con degradado."""
    ic = icon(height)
    f = font("Poppins-ExtraBold", int(height * 0.62))
    tmp = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    b1 = tmp.textbbox((0, 0), "Truco", font=f)
    b2 = tmp.textbbox((0, 0), "Digital", font=f)
    gap = int(height * 0.22)
    w = height + gap + (b1[2] - b1[0]) + (b2[2] - b2[0]) + int(height * 0.1)
    img = Image.new("RGBA", (w, height), (0, 0, 0, 0))
    img.alpha_composite(ic, (0, 0))
    d = ImageDraw.Draw(img)
    ty = (height - (b1[3] - b1[1])) / 2 - b1[1]
    x = height + gap
    d.text((x - b1[0], ty), "Truco", font=f, fill=(255, 255, 255) if dark_bg else (15, 18, 34))
    x2 = x + (b1[2] - b1[0]) + int(height * 0.02)
    tw = b2[2] - b2[0]
    m = Image.new("L", (tw + 20, height), 0)
    ImageDraw.Draw(m).text((-b2[0], ty), "Digital", font=f, fill=255)
    g = gradient(tw + 20, height, PINK, VIOLET, diagonal=False).convert("RGBA")
    img.paste(g, (x2, 0), m)
    return img


def banner():
    """Banner de YouTube 2560x1440; todo lo importante en la zona segura central 1546x423."""
    W, H = 2560, 1440
    img = gradient(W, H, (18, 10, 48), DARK).convert("RGBA")
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gd.ellipse([300, 250, 1300, 1050], fill=PINK + (90,))
    gd.ellipse([1300, 300, 2300, 1150], fill=VIOLET + (110,))
    img = Image.alpha_composite(img, glow.filter(ImageFilter.GaussianBlur(160)))
    wm = wordmark(170, dark_bg=True)
    img.alpha_composite(wm, ((W - wm.width) // 2, 560))
    d = ImageDraw.Draw(img)
    f = font("Poppins-SemiBold", 54)
    t = "Trucos de móvil, WhatsApp, apps e IA en 30 segundos"
    tw = d.textlength(t, font=f)
    d.text(((W - tw) / 2, 760), t, font=f, fill=(225, 228, 255))
    pill = "⚡ Un truco nuevo cada día · trucodigital.org"
    pill = pill.replace("⚡ ", "")
    fp = font("Poppins-ExtraBold", 40)
    pw = d.textlength(pill, font=fp)
    x0 = (W - pw) / 2 - 40
    d.rounded_rectangle([x0 - 50, 850, x0 + pw + 80, 930], radius=40, fill=YELLOW)
    bolt(d, x0 - 8, 890, 52, (15, 18, 34))
    d.text((x0 + 40, 862), pill, font=fp, fill=(15, 18, 34))
    return img.convert("RGB")


def main():
    out = ROOT
    icon(1024).save(out / "logo-icono-1024.png")
    icon(800).save(out / "avatar-800.png")  # YouTube / TikTok (se recorta en círculo: el icono cabe entero)
    icon(120).save(out / "google-oauth-120.png")
    icon(512, shadow=True).save(out / "logo-icono-sombra.png")
    wordmark(240).save(out / "logo-horizontal.png")
    wordmark(240, dark_bg=True).save(out / "logo-horizontal-fondo-oscuro.png")
    wm = Image.new("RGBA", (150, 150), (0, 0, 0, 0))
    wm.alpha_composite(icon(150, radius_ratio=0.5))
    wm.save(out / "youtube-marca-agua-150.png")
    banner().save(out / "youtube-banner-2560x1440.jpg", quality=92)
    # avatar circular de vista previa
    av = icon(800)
    circ = Image.new("L", av.size, 0)
    ImageDraw.Draw(circ).ellipse([0, 0, 799, 799], fill=255)
    prev = Image.new("RGBA", av.size, (0, 0, 0, 0))
    prev.paste(av, (0, 0), circ)
    prev.save(out / "vista-previa-avatar-circular.png")
    print("Marca generada en", out)


if __name__ == "__main__":
    main()
