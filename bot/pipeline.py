"""Orquestador diario: artículos → vídeos → subidas → web. Cada paso tolera fallos del anterior."""
import subprocess
import sys
from pathlib import Path

BOT = Path(__file__).resolve().parent
STEPS = ["generate.py", "video.py", "upload_youtube.py", "upload_tiktok.py", "build.py"]


def main() -> int:
    failed = []
    for step in STEPS:
        print(f"\n=== {step} ===", flush=True)
        if subprocess.run([sys.executable, str(BOT / step)], cwd=BOT).returncode != 0:
            failed.append(step)
    print(f"\nPasos con fallo: {failed or 'ninguno'}")
    return 1 if "build.py" in failed else 0  # solo es crítico que la web se construya


if __name__ == "__main__":
    sys.exit(main())
