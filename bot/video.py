"""Motor de Shorts v2: convierte el guion de cada artículo en un vídeo vertical 1080x1920 listo para
YouTube Shorts / TikTok / Reels. Todo gratis y sin copyright:

- Voz: Piper TTS (open source, local).
- Subtítulos karaoke palabra a palabra (sincronizados por fonemas + energía del audio), con pop.
- Emojis animados (Noto Emoji, Apache 2.0) y maqueta de móvil que recorre la ruta de menús.
- Fondo: vídeo de stock de Pexels (si hay PEXELS_API_KEY) o fondo animado procedural.
- Música lo-fi generada por código + ducking bajo la voz + efectos whoosh/pop.
- 4 plantillas visuales elegidas por artículo para que los vídeos no parezcan clones.
"""
import datetime as dt
import hashlib
import math
import os
import re
import subprocess
import sys
import tempfile
import wave
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import imageio_ffmpeg
import numpy as np
import requests
from PIL import Image, ImageDraw, ImageFilter, ImageFont
from piper import PiperVoice, SynthesisConfig

from common import CONFIG, DATA_DIR, ROOT, VIDEOS_DIR, load_posts, save_post

V = CONFIG["video"]
SITE = CONFIG["site"]
W, H = V["width"], V["height"]
FPS = 30
SR = 44100
GAP = 0.12  # silencio entre frases (ritmo rápido = más retención)
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
VOICES_DIR = DATA_DIR / "voices"
EMOJI_DIR = DATA_DIR / "emoji"
FONTS = ROOT / "static" / "fonts"
RECENT_DAYS = 7  # los vídeos no se guardan en git: se re-renderizan si aún falta subirlos
MAX_PER_RUN = 10
CX = 510  # centro horizontal algo a la izquierda: evita los botones laterales de Shorts/TikTok
TEXT_W = 820

THEMES = [
    {"name": "neon", "bg": [(18, 10, 48), (4, 4, 20)], "blobs": [(120, 40, 255), (0, 200, 255), (255, 0, 140)],
     "hl": (255, 230, 0), "accent": (0, 229, 255), "box": None},
    {"name": "sunset", "bg": [(80, 14, 30), (20, 4, 12)], "blobs": [(255, 90, 40), (255, 0, 90), (255, 190, 0)],
     "hl": (20, 20, 20), "accent": (255, 200, 0), "box": (255, 214, 0)},
    {"name": "mint", "bg": [(4, 48, 48), (2, 14, 20)], "blobs": [(0, 255, 170), (0, 140, 255), (120, 255, 60)],
     "hl": (124, 255, 178), "accent": (124, 255, 178), "box": None},
    {"name": "pop", "bg": [(24, 24, 28), (6, 6, 8)], "blobs": [(255, 59, 92), (80, 80, 255), (255, 160, 0)],
     "hl": (255, 255, 255), "accent": (255, 59, 92), "box": (255, 59, 92)},
]


# ---------------------------------------------------------------- utilidades


@lru_cache(maxsize=64)
def font(name: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONTS / f"{name}.ttf"), size)


def ease_out_back(x: float) -> float:
    x = min(max(x, 0.0), 1.0)
    c1, c3 = 1.70158, 2.70158
    return 1 + c3 * (x - 1) ** 3 + c1 * (x - 1) ** 2


def ease_out(x: float) -> float:
    x = min(max(x, 0.0), 1.0)
    return 1 - (1 - x) ** 3


def seed_of(text: str) -> int:
    return int(hashlib.md5(text.encode()).hexdigest()[:8], 16)


def emoji_image(emoji: str) -> Image.Image | None:
    cps = "_".join(f"{ord(c):x}" for c in emoji if ord(c) not in (0xFE0F, 0x200D))
    if not cps:
        return None
    path = EMOJI_DIR / f"{cps}.png"
    if not path.exists():
        EMOJI_DIR.mkdir(parents=True, exist_ok=True)
        try:
            r = requests.get(f"https://fonts.gstatic.com/s/e/notoemoji/latest/{cps}/512.png", timeout=20)
            if r.status_code != 200 and "_" in cps:  # emojis compuestos: probar con el primer código
                r = requests.get(f"https://fonts.gstatic.com/s/e/notoemoji/latest/{cps.split('_')[0]}/512.png", timeout=20)
            r.raise_for_status()
            path.write_bytes(r.content)
        except requests.RequestException:
            return None
    return Image.open(path).convert("RGBA")


