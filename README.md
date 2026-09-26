# TrucoDigital · Autopiloto de contenido

Web de nicho que se escribe sola + fábrica de YouTube Shorts / TikTok. Cada día, GitHub Actions:

1. **Escribe 5 artículos** con Claude (≥900 palabras, FAQ, enlazado interno, guion de Short).
2. **Renderiza 5 vídeos verticales** 1080×1920 (voz Piper TTS + diapositivas + ffmpeg), 100 % gratis.
3. **Los sube** a YouTube Shorts (API oficial) y a la bandeja de TikTok (Content Posting API).
4. **Reconstruye la web** (SEO completo) y la publica en GitHub Pages, incrustando cada Short en su artículo.
5. Cuando se acaban las keywords, **Claude investiga nuevas long-tail** y recarga la cola sola.

```
content/posts/*.json   ← artículos (fuente de verdad, versionados en git)
data/keywords.txt      ← cola de búsquedas por atacar (se autorrellena)
bot/generate.py        ← cerebro: artículos + guiones (Claude API)
bot/video.py           ← Shorts gratis (Piper + Pillow + ffmpeg)
bot/upload_youtube.py  ← subida a YouTube Shorts
bot/upload_tiktok.py   ← subida a TikTok (borrador en tu bandeja)
bot/build.py           ← web estática + sitemap, RSS, schema, ads.txt, legales
bot/pipeline.py        ← orquestador diario
```

## Puesta en marcha (≈45 min, una sola vez)

### 1. Repo y hosting (gratis)
1. Crea un repo **público** en GitHub (en público los minutos de Actions son ilimitados) y sube esta carpeta.
2. Settings › Pages › Source: **GitHub Actions**.
3. Edita `config.json` → `site.url` con `https://TU-USUARIO.github.io/NOMBRE-REPO`, tu email y datos legales (LSSI).
4. **Muy recomendable:** compra un dominio propio (~10 €/año), ponlo en Settings › Pages › Custom domain y en `site.url`. AdSense aprueba mucho mejor dominios propios y `robots.txt` solo funciona en la raíz del dominio.

### 2. Cerebro (Claude)
- Crea una API key en console.anthropic.com y añádela como secret `ANTHROPIC_API_KEY`
  (Settings › Secrets and variables › Actions).
- Coste orientativo: 5 artículos/día con `claude-opus-5` ≈ 0,30–0,60 $/día (~10–18 $/mes).

### 3. YouTube Shorts
1. Google Cloud Console → nuevo proyecto → activa **YouTube Data API v3**.
2. Pantalla de consentimiento OAuth (tipo Externo, añade tu cuenta como usuario de prueba) → Credenciales → ID de cliente OAuth **App de escritorio** → descarga como `bot/client_secret.json`.
3. `pip install -r requirements.txt` y `python bot/get_youtube_token.py` → pega los 3 valores como secrets `YT_CLIENT_ID`, `YT_CLIENT_SECRET`, `YT_REFRESH_TOKEN`.
4. ⚠️ **Publica la app OAuth** (pasa de «Prueba» a «En producción»): en modo prueba el refresh token caduca a los 7 días.
5. ⚠️ Los proyectos de API no verificados suben los vídeos como **privados**. Solicita la auditoría gratuita
   (formulario «YouTube API Services - Audit and Quota Extension»). Mientras tanto, los vídeos quedan en tu
   YouTube Studio listos para pasarlos a públicos con un clic.

### 4. TikTok
1. developers.tiktok.com → crea app → producto **Content Posting API** → scope `video.upload`.
2. Autoriza tu cuenta (flujo OAuth web) y guarda `TIKTOK_CLIENT_KEY`, `TIKTOK_CLIENT_SECRET`, `TIKTOK_REFRESH_TOKEN`.
3. Los vídeos llegan a tu **bandeja de TikTok como borradores**: publícalos con un toque y elige un sonido en
   tendencia (eso multiplica el alcance). Para publicación 100 % directa, solicita la auditoría de TikTok.
- Sin credenciales, los vídeos del día igualmente quedan descargables en la pestaña Actions (artefacto `shorts-N`).

### 5. Monetización
| Fuente | Cuándo | Qué hacer |
|---|---|---|
| **Google AdSense** | Con ~25-30 artículos y tráfico inicial (3-6 semanas) | Solicita en adsense.google.com, pega tu `ca-pub-…` en `config.json › adsense.client_id` (genera `ads.txt` solo). Activa **Anuncios automáticos** y el **CMP de Google** (Privacidad y mensajes) — obligatorio en la UE. |
| **YouTube Partner Program** | 1.000 suscriptores + 10 M de vistas de Shorts en 90 días | Reparto de ingresos de Shorts |
| **TikTok Creator Rewards** | 10.000 seguidores + 100.000 vistas/30 días; vídeos >1 min | Considera versiones >60 s para este programa |
| **Afiliación (Amazon Afiliados)** | Desde ya | Muchas guías (cargadores, fundas, routers wifi…) convierten mejor que AdSense |
| **Search Console** | Día 1 | Verifica el sitio, envía `sitemap.xml`, pon el código en `analytics.google_site_verification` |

## Uso manual
```bash
python bot/generate.py 2       # generar 2 artículos
python bot/video.py            # renderizar vídeos pendientes
python bot/build.py            # construir la web en public/
SITE_URL=http://localhost:8765 python bot/build.py && python -m http.server 8765 -d public
```
En GitHub: Actions › Autopiloto diario › Run workflow (puedes elegir cuántos artículos).

## Reglas del juego (para que dure)
- Google penaliza el **«abuso de contenido a escala»**: páginas en masa hechas para posicionar sin aportar valor.
  El prompt exige guías útiles y verificables, pero **revisa una muestra cada semana** y corrige lo que falle.
  Si quieres revisión previa a publicar, pon `generation.require_review: true` y cambia `draft` a `false` a mano.
- YouTube no monetiza contenido **repetitivo o producido en masa**. Varía hooks y formatos, y graba tú de vez en
  cuando vídeos con tu voz o tu pantalla: es lo que más ayuda a entrar en el YPP.
- Los vídeos declaran voz sintética (`containsSyntheticMedia`) como exige YouTube.
