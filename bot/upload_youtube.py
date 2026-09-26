"""Sube a YouTube Shorts los vídeos renderizados que aún no se han publicado.

Credenciales (secrets de GitHub): YT_CLIENT_ID, YT_CLIENT_SECRET, YT_REFRESH_TOKEN.
Se obtienen una sola vez con bot/get_youtube_token.py.
Cuota por defecto de la API: 10.000 unidades/día; cada subida cuesta ~1.600 → máx. 6 al día.
"""
import os

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

from common import CONFIG, ROOT, load_posts, save_post

SITE = CONFIG["site"]
MAX_PER_RUN = 6


def client():
    creds = Credentials(
        token=None,
        refresh_token=os.environ["YT_REFRESH_TOKEN"],
        client_id=os.environ["YT_CLIENT_ID"],
        client_secret=os.environ["YT_CLIENT_SECRET"],
        token_uri="https://oauth2.googleapis.com/token",
        scopes=["https://www.googleapis.com/auth/youtube.upload"],
    )
    return build("youtube", "v3", credentials=creds, cache_discovery=False)


def description(p: dict) -> str:
    url = f"{SITE['url'].rstrip('/')}/{p['slug']}/"
    tags = " ".join(f"#{h.replace(' ', '')}" for h in p["short"]["hashtags"])
    points = "\n".join(f"✅ {t}" for t in p["key_takeaways"])
    return f"{p['meta_description']}\n\n{points}\n\n📖 Guía completa paso a paso: {url}\n\n#Shorts {tags}"


def main() -> None:
    if not CONFIG["upload"]["youtube"] or not os.environ.get("YT_REFRESH_TOKEN"):
        print("YouTube desactivado o sin credenciales; se omite")
        return
    yt = client()
    pending = [p for p in load_posts() if p["video"].get("file") and (ROOT / p["video"]["file"]).exists()
               and not p["video"].get("youtube_id")]
    for p in pending[:MAX_PER_RUN]:
        body = {
            "snippet": {
                "title": p["short"]["title"][:95],
                "description": description(p)[:4900],
                "tags": (p["tags"] + p["short"]["hashtags"])[:15],
                "categoryId": "28",  # Ciencia y tecnología
                "defaultLanguage": CONFIG["site"]["language"],
            },
            "status": {
                "privacyStatus": CONFIG["upload"]["youtube_privacy"],
                "selfDeclaredMadeForKids": False,
                "containsSyntheticMedia": True,  # voz sintética: declaración de contenido alterado/sintético
            },
        }
        media = MediaFileUpload(str(ROOT / p["video"]["file"]), mimetype="video/mp4", resumable=True)
        try:
            req = yt.videos().insert(part="snippet,status", body=body, media_body=media)
            resp = None
            while resp is None:
                _, resp = req.next_chunk()
        except HttpError as err:
            print(f"  ! YouTube error en {p['slug']}: {err}")
            if err.resp.status in (403, 429):  # cuota agotada: parar hasta mañana
                break
            continue
        p["video"]["youtube_id"] = resp["id"]
        save_post(p)
        print(f"  YouTube ok: https://youtube.com/shorts/{resp['id']}")


if __name__ == "__main__":
    main()
