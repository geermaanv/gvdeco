# Déco Porteño

Relevamiento fotográfico de puertas y herrería Art Déco/racionalista en CABA, usado como referencia técnica para fabricación en herrería.

## Cómo funciona

No hay pipeline ni infraestructura propia: sacar la foto es manual, y cargarla también empieza como una conversación normal con Claude.

1. Sacás la foto de la puerta/elemento (manual, en el momento).
2. En una conversación con Claude, compartís la(s) foto(s) junto con la dirección.
3. Claude analiza las fotos, geocodifica la dirección (Nominatim/OpenStreetMap, sin API key) y manda la ficha directo a un **Google Form** vinculado al Sheet — la fila aparece sola, sin que copies nada a mano.

```
Fotos + dirección (chat con Claude)
        ↓
  Claude analiza las fotos y geocodifica
        ↓
  POST al Google Form (sin auth, sin service account)
        ↓
  Google Sheets — pestaña de respuestas del Form
```

## Por qué este approach y no un pipeline automático

Se evaluaron antes: un artifact HTML con OAuth de Google, un Google Apps Script, y un pipeline en Python corriendo por cron en GitHub Actions (Gmail o Telegram como entrada, Sheets vía service account, Claude Vision u OpenRouter para el análisis). Todos funcionan, pero exigen crear y mantener credenciales (OAuth client, service account, API keys, secrets) para un volumen de uso bajo y esporádico. Un Google Form vinculado al Sheet acepta envíos sin autenticación (es la función para la que existe), así que resuelve la única parte que hacía falta automatizar — cargar la fila — sin ninguna de esas credenciales.

## Sheet

ID `1ImBKT58KqTMcymS36OuX5yblesewgRD3s5wXEeU00HM` ("Déco Porteño"). Las respuestas del Form caen en su propia pestaña dentro del mismo archivo (columna Timestamp + una por cada pregunta del Form, en el orden en que se crearon):

`Fecha | Dirección | Barrio | Lat | Long | Material | Estado | Motivo | Año edif. | Color/acabado | Herraje | Ref. herrería | Certeza | Notas | Origen`

`Certeza` es un promedio simple de la certeza (alto/medio/bajo) que informa el análisis por campo; si hay varias fotos de la misma puerta, cada campo toma el valor con mayor certeza entre todas.

## Si hace falta reconfigurar el Form

El Form ya está creado y vinculado al Sheet. Si se pierde el mapeo de campos (`entry.NNNNNNN` de cada pregunta → nombre de columna) o se recrea el Form, hay que volver a sacarlo: abrir el Form en modo vista previa → menú de 3 puntos → "Obtener enlace con datos precargados" → completar cada campo con su propio nombre → copiar la URL generada. Esos IDs y la URL de envío (`.../formResponse`) no se commitean a este repo — viven solo en la conversación donde se usan, para no exponerlos en texto plano como quedó expuesto un token en `depto-bot`.
