"""Convierte el guion de cada artículo en un vídeo vertical 1080x1920 (YouTube Shorts / TikTok).

Todo gratis y local: voz con Piper TTS (open source), diapositivas con Pillow, montaje con ffmpeg
(binario de imageio-ffmpeg, así no hace falta instalar nada en el sistema). Sin música para
evitar reclamaciones de copyright.
"""
import colorsys
import datetime as dt
import hashlib
import subprocess
import sys
import tempfile
import textwrap
import wave
from pathlib import Path

import imageio_ffmpeg
from PIL import Image, ImageDraw, ImageFont
from piper import PiperVoice, SynthesisConfig

from common import CONFIG, DATA_DIR, ROOT, VIDEOS_DIR, load_posts, save_post

V = CONFIG["video"]
SITE = CONFIG["site"]
W, H = V["width"], V["height"]
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
VOICES_DIR = DATA_DIR / "voices"
FONT_CANDIDATES = [
    ROOT / "static" / "fonts" / "font-bold.ttf",
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    Path("C:/Windows/Fonts/arialbd.ttf"),
    Path("/System/Library/Fonts/Supplemental/Arial Bold.ttf"),
]
FONT_PATH = next((str(p) for p in FONT_CANDIDATES if p.exists()), None)
PAUSE_S = 0.28
RECENT_DAYS = 7  # los vídeos no se guardan en git: se re-renderizan si aún falta subirlos
MAX_PER_RUN = 10


