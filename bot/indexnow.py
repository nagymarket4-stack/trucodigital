"""Avisa a los buscadores (Bing, Yandex, Seznam, Naver… vía IndexNow) de las URLs nuevas del día.
Bing alimenta también a DuckDuckGo, Ecosia y la búsqueda de ChatGPT/Copilot."""
import datetime as dt
from urllib.parse import urlparse

import requests

from build import BASE_URL, absu, indexnow_key
from common import load_posts


def main() -> None:
    host = urlparse(BASE_URL).hostname
    if host in ("localhost", "127.0.0.1"):
        return
    since = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=2)
    urls = [absu(f"/{p['slug']}/") for p in load_posts() if dt.datetime.fromisoformat(p.get("updated", p["date"])) > since]
    if not urls:
        print("IndexNow: nada nuevo")
        return
    key = indexnow_key()
    r = requests.post("https://api.indexnow.org/indexnow", timeout=30, json={
        "host": host, "key": key, "keyLocation": absu(f"/{key}.txt"), "urlList": [BASE_URL + "/"] + urls})
    print(f"IndexNow: {len(urls)} URLs → HTTP {r.status_code}")


if __name__ == "__main__":
    main()
