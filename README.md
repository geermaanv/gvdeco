# Déco Porteño

Relevamiento fotográfico de puertas y herrería Art Déco/racionalista en CABA. Pipeline en Python, mismo patrón que [hayminga-pipeline](https://github.com/geermaanv/hayminga-pipeline): corre por cron en GitHub Actions, sin servidor propio.

## Arquitectura

```
Gmail (asunto "gvdeco" + fotos + dirección en el cuerpo)
        ↓
  src/gmail_reader.py — busca emails nuevos, extrae dirección y fotos
        ↓
  src/processor.py — Claude Vision analiza cada foto (material, estado, motivo, etc.)
        ↓
  src/geocode.py — geocodifica la dirección (lat/long, barrio)
        ↓
  src/sheets.py — escribe la fila en Google Sheets
        ↓
  Gmail — se marca el email con la etiqueta "gvdeco-procesado"
```

Corre cada 15 minutos vía GitHub Actions — gratis.

### Por qué no es igual a hayminga-pipeline en la autenticación

hayminga-pipeline solo necesita escribir en Sheets, así que un **service account** alcanza: se comparte la hoja con su email y listo, sin login de usuario. Acá además hace falta **leer tu Gmail personal**, y eso Google no lo permite con un service account solo (se necesita delegación de dominio de Google Workspace, que no existe en una cuenta @gmail.com común). Por eso Gmail usa un **refresh token de OAuth de usuario** generado una sola vez a mano — corre desatendido en cada ejecución igual que el resto, pero el paso inicial no se puede evitar.

Sheets sigue usando service account, igual que hayminga.

## Setup (una sola vez)

### 1. Google Sheets

El Sheet ya existe: `1ImBKT58KqTMcymS36OuX5yblesewgRD3s5wXEeU00HM` ("Déco Porteño"), vacío. El pipeline crea la fila de encabezados solo, en la primera corrida.

### 2. Service account (para Sheets)

1. [Google Cloud Console](https://console.cloud.google.com) → creá un proyecto (ej. "gvdeco").
2. Activá **Google Sheets API** y **Geocoding API**.
3. Credentials → Create credentials → **Service account** → descargá el JSON de la clave.
4. Compartí el Google Sheet con el email de la service account (`...@...iam.gserviceaccount.com`), permiso Editor.

### 3. OAuth de usuario (para Gmail)

1. En el mismo proyecto de Cloud Console → Credentials → Create credentials → OAuth client ID → tipo **Desktop app**. Descargalo como `client_secret.json`.
2. OAuth consent screen: agregá el scope `https://www.googleapis.com/auth/gmail.modify` y, si la app queda en modo "Testing", agregate como test user con tu propia cuenta de Gmail.
3. En tu máquina (no en GitHub Actions):
   ```bash
   pip install google-auth-oauthlib
   python scripts/get_gmail_refresh_token.py
   ```
   Se abre un navegador para el consentimiento y el script imprime `GMAIL_CLIENT_ID`, `GMAIL_CLIENT_SECRET` y `GMAIL_REFRESH_TOKEN`. Borrá `client_secret.json` después — ya no hace falta.

### 4. API key de Google Maps (Geocoding)

Credentials → Create credentials → **API key**, con **Geocoding API** habilitada. Restringila por API (no hace falta restricción de referrer: la llamada es servidor a servidor).

### 5. API key de Anthropic

[console.anthropic.com](https://console.anthropic.com) → API Keys → Create Key. Verificá que el modelo configurado (`claude-sonnet-4-6` por defecto, variable `CLAUDE_MODEL`) esté disponible para tu cuenta.

### 6. Secrets en GitHub

Repo → Settings → Secrets and variables → Actions → New repository secret:

| Secret | Valor |
|--------|-------|
| `ANTHROPIC_API_KEY` | API key de Anthropic |
| `MAPS_API_KEY` | API key de Geocoding |
| `GOOGLE_SPREADSHEET_ID` | `1ImBKT58KqTMcymS36OuX5yblesewgRD3s5wXEeU00HM` |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | Contenido completo del JSON de la service account |
| `GMAIL_CLIENT_ID` | Del paso 3 |
| `GMAIL_CLIENT_SECRET` | Del paso 3 |
| `GMAIL_REFRESH_TOKEN` | Del paso 3 |

Opcional, en **Variables** (no Secrets) de Actions: `CLAUDE_MODEL` si querés otro modelo distinto del default.

## Correr manualmente

```bash
pip install -r requirements.txt

export ANTHROPIC_API_KEY=...
export MAPS_API_KEY=...
export GOOGLE_SPREADSHEET_ID=1ImBKT58KqTMcymS36OuX5yblesewgRD3s5wXEeU00HM
export GOOGLE_SERVICE_ACCOUNT_JSON='{"type":"service_account",...}'
export GMAIL_CLIENT_ID=...
export GMAIL_CLIENT_SECRET=...
export GMAIL_REFRESH_TOKEN=...

python main.py
```

O desde GitHub: pestaña **Actions** → "Procesar emails Déco Porteño" → **Run workflow**.

## Columnas del Sheet

`Fecha | Dirección | Barrio | Lat | Long | Material | Estado | Motivo | Año edif. | Color/acabado | Herraje | Ref. herrería | Certeza | Notas | Email origen`

`Certeza` es un promedio simple de la certeza (alto/medio/bajo) que informa Claude Vision por campo; si el email tiene varias fotos, cada campo toma el valor con mayor certeza entre todas.

## Notas técnicas

- **Dirección**: se toma la primera línea no vacía del cuerpo del email.
- **Barrio**: viene del resultado de geocodificación (`sublocality_level_1` / `sublocality` / `neighborhood`), no lo informa Claude Vision.
- **Reprocesamiento**: si un email falla (sin fotos, sin dirección, error de red o de la API), no se marca como procesado y se reintenta en la próxima corrida.
- **Modelo Claude**: viene con `claude-sonnet-4-6` por defecto — verificalo contra tu cuenta antes de correr en volumen; ajustalo con la variable de Actions `CLAUDE_MODEL` si hace falta.
