"""Ejecutar UNA vez en tu PC para autorizar la subida a YouTube.

Requisitos: bot/client_secret.json (ID de cliente OAuth tipo «App de escritorio») y `gh` con sesión iniciada.
Abre el navegador, inicias sesión con la cuenta del canal y guarda YT_CLIENT_ID, YT_CLIENT_SECRET y
YT_REFRESH_TOKEN como secrets del repo directamente (no se muestran en pantalla).
"""
import json
import subprocess
from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow

REPO = "nagymarket4-stack/trucodigital"
secret = Path(__file__).with_name("client_secret.json")
flow = InstalledAppFlow.from_client_secrets_file(str(secret), scopes=["https://www.googleapis.com/auth/youtube.upload"])
creds = flow.run_local_server(port=0, access_type="offline", prompt="consent")
cfg = json.loads(secret.read_text())["installed"]
values = {"YT_CLIENT_ID": cfg["client_id"], "YT_CLIENT_SECRET": cfg["client_secret"], "YT_REFRESH_TOKEN": creds.refresh_token}
for name, value in values.items():
    subprocess.run(["gh", "secret", "set", name, "-R", REPO], input=value, text=True, check=True)
    print(f"✓ secret {name} guardado en GitHub")
