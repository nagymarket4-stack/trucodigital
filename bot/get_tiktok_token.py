"""Autoriza la subida a TikTok (ejecutar UNA vez en tu terminal): python bot/get_tiktok_token.py

1. Pide el Client key y el Client secret de tu app de TikTok for Developers (no se muestran).
2. Te da un enlace: ábrelo, inicia sesión con la cuenta de TikTok del negocio y autoriza.
3. TikTok te lleva a trucodigital.org/tiktok/callback/, que muestra un código: cópialo y pégalo aquí.
4. Guarda TIKTOK_CLIENT_KEY, TIKTOK_CLIENT_SECRET y TIKTOK_REFRESH_TOKEN como secrets del repo.
"""
import getpass
import secrets
import subprocess
from urllib.parse import unquote, urlencode

import requests

from common import CONFIG

REPO = "nagymarket4-stack/trucodigital"
REDIRECT = CONFIG["site"]["url"].rstrip("/") + "/tiktok/callback/"
SCOPES = "user.info.basic,video.upload"


def main() -> None:
    key = getpass.getpass("Client key (no se muestra): ").strip()
    secret = getpass.getpass("Client secret (no se muestra): ").strip()
    state = secrets.token_urlsafe(12)
    url = "https://www.tiktok.com/v2/auth/authorize/?" + urlencode(
        {"client_key": key, "scope": SCOPES, "response_type": "code", "redirect_uri": REDIRECT, "state": state})
    print(f"\n1) Abre este enlace y autoriza con la cuenta de TikTok del negocio:\n\n{url}\n")
    code = unquote(input("2) Pega aquí el código que muestra la página: ").strip())
    r = requests.post("https://open.tiktokapis.com/v2/oauth/token/", timeout=30, data={
        "client_key": key, "client_secret": secret, "code": code,
        "grant_type": "authorization_code", "redirect_uri": REDIRECT})
    data = r.json()
    if "refresh_token" not in data:
        print(f"✗ TikTok respondió: {data.get('error')} – {data.get('error_description')}")
        return
    for name, value in (("TIKTOK_CLIENT_KEY", key), ("TIKTOK_CLIENT_SECRET", secret),
                        ("TIKTOK_REFRESH_TOKEN", data["refresh_token"])):
        subprocess.run(["gh", "secret", "set", name, "-R", REPO], input=value, text=True, check=True)
        print(f"✓ secret {name} guardado en GitHub")
    print(f"Listo. El refresh token caduca en {data.get('refresh_expires_in', 31536000) // 86400} días.")


if __name__ == "__main__":
    main()
