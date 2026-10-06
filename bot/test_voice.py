"""Diagnóstico de la clave de Google Text-to-Speech: python bot/test_voice.py (la clave no se muestra)."""
import getpass

import requests

key = getpass.getpass("Pega tu clave de Google TTS (no se mostrará): ").strip()
r = requests.post("https://texttospeech.googleapis.com/v1/text:synthesize", params={"key": key}, timeout=30, json={
    "input": {"text": "Hola, esto es una prueba de TrucoDigital."},
    "voice": {"languageCode": "es-ES", "name": "es-ES-Chirp3-HD-Charon"},
    "audioConfig": {"audioEncoding": "LINEAR16"}})
if r.ok:
    print("✓ La clave funciona: Google ha generado el audio correctamente.")
else:
    err = r.json().get("error", {})
    print(f"✗ HTTP {r.status_code}: {err.get('message')}")
    for d in err.get("details", []):
        if d.get("reason") or d.get("metadata"):
            print("   motivo:", d.get("reason"), d.get("metadata", {}))
