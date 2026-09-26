"""Cambia la web a un dominio propio: python bot/set_domain.py midominio.com

1. Actualiza config.json (site.url) → canonical, sitemap, OG, CNAME e IndexNow usan el dominio nuevo.
2. Configura el dominio en GitHub Pages (requiere `gh` con sesión iniciada) y activa HTTPS cuando esté listo.
3. Imprime los registros DNS que debes crear en tu registrador.
"""
import json
import subprocess
import sys

from common import ROOT

REPO = "nagymarket4-stack/trucodigital"


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 1
    domain = sys.argv[1].lower().removeprefix("https://").removeprefix("http://").strip("/")
    apex = domain.removeprefix("www.")
    cfg_path = ROOT / "config.json"
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    cfg["site"]["url"] = f"https://{domain}"
    cfg_path.write_text(json.dumps(cfg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"✓ config.json → https://{domain}")

    r = subprocess.run(["gh", "api", "-X", "PUT", f"repos/{REPO}/pages", "-f", f"cname={domain}"], capture_output=True, text=True)
    print("✓ GitHub Pages con dominio propio" if r.returncode == 0 else f"! GitHub Pages: {r.stderr.strip()}")

    print(f"""
Crea estos registros DNS en tu registrador (borra antes cualquier A/AAAA de «parking»):

  Tipo   Nombre   Valor
  A      @        185.199.108.153
  A      @        185.199.109.153
  A      @        185.199.110.153
  A      @        185.199.111.153
  AAAA   @        2606:50c0:8000::153
  AAAA   @        2606:50c0:8001::153
  AAAA   @        2606:50c0:8002::153
  AAAA   @        2606:50c0:8003::153
  CNAME  www      nagymarket4-stack.github.io

Cuando el DNS propague (de minutos a unas horas), activa HTTPS con:
  gh api -X PUT repos/{REPO}/pages -F https_enforced=true
Después haz commit y push de config.json para reconstruir la web con {apex}.""")
    return 0


if __name__ == "__main__":
    sys.exit(main())
