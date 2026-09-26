"""Envía los vídeos a TikTok con la Content Posting API oficial.

Modo "inbox" (scope video.upload): el vídeo llega a tu bandeja de TikTok como borrador y lo
publicas con un toque desde la app (ahí eliges sonido en tendencia, que dispara el alcance).
La publicación 100 % directa (video.publish) exige que TikTok audite tu app; hasta entonces
solo permite vídeos privados.

Secrets: TIKTOK_CLIENT_KEY, TIKTOK_CLIENT_SECRET, TIKTOK_REFRESH_TOKEN.
"""
import os
from pathlib import Path

import requests

from common import CONFIG, ROOT, load_posts, save_post

API = "https://open.tiktokapis.com/v2"
CHUNK = 10 * 1024 * 1024
MAX_PER_RUN = 5


def access_token() -> str:
    r = requests.post(f"{API}/oauth/token/", data={
        "client_key": os.environ["TIKTOK_CLIENT_KEY"],
        "client_secret": os.environ["TIKTOK_CLIENT_SECRET"],
        "grant_type": "refresh_token",
        "refresh_token": os.environ["TIKTOK_REFRESH_TOKEN"],
    }, timeout=30)
    r.raise_for_status()
    return r.json()["access_token"]  # el refresh token dura 365 días: renuévalo una vez al año


def upload(token: str, path: Path) -> str:
    size = path.stat().st_size
    chunk = size if size < CHUNK else CHUNK
    total = max(1, size // chunk) if size >= CHUNK else 1
    r = requests.post(f"{API}/post/publish/inbox/video/init/", timeout=30,
                      headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json; charset=UTF-8"},
                      json={"source_info": {"source": "FILE_UPLOAD", "video_size": size,
                                            "chunk_size": chunk, "total_chunk_count": total}})
    r.raise_for_status()
    data = r.json()["data"]
    with path.open("rb") as f:
        for i in range(total):
            start = i * chunk
            end = size - 1 if i == total - 1 else start + chunk - 1  # el último trozo absorbe el resto
            f.seek(start)
            blob = f.read(end - start + 1)
            put = requests.put(data["upload_url"], data=blob, timeout=300, headers={
                "Content-Type": "video/mp4", "Content-Length": str(len(blob)),
                "Content-Range": f"bytes {start}-{end}/{size}"})
            put.raise_for_status()
    return data["publish_id"]


def main() -> None:
    if not CONFIG["upload"]["tiktok"] or not os.environ.get("TIKTOK_REFRESH_TOKEN"):
        print("TikTok desactivado o sin credenciales; se omite")
        return
    token = access_token()
    pending = [p for p in load_posts() if p["video"].get("file") and (ROOT / p["video"]["file"]).exists()
               and not p["video"].get("tiktok_publish_id")]
    for p in pending[:MAX_PER_RUN]:
        try:
            pid = upload(token, ROOT / p["video"]["file"])
        except requests.HTTPError as err:
            print(f"  ! TikTok error en {p['slug']}: {err} {err.response.text[:300]}")
            continue
        p["video"]["tiktok_publish_id"] = pid
        save_post(p)
        print(f"  TikTok ok (borrador en tu bandeja): {p['slug']}")


if __name__ == "__main__":
    main()