# ---------------------------------------------------------------- voz y tiempos por palabra


@dataclass
class Segment:
    kind: str  # hook | line | cta
    text: str
    emoji: str = ""
    ui_path: list = field(default_factory=list)
    broll: str = ""
    step: int = 0
    audio: np.ndarray | None = None
    words: list = field(default_factory=list)  # (palabra, t0, t1) relativos al segmento
    start: float = 0.0
    dur: float = 0.0
    chunks: list = field(default_factory=list)  # (índices de palabra, t0, t1)
    clip: Path | None = None


def load_voice() -> PiperVoice:
    name = V["piper_voice"]
    model = VOICES_DIR / f"{name}.onnx"
    if not model.exists():
        VOICES_DIR.mkdir(parents=True, exist_ok=True)
        subprocess.run([sys.executable, "-m", "piper.download_voices", "--download-dir", str(VOICES_DIR), name], check=True)
    return PiperVoice.load(str(model))


def _clean_ph(g: str) -> str:
    return re.sub(r"[ˈˌ.,;:!?¡¿\"'…—-]", "", g)


def _place(words: list[str], weights: list[float], t0: float, t1: float) -> list:
    total = sum(weights) or 1
    out, t = [], t0
    for w, wt in zip(words, weights):
        d = (t1 - t0) * wt / total
        out.append((w, t, t + d))
        t += d
    return out


def synth(voice: PiperVoice, text: str) -> tuple[np.ndarray, list]:
    chunks = list(voice.synthesize(text, syn_config=SynthesisConfig(length_scale=V.get("speech_rate", 0.9))))
    sr = chunks[0].sample_rate
    sentences = [s for s in re.split(r"(?<=[.!?…])\s+", text.strip()) if s]
    per_chunk = len(sentences) == len(chunks)
    parts, words, bounds, t = [], [], [], 0.0
    for i, c in enumerate(chunks):
        a = c.audio_float_array.astype(np.float32).reshape(-1)
        dur = len(a) / sr
        env = np.abs(a)
        idx = np.where(env > max(0.015, float(env.max()) * 0.06))[0]
        s0, s1 = (idx[0] / sr, idx[-1] / sr) if len(idx) else (0.0, dur)
        bounds.append((t + s0, t + s1))
        if per_chunk:
            cw = sentences[i].split()
            groups = [g for g in "".join(c.phonemes).split(" ") if _clean_ph(g)]
            weights = [len(_clean_ph(g)) for g in groups] if len(groups) == len(cw) else [len(w) for w in cw]
            words += _place(cw, weights, t + s0, t + s1)
        parts.append(a)
        t += dur
    audio = np.concatenate(parts)
    if not per_chunk:
        ws = text.split()
        words = _place(ws, [len(w) for w in ws], bounds[0][0], bounds[-1][1])
    n_out = int(len(audio) * SR / sr)  # 22,05 kHz → 44,1 kHz
    audio = np.interp(np.linspace(0, len(audio) - 1, n_out), np.arange(len(audio)), audio).astype(np.float32)
    return audio, words


def make_chunks(words: list, dur: float) -> list:
    """Agrupa palabras en bloques de 1-3 palabras estilo CapCut."""
    chunks, cur = [], []
    for i, (w, _, _) in enumerate(words):
        cur.append(i)
        chars = sum(len(words[j][0]) for j in cur)
        if len(cur) >= 3 or chars >= 15 or re.search(r"[.,!?:;…]$", w):
            chunks.append(cur)
            cur = []
    if cur:
        chunks.append(cur)
    out = []
    for k, c in enumerate(chunks):
        t0 = words[c[0]][1]
        t1 = words[chunks[k + 1][0]][1] if k + 1 < len(chunks) else dur
        out.append((c, t0, t1))
    return out


# ---------------------------------------------------------------- audio: música procedural + sfx


def note(n: int) -> float:
    return 440.0 * 2 ** ((n - 69) / 12)


