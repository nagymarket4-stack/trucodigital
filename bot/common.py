"""Utilidades compartidas: rutas, configuración y acceso a los posts."""
import json
import os
import re
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
if os.environ.get("SITE_URL"):  # p. ej. vista previa local o dominio definido como variable del repo
    CONFIG["site"]["url"] = os.environ["SITE_URL"]
POSTS_DIR = ROOT / "content" / "posts"
DATA_DIR = ROOT / "data"
VIDEOS_DIR = ROOT / "videos"
PUBLIC_DIR = ROOT / "public"
KEYWORDS_FILE = DATA_DIR / "keywords.txt"
USED_KEYWORDS_FILE = DATA_DIR / "keywords_used.txt"


def slugify(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text.lower()).strip("-")
    return text[:80].rstrip("-")


def load_posts(include_drafts: bool = False) -> list[dict]:
    posts = []
    for f in POSTS_DIR.glob("*.json"):
        post = json.loads(f.read_text(encoding="utf-8"))
        if post.get("draft") and not include_drafts:
            continue
        posts.append(post)
    posts.sort(key=lambda p: p["date"], reverse=True)
    return posts


def save_post(post: dict) -> None:
    POSTS_DIR.mkdir(parents=True, exist_ok=True)
    path = POSTS_DIR / f"{post['slug']}.json"
    path.write_text(json.dumps(post, ensure_ascii=False, indent=2), encoding="utf-8")


def read_lines(path: Path) -> list[str]:
    if not path.exists():
        return []
    return [l.strip() for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def write_lines(path: Path, lines: list[str]) -> None:
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
