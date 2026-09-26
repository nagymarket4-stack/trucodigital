"""Ejecutar UNA vez en tu PC para obtener el refresh token de YouTube.

1. En Google Cloud Console crea un proyecto, activa "YouTube Data API v3",
   configura la pantalla de consentimiento OAuth y crea un ID de cliente OAuth tipo "App de escritorio".
2. Descarga el JSON como client_secret.json en esta carpeta.
3. python bot/get_youtube_token.py  → inicia sesión con la cuenta del canal.
4. Copia los tres valores que imprime a los secrets del repo de GitHub.
"""
import json
from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow

secret = Path(__file__).with_name("client_secret.json")
flow = InstalledAppFlow.from_client_secrets_file(str(secret), scopes=["https://www.googleapis.com/auth/youtube.upload"])
creds = flow.run_local_server(port=0, access_type="offline", prompt="consent")
cfg = json.loads(secret.read_text())["installed"]
print("\nAñade estos secrets en GitHub (Settings › Secrets and variables › Actions):\n")
print(f"YT_CLIENT_ID={cfg['client_id']}")
print(f"YT_CLIENT_SECRET={cfg['client_secret']}")
print(f"YT_REFRESH_TOKEN={creds.refresh_token}")
