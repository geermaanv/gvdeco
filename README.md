# Déco Porteño

Relevamiento fotográfico de puertas y herrería Art Déco/racionalista en CABA, usado como referencia técnica para fabricación en herrería.

## Arquitectura

```
Telegram (bot @geermaanv_bot: fotos + dirección como descripción)
        ↓
  Code.gs — lee mensajes nuevos, agrupa álbumes en una ficha
        ↓
  OpenRouter — un modelo de visión analiza cada foto (material, estado, motivo, etc.)
        ↓
  Nominatim (OpenStreetMap) — geocodifica la dirección, sin API key
        ↓
  Google Drive — guarda las fotos en la carpeta "Fotos" (junto al Sheet)
        ↓
  Google Sheets — escribe la fila (con los links a las fotos guardadas)
        ↓
  Telegram — el bot te contesta con la ficha creada (o el motivo si falló)
```

Todo corre como **Google Apps Script atado al Sheet**: sin repo desplegado, sin Cloud Console, sin service account, sin secrets de GitHub. Se autoriza una sola vez desde el editor de Apps Script y después corre solo con un trigger de tiempo, cada 10 minutos.

## Por qué esta versión y no las anteriores

Se evaluaron antes: un artifact HTML con OAuth de usuario, un pipeline en Python por cron en GitHub Actions (con Gmail o Telegram, service account de Sheets, y Anthropic o OpenRouter para el análisis), y un flujo 100% manual vía Google Form. Apps Script es el punto medio: nada de infraestructura ni credenciales de Cloud Console que mantener (como el pipeline de Python), pero tampoco requiere tocar nada a mano por cada foto (como el Form). El costo es que el código vive pegado en el editor de Apps Script de la hoja, no en este repo desplegado — `apps-script/Code.gs` es la fuente de verdad para copiar/pegar y mantener versionado, no algo que se ejecute directo desde acá.

## Setup (una sola vez, ~10 minutos)

### 1. Pegar el script

1. Abrí el Sheet ("Déco Porteño", ID `1ImBKT58KqTMcymS36OuX5yblesewgRD3s5wXEeU00HM`).
2. Extensiones → Apps Script.
3. Borrá el contenido de `Code.gs` que viene por default y pegá el contenido de [`apps-script/Code.gs`](apps-script/Code.gs) de este repo.
4. Guardar (ícono de disco o Ctrl/Cmd+S).

### 2. Configurar credenciales

En el editor de Apps Script: ⚙️ Configuración del proyecto → Propiedades del script → **Agregar propiedad del script**, una por una:

| Propiedad | Valor |
|-----------|-------|
| `TELEGRAM_BOT_TOKEN` | Token de `@geermaanv_bot` (el que te dio @BotFather) |
| `TELEGRAM_ALLOWED_CHAT_ID` | Tu chat ID de Telegram (evita que un desconocido le escriba al bot y te llene la hoja) |
| `OPENROUTER_API_KEY` | API key de [openrouter.ai](https://openrouter.ai) |
| `OPENROUTER_MODEL` | Un modelo con soporte de imagen de [openrouter.ai/models](https://openrouter.ai/models) (filtrar por input "image") — no pude confirmar el catálogo actual desde esta sesión, verificalo vos |
| `DRIVE_FOLDER_ID` (opcional) | ID de una carpeta de Drive ya creada por vos, si querés elegir dónde se guardan las fotos (el ID es la parte de la URL después de `/folders/`). Si no la definís, el script usa o crea sola una carpeta llamada **"Fotos"** en la misma carpeta de Drive donde está el Sheet. |

### 3. Autorizar y activar

1. Volvé a la hoja, recargala. Debería aparecer un menú **Déco Porteño** en la barra superior (lo agrega la función `onOpen`).
2. Menú **Déco Porteño → Procesar ahora**. La primera vez Google va a pedir autorización — click en **Revisar permisos**, elegí tu cuenta, **Avanzado → Ir a (nombre del proyecto), no seguro** (es tu propio script, no un tercero), y **Permitir**. Esto es todo lo que reemplaza al Cloud Console/OAuth Client ID de las versiones anteriores.
3. Menú **Déco Porteño → Crear fila de encabezados**.
4. Menú **Déco Porteño → Instalar trigger automático (cada 10 min)**.

Listo — de acá en más es mandarle fotos al bot y esperar.

## Uso

Mandale al bot todas las fotos de una puerta **como álbum** (seleccioná varias imágenes juntas antes de enviar) y escribí la dirección como **descripción** del álbum. Si mandás una sola foto, la descripción de esa foto es la dirección. El bot te contesta en el mismo chat cuando corre el trigger (cada 10 min).

## Columnas del Sheet

`Fecha | Dirección | Barrio | Lat | Long | Material | Estado | Motivo | Año edif. | Color/acabado | Herraje | Ref. herrería | Certeza | Notas | Origen | Fotos`

`Certeza` es un promedio simple de la certeza (alto/medio/bajo) que informa el modelo por campo; si hay varias fotos, cada campo toma el valor con mayor certeza entre todas.

`Fotos` tiene un link por foto (uno por línea dentro de la celda) a los archivos guardados en la carpeta de Drive **"Fotos"** — el script la crea sola, junto al Sheet, la primera vez que corre. Cada archivo se nombra como `Dirección - #foto - fecha_hora.jpg` y queda compartido como "cualquiera con el link puede ver".

## Notas técnicas

- **Confirmación no es instantánea**: el bot contesta cuando corre el trigger (cada 10 min) o cuando ejecutás "Procesar ahora" a mano — no hay respuesta en el momento de mandar las fotos.
- **Control de acceso**: solo se procesan mensajes de `TELEGRAM_ALLOWED_CHAT_ID`; cualquier otro mensaje al bot se ignora.
- **Reprocesamiento**: si falla el análisis de un grupo de fotos, igual se confirma el update de Telegram (no vuelve a aparecer) — mirá **Ver → Registros de ejecución** en Apps Script si un mensaje no generó fila.
- **Alerta de falla total**: si el pipeline entero revienta (credenciales vencidas, cuota agotada, etc.), manda un 🔴 a `TELEGRAM_ALLOWED_CHAT_ID`.
- **Geocoding**: Nominatim tiene un límite de uso de 1 request/segundo y pide un User-Agent identificable (ya seteado en el código). Su política de uso (`operations.osmfoundation.org/policies/nominatim`) desalienta explícitamente el uso automatizado/periódico desde apps, y en la práctica puede bloquear o degradar requests que vienen de rangos de IP compartidos como los de Apps Script — si ves `Barrio`/`Lat`/`Long` vacíos en el Sheet, mirá **Ver → Registros de ejecución**: el código ahora loguea el código HTTP y el body cuando Nominatim no devuelve resultados, para poder confirmar si es bloqueo, rate-limit, o la dirección que no matchea. Si el bloqueo persiste, la alternativa es sumar una API key de un proveedor que sí permita uso automatizado (ej. LocationIQ, capa gratuita) en vez del endpoint público.
- **Calidad del modelo**: si ves errores de parseo en los logs, probá otro modelo en `OPENROUTER_MODEL` — no todos siguen instrucciones de JSON estricto igual de bien.
- No pude probar el flujo completo en vivo (Telegram, OpenRouter, Nominatim) desde la sesión donde se escribió este código — esta sesión de Claude no tiene salida de red hacia esos dominios. Apps Script sí la tiene; probalo con una foto real después del setup y revisá los logs si algo no cierra.
