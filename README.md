# Déco Porteño

Relevamiento fotográfico de puertas y herrería Art Déco/racionalista en CABA. Pipeline en Python, mismo patrón que [hayminga-pipeline](https://github.com/geermaanv/hayminga-pipeline): corre por cron en GitHub Actions, sin servidor propio.

## Arquitectura

```
Telegram (bot @geermaanv_bot: fotos + dirección como descripción)
        ↓
  src/telegram_reader.py — lee mensajes nuevos, agrupa álbumes en una ficha
        ↓
  src/processor.py — un modelo de visión (vía OpenRouter) analiza cada foto (material, estado, motivo, etc.)
        ↓
  src/geocode.py — geocodifica la dirección (lat/long, barrio)
        ↓
  src/sheets.py — escribe la fila en Google Sheets
        ↓
  Telegram — el bot te contesta con la ficha creada (o el motivo si falló)
```

Corre cada 15 minutos vía GitHub Actions — gratis.

### Por qué Telegram en vez de Gmail

Un bot de Telegram no necesita OAuth: alcanza con el token que te da @BotFather. Además, Telegram lleva registro de qué mensajes ya confirmaste leer (`offset` en `getUpdates`) — no hace falta ningún label ni archivo propio para saber qué está procesado, como sí hacía falta con Gmail. Sheets sigue usando **service account**, igual que hayminga.

**Importante — control de acceso**: cualquiera que le escriba a `@geermaanv_bot` puede mandar fotos si no se restringe. El pipeline sólo procesa mensajes de tu `TELEGRAM_ALLOWED_CHAT_ID` (ver paso 2); todo lo demás se ignora.

## Uso

Mandale al bot todas las fotos de una puerta **como álbum** (seleccioná varias imágenes juntas antes de enviar) y escribí la dirección como **descripción** del álbum. Si mandás una sola foto, la descripción de esa foto es la dirección. El bot te contesta en el mismo chat cuando la próxima corrida (cada 15 min, o manual) la procesa.

## Setup (una sola vez)

### 1. Google Sheets + service account (para escribir)

1. El Sheet ya existe: `1ImBKT58KqTMcymS36OuX5yblesewgRD3s5wXEeU00HM` ("Déco Porteño"), vacío. El pipeline crea la fila de encabezados solo.
2. [Google Cloud Console](https://console.cloud.google.com) → creá un proyecto → activá **Google Sheets API** y **Geocoding API**.
3. Credentials → Create credentials → **Service account** → descargá el JSON de la clave.
4. Compartí el Sheet con el email de la service account (`...@...iam.gserviceaccount.com`), permiso Editor.

### 2. Telegram

Ya tenés el bot creado (`@geermaanv_bot`). Falta:

1. **Chat ID permitido**: en un chat privado el `chat_id` de Telegram coincide con tu `user_id` y es el mismo sin importar con qué bot hables — si usás otro bot tuyo (ej. depto-bot) ya tenés ese número. Confirmalo igual mandándole cualquier mensaje al bot y abriendo en el navegador:
   `https://api.telegram.org/bot<TU_TOKEN>/getUpdates`
   copiando el valor de `message.chat.id`. Ese es `TELEGRAM_ALLOWED_CHAT_ID`.
2. Guardá el token del bot (`TELEGRAM_BOT_TOKEN`) — es el que te dio @BotFather al crearlo, nunca lo compartas en texto plano fuera de los secrets de GitHub.

### 3. API key de Google Maps (Geocoding)

Cloud Console → Credentials → Create credentials → **API key**, con **Geocoding API** habilitada. No hace falta restricción de referrer: la llamada es servidor a servidor.

### 4. OpenRouter (en vez de Anthropic directo)

1. [openrouter.ai](https://openrouter.ai) → Keys → **Create Key**.
2. En [openrouter.ai/models](https://openrouter.ai/models), filtrá por input **image** y elegí un modelo de visión. No pude chequear el catálogo actual esta sesión (el dominio está bloqueado acá), así que confirmá vos disponibilidad/precio antes de fijarlo — ejemplos históricos con soporte de imagen: `google/gemini-2.5-flash`, `anthropic/claude-sonnet-4.5`, `qwen/qwen2.5-vl-72b-instruct`.
3. Si vas a reusar la key de OpenRouter que tenías en `depto-bot/tutor_runner.py` (`OPENROUTER_API_KEY = "sk-or-v1-..."`), **rotala primero** en openrouter.ai/keys — quedó expuesta en texto plano en ese repo.

### 5. Secrets en GitHub

Repo → Settings → Secrets and variables → Actions:

**Secrets** (New repository secret):

| Secret | Valor |
|--------|-------|
| `OPENROUTER_API_KEY` | API key de OpenRouter |
| `MAPS_API_KEY` | API key de Geocoding |
| `GOOGLE_SPREADSHEET_ID` | `1ImBKT58KqTMcymS36OuX5yblesewgRD3s5wXEeU00HM` |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | Contenido completo del JSON de la service account |
| `TELEGRAM_BOT_TOKEN` | Token de `@geermaanv_bot` |
| `TELEGRAM_ALLOWED_CHAT_ID` | Tu chat ID (paso 2) |

**Variables** (New repository variable) — no es secreto, pero es obligatorio, no tiene default:

| Variable | Valor |
|----------|-------|
| `OPENROUTER_MODEL` | El slug del modelo elegido en el paso 4, ej. `google/gemini-2.5-flash` |

## Correr manualmente

```bash
pip install -r requirements.txt

export OPENROUTER_API_KEY=...
export OPENROUTER_MODEL=google/gemini-2.5-flash
export MAPS_API_KEY=...
export GOOGLE_SPREADSHEET_ID=1ImBKT58KqTMcymS36OuX5yblesewgRD3s5wXEeU00HM
export GOOGLE_SERVICE_ACCOUNT_JSON='{"type":"service_account",...}'
export TELEGRAM_BOT_TOKEN=...
export TELEGRAM_ALLOWED_CHAT_ID=...

python main.py
```

O desde GitHub: pestaña **Actions** → "Procesar fotos Déco Porteño" → **Run workflow**.

## Columnas del Sheet

`Fecha | Dirección | Barrio | Lat | Long | Material | Estado | Motivo | Año edif. | Color/acabado | Herraje | Ref. herrería | Certeza | Notas | Origen (Telegram)`

`Certeza` es un promedio simple de la certeza (alto/medio/bajo) que informa el modelo por campo; si hay varias fotos, cada campo toma el valor con mayor certeza entre todas.

## Notas técnicas

- **Fotos vía "foto" de Telegram** (no como archivo/documento): Telegram las recomprime a JPEG, suficiente para el análisis pero no es la imagen original sin comprimir.
- **Confirmación no es instantánea**: el bot contesta recién cuando corre el pipeline (cada 15 min, o al disparar el workflow a mano) — no hay respuesta en el momento de mandar las fotos.
- **Barrio**: viene del resultado de geocodificación (`sublocality_level_1` / `sublocality` / `neighborhood`), no lo informa el modelo de visión.
- **Reprocesamiento**: si falla el análisis de un grupo de fotos, igual se confirma el update de Telegram (no vuelve a aparecer) — revisá el log del run de Actions si un mensaje no generó fila.
- **Alerta de falla total**: si el pipeline entero revienta (credenciales vencidas, etc.), manda un mensaje 🔴 a `TELEGRAM_ALLOWED_CHAT_ID` antes de salir con error, para enterarte sin mirar los logs de Actions.
- **Calidad del modelo**: no todos los modelos de OpenRouter siguen instrucciones de JSON estricto igual de bien — si ves errores de parseo en los logs (`[processor] Error JSON`), probá con otro modelo en `OPENROUTER_MODEL`.