def music_track(total: float, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    bpm = float(rng.choice([82, 88, 92, 96]))
    beat = 60 / bpm
    progs = [[57, 53, 48, 55], [50, 57, 53, 55], [48, 55, 57, 53], [52, 48, 55, 50]]  # tónicas (MIDI)
    prog = progs[int(rng.integers(len(progs)))]
    minor = {57, 50, 52}
    n = int(total * SR) + SR
    out = np.zeros(n, np.float32)
    bar = beat * 4
    for k in range(int(total / (bar * 2)) + 2):  # pads: 2 compases por acorde
        s, e = int(k * bar * 2 * SR), min(n, int((k + 1) * bar * 2 * SR))
        if s >= n:
            break
        root = prog[k % len(prog)]
        chord = [root, root + (3 if root in minor else 4), root + 7, root + 12]
        tt = np.arange(e - s) / SR
        env = np.minimum(1, tt / 0.6) * np.minimum(1, (bar * 2 - tt) / 0.5)
        pad = sum(np.sin(2 * np.pi * note(m) * tt) + 0.3 * np.sin(2 * np.pi * note(m) * 1.003 * tt) for m in chord)
        out[s:e] += 0.05 * pad * env
        for b in range(0, 8, 2):  # bajo en tiempos 1 y 3
            bs = s + int(b * beat * SR)
            be = min(n, bs + int(beat * SR))
            if bs < n:
                tb = np.arange(be - bs) / SR
                out[bs:be] += 0.22 * np.sin(2 * np.pi * note(root - 12) * tb) * np.exp(-tb * 3)
    kick_t = np.arange(int(0.3 * SR)) / SR
    kick = np.sin(2 * np.pi * (50 + 90 * np.exp(-kick_t * 25)) * kick_t) * np.exp(-kick_t * 9)
    noise = rng.standard_normal(int(0.2 * SR)).astype(np.float32)
    snare = np.diff(noise, prepend=0) * np.exp(-np.arange(len(noise)) / SR * 22)
    hn = int(0.05 * SR)
    hat = np.diff(np.diff(noise[:hn], prepend=0), prepend=0) * np.exp(-np.arange(hn) / SR * 90)
    for b in range(int(total / beat) + 1):
        for sample, vol, on, off in ((kick, 0.5, b % 4 in (0, 2), 0), (snare, 0.10, b % 4 in (1, 3), 0),
                                     (hat, 0.05, True, 0), (hat, 0.035, True, 0.5)):
            p = int((b + off) * beat * SR)
            if on and p < n:
                m = min(len(sample), n - p)
                out[p:p + m] += vol * sample[:m]
    out = np.convolve(out, np.ones(6) / 6, mode="same")  # toque lo-fi (pasa-bajos)
    return out[: int(total * SR)] / (np.abs(out).max() + 1e-6)


def whoosh(seed: int) -> np.ndarray:
    n = int(0.32 * SR)
    x = np.diff(np.random.default_rng(seed).standard_normal(n + 1)).astype(np.float32)
    return 0.16 * x * np.sin(np.pi * np.arange(n) / n) ** 2


def pop() -> np.ndarray:
    t = np.arange(int(0.09 * SR)) / SR
    return (0.3 * np.sin(2 * np.pi * (1100 - 3500 * t) * t) * np.exp(-t * 40)).astype(np.float32)


def mix_audio(segs: list[Segment], total: float, seed: int) -> np.ndarray:
    n = int(total * SR) + SR
    voice = np.zeros(n, np.float32)
    sfx = np.zeros(n, np.float32)
    for i, s in enumerate(segs):
        p = int(s.start * SR)
        voice[p:p + len(s.audio)] += s.audio
        for fx, off in ((whoosh(seed + i), -0.12), (pop(), 0.08)):
            q = max(0, p + int(off * SR))
            sfx[q:q + len(fx)] += fx[: n - q]
    music = np.zeros(n, np.float32)
    music[: int(total * SR)] = music_track(total, seed)
    env = np.convolve(np.abs(voice), np.ones(2205) / 2205, mode="same")  # ducking bajo la voz
    duck = 1 - 0.65 * np.clip(env / (env.max() + 1e-6) * 3, 0, 1)
    out = voice + music * V.get("music_volume", 0.14) * duck + sfx
    out = np.tanh(out * 1.2) / np.tanh(1.2)
    return (out / (np.abs(out).max() + 1e-6) * 0.93)[: int(total * SR)]


def write_wav(path: Path, audio: np.ndarray) -> None:
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((audio * 32767).astype(np.int16).tobytes())


# ---------------------------------------------------------------- fondos


def pexels_clip(query: str, used: set, tmp: Path) -> Path | None:
    key = os.environ.get("PEXELS_API_KEY")
    if not key or not query:
        return None
    try:
        r = requests.get("https://api.pexels.com/videos/search", timeout=20, headers={"Authorization": key},
                         params={"query": query, "orientation": "portrait", "size": "medium", "per_page": 8})
        r.raise_for_status()
        for vid in r.json().get("videos", []):
            if vid["id"] in used:
                continue
            files = [f for f in vid["video_files"] if f.get("height") and f.get("width") and f["height"] > f["width"]
                     and 1000 <= f["height"] <= 2200 and f.get("file_type") == "video/mp4"]
            if not files:
                continue
            best = min(files, key=lambda f: abs(f["height"] - 1920))
            out = tmp / f"pexels_{vid['id']}.mp4"
            with requests.get(best["link"], timeout=60, stream=True) as dl:
                dl.raise_for_status()
                with out.open("wb") as fh:
                    for part in dl.iter_content(1 << 20):
                        fh.write(part)
            used.add(vid["id"])
            return out
    except requests.RequestException as err:
        print(f"    (pexels sin clip para '{query}': {err})")
    return None


class ClipReader:
    """Lee fotogramas de un clip ya escalado a WxH vía ffmpeg (en bucle si es corto)."""

    def __init__(self, path: Path, dur: float):
        vf = (f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},fps={FPS},"
              "eq=brightness=-0.10:saturation=1.15:contrast=1.05")
        self.p = subprocess.Popen([FFMPEG, "-loglevel", "error", "-stream_loop", "-1", "-i", str(path),
                                   "-t", f"{dur + 0.5:.2f}", "-vf", vf, "-an", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                                  stdout=subprocess.PIPE)
        self.last = None

    def frame(self) -> Image.Image:
        buf = self.p.stdout.read(W * H * 3)
        if len(buf) == W * H * 3:
            self.last = Image.frombytes("RGB", (W, H), buf)
        return self.last if self.last is not None else Image.new("RGB", (W, H))

    def close(self):
        self.p.stdout.close()
        self.p.kill()


class AnimatedBG:
    """Fondo procedural: degradado + manchas de color en movimiento (calculado a baja resolución)."""

    LW, LH = 216, 384

    def __init__(self, theme: dict, seed: int):
        self.t = theme
        self.params = np.random.default_rng(seed).uniform(0, 2 * np.pi, (3, 4))
        y = np.linspace(0, 1, self.LH)[:, None, None]
        top, bot = np.array(theme["bg"][0], np.float32), np.array(theme["bg"][1], np.float32)
        self.base = (top * (1 - y) + bot * y) * np.ones((1, self.LW, 1), np.float32)
        yy, xx = np.mgrid[0:self.LH, 0:self.LW].astype(np.float32)
        self.xx, self.yy = xx / self.LW, yy / self.LH
        d = np.sqrt((self.xx - 0.5) ** 2 + ((self.yy - 0.5) * 1.2) ** 2)
        self.vig = np.clip(1.15 - d * 0.9, 0.35, 1)[..., None]  # viñeta para legibilidad

    def frame(self, t: float, z: float = 1.0) -> Image.Image:
        img = self.base.copy()
        for k, col in enumerate(self.t["blobs"]):
            a, b, c, d = self.params[k]
            cx = 0.5 + 0.38 * math.sin(t * 0.35 + a) * math.cos(t * 0.21 + b)
            cy = 0.5 + 0.40 * math.sin(t * 0.27 + c)
            r = 0.30 + 0.06 * math.sin(t * 0.5 + d)
            g = np.exp(-(((self.xx - cx) ** 2) / (r * r) + ((self.yy - cy) ** 2) * 0.35 / (r * r)))
            img += g[..., None] * np.array(col, np.float32) * 0.55
        img = Image.fromarray(np.clip(img * self.vig, 0, 255).astype(np.uint8), "RGB")
        cw, ch = self.LW / z, self.LH / z
        box = ((self.LW - cw) / 2, (self.LH - ch) / 2, (self.LW + cw) / 2, (self.LH + ch) / 2)
        return img.resize((W, H), Image.BILINEAR, box=box)


# ---------------------------------------------------------------- capas gráficas


def text_size(d: ImageDraw.ImageDraw, text: str, f) -> tuple[int, int]:
    b = d.textbbox((0, 0), text, font=f)
    return b[2] - b[0], b[3] - b[1]


@lru_cache(maxsize=512)
def caption_img(words: tuple, active: int, size: int, theme_idx: int) -> Image.Image:
    th = THEMES[theme_idx]
    tmp = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    while True:  # si una palabra larga no cabe, reduce el tamaño
        f = font("Poppins-Black", size)
        sizes = [text_size(tmp, w, f) for w in words]
        if max(w for w, _ in sizes) <= TEXT_W - 40 or size <= 48:
            break
        size -= 6
    space = int(size * 0.28)
    lines, cur, cw = [], [], 0
    for i, (w, _) in enumerate(sizes):
        if cur and cw + space + w > TEXT_W:
            lines.append(cur)
            cur, cw = [], 0
        cur.append(i)
        cw += (space if cw else 0) + w
    lines.append(cur)
    lh, pad = int(size * 1.18), 30
    img = Image.new("RGBA", (TEXT_W + pad * 2, lh * len(lines) + pad * 2), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    y = pad
    for line in lines:
        lw = sum(sizes[i][0] for i in line) + space * (len(line) - 1)
        x = (img.width - lw) // 2
        for i in line:
            on = i == active
            fill = th["hl"] if on else (255, 255, 255)
            if on and th["box"]:
                d.rounded_rectangle([x - 14, y - 2, x + sizes[i][0] + 14, y + lh - 12], radius=18, fill=th["box"])
            stroke = 0 if (on and th["box"]) else max(6, size // 11)
            d.text((x, y), words[i], font=f, fill=fill, stroke_width=stroke, stroke_fill=(0, 0, 0))
            x += sizes[i][0] + space
        y += lh
    return img


@lru_cache(maxsize=64)
def pill(text: str, size: int, bg: tuple, fg: tuple) -> Image.Image:
    f = font("Poppins-ExtraBold", size)
    tw, th = text_size(ImageDraw.Draw(Image.new("RGBA", (1, 1))), text, f)
    img = Image.new("RGBA", (tw + size * 2, int(size * 2.1)), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([0, 0, img.width - 1, img.height - 1], radius=img.height // 2, fill=bg)
    d.text((size, (img.height - th) // 2 - size * 0.2), text, font=f, fill=fg)
    return img


PHONE_TOP, ROW_H = 150, 118


def phone_img(items: tuple, active: int, theme_idx: int) -> Image.Image:
    th = THEMES[theme_idx]
    pw = 620
    ph = PHONE_TOP + ROW_H * max(len(items), 3) + 60
    img = Image.new("RGBA", (pw + 40, ph + 50), (0, 0, 0, 0))
    sh = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(sh).rounded_rectangle([20, 30, pw + 20, ph + 30], radius=60, fill=(0, 0, 0, 150))
    img = Image.alpha_composite(img, sh.filter(ImageFilter.GaussianBlur(14)))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([20, 20, pw + 20, ph + 20], radius=60, fill=(245, 245, 247), outline=(30, 30, 34), width=10)
    d.rounded_rectangle([pw // 2 - 50, 40, pw // 2 + 90, 62], radius=11, fill=(30, 30, 34))
    d.text((70, 82), "9:41", font=font("Poppins-SemiBold", 30), fill=(40, 40, 40))
    fs = font("Poppins-SemiBold", 40)
    y = PHONE_TOP
    for i, it in enumerate(items):
        if i > active:
            break
        on = i == active
        if on:
            d.rounded_rectangle([44, y, pw - 4, y + ROW_H - 16], radius=26, fill=th["accent"])
        label = it if len(it) <= 22 else it[:21] + "…"
        d.text((80, y + 22), label, font=fs, fill=(15, 15, 15) if on else (40, 40, 40))
        d.text((pw - 60, y + 16), "›", font=font("Poppins-ExtraBold", 48), fill=(15, 15, 15) if on else (150, 150, 150))
        if not on:
            d.line([80, y + ROW_H - 8, pw - 30, y + ROW_H - 8], fill=(220, 220, 224), width=3)
        y += ROW_H
    return img


# ---------------------------------------------------------------- render


def normalize_script(short: dict) -> list[Segment]:
    segs = [Segment("hook", short["hook"], short.get("hook_emoji") or "😱", [], short.get("hook_broll_query", ""))]
    for i, line in enumerate(short["lines"], start=1):
        if isinstance(line, str):
            line = {"text": line}
        segs.append(Segment("line", line["text"], line.get("emoji", ""), list(line.get("ui_path") or [])[:5],
                            line.get("broll_query", ""), step=i))
    segs.append(Segment("cta", short["cta"], short.get("cta_emoji") or "👉", [], ""))
    return segs


def render(post: dict, voice: PiperVoice) -> Path:
    seed = seed_of(post["slug"])
    ti = seed % len(THEMES)
    th = THEMES[ti]
    segs = normalize_script(post["short"])

    t, kept = 0.15, []
    for s in segs:  # voz + tiempos; recorta pasos si nos pasamos del máximo
        s.audio, s.words = synth(voice, s.text)
        s.dur = len(s.audio) / SR + GAP
        if s.kind == "line" and t + s.dur > V["max_seconds"] - 4:
            continue
        s.start, s.chunks = t, make_chunks(s.words, s.dur)
        t += s.dur
        kept.append(s)
    segs = kept
    n_steps = sum(1 for s in segs if s.kind == "line")
    for k, s in enumerate(x for x in segs if x.kind == "line"):
        s.step = k + 1
    total = t + 0.35

    out = VIDEOS_DIR / f"{post['slug']}.mp4"
    VIDEOS_DIR.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        write_wav(tmp / "audio.wav", mix_audio(segs, total, seed))
        used: set = set()
        for s in segs:
            s.clip = pexels_clip(s.broll, used, tmp)
        anim = AnimatedBG(th, seed)
        emojis = {s.emoji: emoji_image(s.emoji) for s in segs if s.emoji}
        brand = pill(SITE["name"].upper(), 30, th["accent"], (12, 12, 12))
        follow = pill("SÍGUEME PARA MÁS TRUCOS", 44, th["accent"], (12, 12, 12))
        link = pill("Guía completa: enlace en el perfil", 32, (255, 255, 255), (12, 12, 12))
        dark = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        gd = ImageDraw.Draw(dark)
        for y in range(H):  # oscurece el vídeo de stock, más arriba y abajo
            a = 150 * max(0.0, (abs(y / H - 0.5) - 0.1) / 0.4) ** 1.5
            gd.line([(0, y), (W, y)], fill=(0, 0, 0, int(min(a + 60, 200))))

        enc = subprocess.Popen([FFMPEG, "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
                                "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-i", str(tmp / "audio.wav"),
                                "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
                                "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", str(out)],
                               stdin=subprocess.PIPE)
        reader, reader_seg = None, None
        phone_cache: dict = {}
        white = Image.new("RGBA", (W, H), (255, 255, 255, 255))
        for fi in range(int(total * FPS)):
            t = fi / FPS
            si = max([i for i, s in enumerate(segs) if s.start <= t] or [0])
            s = segs[si]
            lt = t - s.start

            # fondo + zoom de impacto al entrar en cada frase
            z = 1 + 0.07 * math.exp(-max(lt, 0) * 7) + 0.03 * (max(lt, 0) / max(s.dur, 0.1))
            if s.clip:
                if reader_seg != si:
                    if reader:
                        reader.close()
                    reader, reader_seg = ClipReader(s.clip, s.dur), si
                bg = reader.frame()
                cw, ch = W / z, H / z
                bg = bg.resize((W, H), Image.BILINEAR, box=((W - cw) / 2, (H - ch) / 2, (W + cw) / 2, (H + ch) / 2))
            else:
                bg = anim.frame(t, z)
            frame = bg.convert("RGBA")
            if s.clip:
                frame = Image.alpha_composite(frame, dark)

            d = ImageDraw.Draw(frame)
            d.rectangle([0, 0, W, 12], fill=(255, 255, 255, 60))
            d.rectangle([0, 0, int(W * t / total), 12], fill=th["accent"])
            frame.alpha_composite(brand, (CX - brand.width // 2, 190))

            if s.kind == "line":
                badge = pill(f"PASO {s.step} DE {n_steps}", 40, (255, 255, 255), (12, 12, 12))
                k = ease_out_back(lt / 0.3)
                if k > 0.05:
                    b = badge.resize((max(1, int(badge.width * k)), max(1, int(badge.height * k))))
                    frame.alpha_composite(b, (CX - b.width // 2, 290 + (badge.height - b.height) // 2))

            if s.ui_path:  # maqueta de móvil recorriendo la ruta de menús
                n = len(s.ui_path)
                active = min(n - 1, int(max(lt, 0) / max(0.1, s.dur * 0.7 / n)))  # llega al final al 70 %
                if (si, active) not in phone_cache:
                    phone_cache[(si, active)] = phone_img(tuple(s.ui_path), active, ti)
                ph = phone_cache[(si, active)]
                y = int(420 + (1 - ease_out(lt / 0.35)) * 500)
                frame.alpha_composite(ph, (CX - ph.width // 2, y))
                ry = y + 20 + PHONE_TOP + active * ROW_H + (ROW_H - 16) // 2
                ph_t = (max(lt, 0) * 1.6) % 1
                rr = 18 + 42 * ph_t
                rx = CX - ph.width // 2 + 20 + 620 - 70
                ImageDraw.Draw(frame).ellipse([rx - rr, ry - rr, rx + rr, ry + rr],
                                              outline=(255, 255, 255, int(255 * (1 - ph_t))), width=8)
            elif emojis.get(s.emoji) is not None:  # emoji con rebote
                size = 380 if s.kind == "hook" else 320
                k = ease_out_back((lt - 0.05) / 0.4)
                if k > 0.02:
                    e = emojis[s.emoji].resize((max(1, int(size * k)), max(1, int(size * k))), Image.BILINEAR)
                    yc = (820 if s.kind == "cta" else 760) + math.sin(t * 2.4) * 16
                    if s.kind == "cta":
                        yc = 640
                    frame.alpha_composite(e, (int(CX - e.width / 2), int(yc - e.height / 2)))

            if s.kind == "cta":
                pulse = 1 + 0.05 * math.sin(lt * 9)
                fb = follow.resize((int(follow.width * pulse), int(follow.height * pulse)))
                frame.alpha_composite(fb, (CX - fb.width // 2, 930 - fb.height // 2))
                frame.alpha_composite(link, (CX - link.width // 2, 1040))

            for idxs, c0, c1 in s.chunks:  # subtítulos karaoke
                if c0 - 0.03 <= lt < c1:
                    active = next((j for j, i in enumerate(idxs) if s.words[i][1] <= lt < s.words[i][2] + 0.05), -1)
                    words = tuple(s.words[i][0].upper() for i in idxs)
                    cap = caption_img(words, active, 104 if s.kind == "hook" else 92, ti)
                    k = 0.82 + 0.18 * ease_out_back((lt - c0) / 0.14)
                    cap = cap.resize((max(1, int(cap.width * k)), max(1, int(cap.height * k))), Image.BILINEAR)
                    cy = 1330 if s.kind != "cta" else 1300
                    frame.alpha_composite(cap, (CX - cap.width // 2, cy - cap.height // 2))
                    break

            if si > 0 and lt < 0.08:  # flash en los cortes
                frame = Image.blend(frame, white, 0.22 * (1 - lt / 0.08))

            enc.stdin.write(frame.convert("RGB").tobytes())
        if reader:
            reader.close()
        enc.stdin.close()
        if enc.wait() != 0:
            raise subprocess.CalledProcessError(enc.returncode, "ffmpeg")
    print(f"  vídeo -> {out.name} ({total:.1f}s, plantilla {th['name']}, "
          f"{'pexels' if any(s.clip for s in segs) else 'fondo animado'})")
    return out


def main() -> None:
    if not V["enabled"]:
        return
    up = CONFIG["upload"]
    recent = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=RECENT_DAYS)
    only = sys.argv[1] if len(sys.argv) > 1 else None

    def needs(p: dict) -> bool:
        if only:
            return p["slug"] == only
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
        except (subprocess.CalledProcessError, OSError, KeyError, ValueError) as err:
            print(f"  ! fallo: {err}")
            continue
        p["video"]["file"] = out.relative_to(ROOT).as_posix()
        save_post(p)


if __name__ == "__main__":
    main()
