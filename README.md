# Déco Porteño

Relevamiento fotográfico de puertas y herrería Art Déco/racionalista en CABA. `index.html` es una app estática de una sola página (sin backend) que lee emails de Gmail, analiza las fotos adjuntas con Claude Vision, geocodifica la dirección y escribe una fila en Google Sheets.

## Flujo

1. El usuario manda un email con `gvdeco` en el asunto, fotos adjuntas y la dirección en el cuerpo.
2. La app busca en Gmail: `subject:gvdeco -label:gvdeco-procesado has:attachment`.
3. Por cada email: descarga las fotos, las manda a Claude Vision, geocodifica la dirección con la Geocoding de Google y combina los resultados (si hay varias fotos, se toma por campo el valor con mayor certeza).
4. Agrega una fila a la hoja de Sheets configurada.
5. Marca el email con la etiqueta Gmail `gvdeco-procesado` para no reprocesarlo.

Todas las llamadas (Gmail, Sheets, Geocoding, Anthropic) se hacen directamente desde el navegador — no hay servidor propio.

## Puesta en marcha

### 1. Crear el Client ID de OAuth (Google Cloud Console)

1. https://console.cloud.google.com/apis/credentials → **Create credentials → OAuth client ID**.
2. Tipo de aplicación: **Web application**.
3. En **Authorized JavaScript origins** agregá el origen exacto donde vas a servir `index.html` (por ejemplo `https://tuusuario.github.io` o la URL del Artifact de Claude que publiques). No hace falta *redirect URI* porque se usa el flujo de token implícito de Google Identity Services.
4. Habilitá estas APIs en el proyecto: **Gmail API**, **Google Sheets API**, **Geocoding API** y **Maps JavaScript API** (la geocodificación se hace con `google.maps.Geocoder`, no contra el endpoint REST — el endpoint REST de Geocoding no habilita CORS para llamadas directas desde el navegador, así que se carga la Maps JavaScript API con la misma key).
5. En la pantalla de consentimiento OAuth agregá los scopes:
   - `https://www.googleapis.com/auth/gmail.readonly`
   - `https://www.googleapis.com/auth/gmail.modify`
   - `https://www.googleapis.com/auth/spreadsheets`

### 2. Claves necesarias (se guardan en `localStorage` del navegador, nunca se commitean)

- **Google OAuth Client ID** (paso anterior).
- **Anthropic API key** — se usa para llamar a `POST https://api.anthropic.com/v1/messages` directamente desde el navegador con la cabecera `anthropic-dangerous-direct-browser-access: true`.
- **Google Maps API key** — misma key que habilitaste para Geocoding + Maps JavaScript API.
- **Sheet ID** — ya viene precargado: `1ImBKT58KqTMcymS36OuX5yblesewgRD3s5wXEeU00HM` ("Déco Porteño").

### 3. Uso

1. Abrí `index.html` desde el origen que autorizaste (GitHub Pages, un Artifact publicado, o cualquier hosting estático — **no sirve abrirlo como `file://`**, Google OAuth lo rechaza). Versión publicada como Artifact de Claude (mismo código, sin el wrapper `<html>/<head>/<body>` que exige la plataforma): https://claude.ai/code/artifact/c7933d31-4302-4903-91ea-1444135fcd78 — el origen a agregar en **Authorized JavaScript origins** es `https://claude.ai`.
2. Completá la configuración y **Guardar configuración**.
3. **Conectar con Google** (pop-up de consentimiento).
4. **Crear fila de encabezados** la primera vez (no hace nada si la hoja ya tiene encabezados).
5. **Buscar y procesar emails**.

## Columnas del Sheet

`Fecha | Dirección | Barrio | Lat | Long | Material | Estado | Motivo | Año edif. | Color/acabado | Herraje | Ref. herrería | Certeza | Notas | Email origen`

`Certeza` es un promedio simple de la certeza (alto/medio/bajo) informada por Claude Vision para los campos analizados; cada campo individual también expone su propia certeza en el JSON devuelto por el modelo (visible en la tabla de la app).

## Notas técnicas / riesgos conocidos

- **Exposición de claves**: al ser una app 100% client-side, la Anthropic API key y la Maps API key quedan visibles en el navegador (localStorage + Network tab). Pensada para uso personal en un origen no público. Restringí la Maps API key por HTTP referrer en Cloud Console.
- **Modelo Claude**: el campo "Modelo Claude" viene precargado con `claude-sonnet-4-6` tal como se especificó. Verificá que ese identificador esté disponible para tu API key antes de procesar en volumen — si la API devuelve error de modelo inválido, ajustá el campo en la UI (se guarda en `localStorage`).
- **Dirección**: se toma la primera línea no vacía del cuerpo del email como dirección a geocodificar y como valor de la columna "Dirección".
- **Barrio**: se extrae del resultado de geocodificación (`sublocality_level_1` / `sublocality` / `neighborhood`), no lo informa Claude Vision.
- **Reprocesamiento**: si un email falla (sin fotos, sin dirección, error de red), no se marca como procesado y va a reaparecer en la próxima búsqueda.