def font(size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(FONT_PATH, size) if FONT_PATH else ImageFont.load_default(size)


def load_voice() -> PiperVoice:
    name = V["piper_voice"]
    model = VOICES_DIR / f"{name}.onnx"
    if not model.exists():
        VOICES_DIR.mkdir(parents=True, exist_ok=True)
        subprocess.run([sys.executable, "-m", "piper.download_voices", "--download-dir", str(VOICES_DIR), name], check=True)
    return PiperVoice.load(str(model))


def palette(seed: str) -> tuple[tuple, tuple, tuple]:
    """Colores distintos por vídeo (evita que todos los Shorts parezcan clones)."""
    h = int(hashlib.md5(seed.encode()).hexdigest()[:6], 16) / 0xFFFFFF
    top = tuple(int(c * 255) for c in colorsys.hsv_to_rgb(h, 0.75, 0.35))
    bottom = tuple(int(c * 255) for c in colorsys.hsv_to_rgb((h + 0.12) % 1, 0.85, 0.12))
    accent = tuple(int(c * 255) for c in colorsys.hsv_to_rgb((h + 0.5) % 1, 0.7, 1.0))
    return top, bottom, accent


def gradient(top, bottom) -> Image.Image:
    img = Image.new("RGB", (W, H))
    d = ImageDraw.Draw(img)
    for y in range(H):
        t = y / H
        d.line([(0, y), (W, y)], fill=tuple(int(a + (b - a) * t) for a, b in zip(top, bottom)))
    return img


def draw_centered(d: ImageDraw.ImageDraw, text: str, size: int, y_center: int, fill, width_chars: int) -> None:
    f = font(size)
    lines = textwrap.wrap(text, width=width_chars)
    lh = int(size * 1.22)
    y = y_center - lh * len(lines) // 2
    for line in lines:
        w = d.textlength(line, font=f)
        x = (W - w) / 2
        d.text((x + 4, y + 4), line, font=f, fill=(0, 0, 0))  # sombra para legibilidad
        d.text((x, y), line, font=f, fill=fill)
        y += lh


def make_slide(bg: Image.Image, text: str, accent, idx: int, total: int, kind: str) -> Image.Image:
    img = bg.copy()
    d = ImageDraw.Draw(img)
    # marca arriba
    brand = SITE["name"].upper()
    fb = font(46)
    d.rounded_rectangle([(W - d.textlength(brand, font=fb)) / 2 - 30, 150, (W + d.textlength(brand, font=fb)) / 2 + 30, 230],
                        radius=40, fill=accent)
    d.text(((W - d.textlength(brand, font=fb)) / 2, 160), brand, font=fb, fill=(20, 20, 20))
    if kind == "hook":
        draw_centered(d, text, 96, H // 2 - 60, (255, 255, 255), 16)
    elif kind == "cta":
        draw_centered(d, text, 76, H // 2 - 120, (255, 255, 255), 20)
        draw_centered(d, "Guía completa en la web", 58, H // 2 + 220, accent, 26)
        draw_centered(d, "(enlace en el perfil)", 44, H // 2 + 310, (220, 220, 220), 30)
    else:
        num = f"{idx}"
        fn = font(150)
        d.text(((W - d.textlength(num, font=fn)) / 2, 420), num, font=fn, fill=accent)
        draw_centered(d, text, 80, H // 2 + 40, (255, 255, 255), 19)
    # barra de progreso (zona segura: lejos de los botones de la derecha y del pie)
    pw = int((W - 160) * idx / total)
    d.rounded_rectangle([80, H - 380, W - 80, H - 364], radius=8, fill=(80, 80, 90))
    d.rounded_rectangle([80, H - 380, 80 + max(pw, 16), H - 364], radius=8, fill=accent)
    return img


def tts(voice: PiperVoice, text: str, out: Path) -> float:
    with wave.open(str(out), "wb") as wf:
        voice.synthesize_wav(text, wf, syn_config=SynthesisConfig(length_scale=0.92))
    with wave.open(str(out), "rb") as wf:
        return wf.getnframes() / wf.getframerate()


def concat_wavs(parts: list[Path], out: Path) -> None:
    with wave.open(str(parts[0]), "rb") as first:
        params = first.getparams()
    silence = b"\x00" * int(params.framerate * PAUSE_S) * params.sampwidth * params.nchannels
    with wave.open(str(out), "wb") as o:
        o.setparams(params)
        for p in parts:
            with wave.open(str(p), "rb") as w:
                o.writeframes(w.readframes(w.getnframes()))
            o.writeframes(silence)


def render(post: dict, voice: PiperVoice) -> Path:
    s = post["short"]
    segments = [("hook", s["hook"])] + [("line", l) for l in s["lines"]] + [("cta", s["cta"])]
    top, bottom, accent = palette(post["slug"])
    bg = gradient(top, bottom)
    out = VIDEOS_DIR / f"{post['slug']}.mp4"
    VIDEOS_DIR.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        wavs, concat_lines, total_s = [], [], 0.0
        n_lines = len(segments)
        for i, (kind, text) in enumerate(segments):
            wav = tmp / f"{i:02d}.wav"
            dur = tts(voice, text, wav) + PAUSE_S
            if total_s + dur > V["max_seconds"] and kind == "line":
                continue  # recorta frases si se pasa de duración (Shorts < 60 s)
            total_s += dur
            wavs.append(wav)
            png = tmp / f"{i:02d}.png"
            make_slide(bg, text, accent, i if kind == "line" else (n_lines if kind == "cta" else 0), n_lines, kind).save(png)
            concat_lines += [f"file '{png.as_posix()}'", f"duration {dur:.3f}"]
        concat_lines.append(concat_lines[-2])  # el demuxer concat necesita repetir el último frame
        (tmp / "list.txt").write_text("\n".join(concat_lines), encoding="utf-8")
        concat_wavs(wavs, tmp / "voice.wav")
        subprocess.run([FFMPEG, "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(tmp / "list.txt"),
                        "-i", str(tmp / "voice.wav"), "-vf", f"fps=30,scale={W}:{H},format=yuv420p",
                        "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-c:a", "aac", "-b:a", "160k",
                        "-shortest", "-movflags", "+faststart", str(out)], check=True)
    print(f"  vídeo -> {out.name} ({total_s:.1f}s)")
    return out


def main() -> None:
    if not V["enabled"]:
        return
    up = CONFIG["upload"]
    recent = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=RECENT_DAYS)

    def needs(p: dict) -> bool:
        v = p["video"]
        missing = not v.get("file") or not (ROOT / v["file"]).exists()
        not_uploaded = (up["youtube"] and not v.get("youtube_id")) or (up["tiktok"] and not v.get("tiktok_publish_id"))
        return missing and (not_uploaded or not v.get("file")) and dt.datetime.fromisoformat(p["date"]) > recent

    pending = [p for p in load_posts() if needs(p)][:MAX_PER_RUN]
    if not pending:
        print("Sin vídeos pendientes")
        return
    voice = load_voice()
    for p in pending:
        print(f"Renderizando: {p['slug']}")
        try:
            out = render(p, voice)
        except (subprocess.CalledProcessError, OSError, KeyError) as err:
            print(f"  ! fallo: {err}")
            continue
        p["video"]["file"] = out.relative_to(ROOT).as_posix()
        save_post(p)


if __name__ == "__main__":
    main()
