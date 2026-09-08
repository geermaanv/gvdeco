/**
 * Déco Porteño — relevamiento de puertas y herrería Art Déco de CABA.
 * Google Apps Script atado a la hoja "Déco Porteño": sin Cloud Console,
 * sin service account, sin secrets de GitHub. Se autoriza una sola vez
 * desde este editor y corre solo con un trigger de tiempo.
 *
 * Flujo: Telegram (bot @geermaanv_bot, fotos + dirección como descripción)
 *   → OpenRouter (visión) → Nominatim (geocoding, sin API key) → Sheet
 *   → el bot te contesta en el chat con la ficha creada.
 *
 * Configuración: Extensiones → Apps Script → ⚙️ Configuración del proyecto
 * → Propiedades del script → agregar:
 *   TELEGRAM_BOT_TOKEN, TELEGRAM_ALLOWED_CHAT_ID, OPENROUTER_API_KEY, OPENROUTER_MODEL
 */

var HEADER_ROW = ["Timestamp", "Fecha", "Dirección", "Barrio", "Lat", "Long", "Material", "Estado",
  "Motivo", "Año edif.", "Color/acabado", "Herraje", "Ref. herrería", "Certeza", "Notas", "Origen"];

var CERT_RANK = { alto: 3, medio: 2, bajo: 1 };

var VISION_PROMPT = "Analizá esta imagen de una puerta o elemento arquitectónico Art Déco en Buenos Aires. " +
  "Completá los siguientes campos con el valor más probable y un nivel de certeza (alto/medio/bajo): " +
  "Material, Estado, Motivo, Año estimado del edificio, Color/acabado, Herraje, Notas técnicas relevantes " +
  "para herrería. Respondé solo en JSON.\n\n" +
  "Además evaluá si el elemento sirve como referencia técnica para fabricación de herrería " +
  "(Ref. herrería: sí/no). Devolvé EXCLUSIVAMENTE un objeto JSON, sin texto adicional ni bloques de código, " +
  "con esta forma exacta:\n" +
  '{"material":{"valor":"hierro forjado|chapa doblada|aluminio|madera+hierro|bronce","certeza":"alto|medio|bajo"},' +
  '"estado":{"valor":"original|restaurado|deteriorado|modificado","certeza":"alto|medio|bajo"},' +
  '"motivo":{"valor":"bandas horiz.|geométrico|mixto|floral|sin ornamento","certeza":"alto|medio|bajo"},' +
  '"anio_edificio":{"valor":"<año o década estimada>","certeza":"alto|medio|bajo"},' +
  '"color_acabado":{"valor":"negro|crema|bronce|grafito|oxidado natural","certeza":"alto|medio|bajo"},' +
  '"herraje":{"valor":"manija circular|barra horiz.|tirador vertical|sin herraje visible","certeza":"alto|medio|bajo"},' +
  '"ref_herreria":{"valor":"sí|no","certeza":"alto|medio|bajo"},' +
  '"notas":"<notas técnicas breves>"}';

// ---- menú ----

function onOpen() {
  SpreadsheetApp.getUi()
    .createMenu("Déco Porteño")
    .addItem("Procesar ahora", "run")
    .addItem("Crear fila de encabezados", "ensureHeaderRowMenu")
    .addSeparator()
    .addItem("Instalar trigger automático (cada 10 min)", "installTrigger")
    .addItem("Quitar trigger automático", "removeTrigger")
    .addToUi();
}

function ensureHeaderRowMenu() {
  ensureHeaderRow(getSheet());
  SpreadsheetApp.getUi().alert("Listo.");
}

function installTrigger() {
  removeTrigger();
  ScriptApp.newTrigger("run").timeBased().everyMinutes(10).create();
  SpreadsheetApp.getUi().alert("Trigger instalado: va a correr cada 10 minutos.");
}

function removeTrigger() {
  ScriptApp.getProjectTriggers().forEach(function (t) {
    if (t.getHandlerFunction() === "run") ScriptApp.deleteTrigger(t);
  });
}

// ---- entrypoint con heartbeat de falla ----

function run() {
  var lock = LockService.getScriptLock();
  if (!lock.tryLock(5000)) {
    Logger.log("Ya hay otra ejecución en curso, se omite esta (evita procesar el mismo mensaje dos veces).");
    return;
  }
  try {
    processAll();
  } catch (e) {
    Logger.log("Error fatal: " + e.message);
    try {
      var cfg = getConfig();
      sendMessage(cfg, cfg.allowedChatId, "🔴 El pipeline de Déco Porteño falló: " + e.message);
    } catch (e2) {
      Logger.log("No se pudo mandar la alerta de falla: " + e2.message);
    }
  } finally {
    lock.releaseLock();
  }
}

// ---- configuración ----

function getConfig() {
  var p = PropertiesService.getScriptProperties();
  var telegramToken = p.getProperty("TELEGRAM_BOT_TOKEN");
  var allowedChatId = p.getProperty("TELEGRAM_ALLOWED_CHAT_ID");
  var openrouterKey = p.getProperty("OPENROUTER_API_KEY");
  var openrouterModel = p.getProperty("OPENROUTER_MODEL");
  if (!telegramToken || !allowedChatId || !openrouterKey || !openrouterModel) {
    throw new Error("Faltan Propiedades del script: TELEGRAM_BOT_TOKEN, TELEGRAM_ALLOWED_CHAT_ID, OPENROUTER_API_KEY, OPENROUTER_MODEL");
  }
  return {
    telegramToken: telegramToken,
    allowedChatId: String(allowedChatId),
    openrouterKey: openrouterKey,
    openrouterModel: openrouterModel
  };
}

function getSheet() {
  return SpreadsheetApp.getActiveSpreadsheet().getSheets()[0];
}

function ensureHeaderRow(sheet) {
  var first = sheet.getRange(1, 1, 1, 1).getValue();
  if (!first) sheet.getRange(1, 1, 1, HEADER_ROW.length).setValues([HEADER_ROW]);
}

// ---- pipeline principal ----

function processAll() {
  var cfg = getConfig();
  var sheet = getSheet();
  ensureHeaderRow(sheet);

  var fetched = fetchNewGroups(cfg);
  if (!fetched.groups.length) {
    Logger.log("Sin mensajes nuevos.");
    return;
  }

  fetched.groups.forEach(function (group) {
    if (!group.address) {
      Logger.log("chat " + group.chatId + ": sin dirección, se omite");
      sendMessage(cfg, group.chatId, "⚠️ No encontré la dirección — mandá las fotos con la dirección como descripción (caption) del mensaje o álbum.");
      return;
    }

    var analyses = [];
    group.fileIds.forEach(function (fileId) {
      var blob = downloadPhoto(cfg, fileId);
      var result = analyzeImage(cfg, blob);
      if (result) analyses.push(result);
    });

    if (!analyses.length) {
      Logger.log(group.address + ": sin resultados válidos del modelo, se omite");
      sendMessage(cfg, group.chatId, "⚠️ No pude analizar las fotos de «" + group.address + "». Probá de nuevo.");
      return;
    }

    var merged = mergeAnalyses(analyses);
    var geo = geocodeAddress(group.address);
    var fecha = Utilities.formatDate(new Date(group.date * 1000), Session.getScriptTimeZone(), "yyyy-MM-dd");

    sheet.appendRow([
      new Date(), fecha, group.address, geo.barrio, geo.lat, geo.lng,
      merged.material.valor, merged.estado.valor, merged.motivo.valor,
      merged.anio_edificio.valor, merged.color_acabado.valor, merged.herraje.valor,
      merged.ref_herreria.valor, overallCertainty(merged), merged.notas, group.from
    ]);

    sendMessage(cfg, group.chatId,
      "✅ Ficha creada: " + group.address + "\n" +
      "Material: " + merged.material.valor + " · Estado: " + merged.estado.valor + " · " +
      "Herraje: " + merged.herraje.valor + " · Certeza: " + overallCertainty(merged));
  });

  if (fetched.lastUpdateId !== null) acknowledge(cfg, fetched.lastUpdateId);
}

// ---- Telegram ----

function tgCall(cfg, method, params) {
  var url = "https://api.telegram.org/bot" + cfg.telegramToken + "/" + method;
  if (params) {
    var qs = Object.keys(params).map(function (k) {
      return k + "=" + encodeURIComponent(params[k]);
    }).join("&");
    url += "?" + qs;
  }
  var res = UrlFetchApp.fetch(url, { muteHttpExceptions: true });
  var data = JSON.parse(res.getContentText());
  if (!data.ok) throw new Error("Telegram API error en " + method + ": " + res.getContentText());
  return data.result;
}

function fetchNewGroups(cfg) {
  var updates = tgCall(cfg, "getUpdates", { timeout: 0 });
  if (!updates.length) return { groups: [], lastUpdateId: null };

  var groups = {};
  var order = [];

  updates.forEach(function (upd) {
    var msg = upd.message;
    if (!msg || !msg.photo) return;

    var chatId = String(msg.chat.id);
    if (chatId !== cfg.allowedChatId) return;

    var key = msg.media_group_id || ("single-" + msg.message_id);
    var largest = msg.photo.reduce(function (a, b) {
      var sa = a.file_size || a.width * a.height;
      var sb = b.file_size || b.width * b.height;
      return sb > sa ? b : a;
    });

    if (!groups[key]) {
      groups[key] = {
        chatId: chatId,
        from: msg.from.username || msg.from.first_name || "",
        date: msg.date,
        address: "",
        fileIds: []
      };
      order.push(key);
    }
    groups[key].fileIds.push(largest.file_id);
    if (msg.caption && !groups[key].address) groups[key].address = msg.caption.trim();
  });

  var orderedGroups = order.map(function (k) { return groups[k]; });
  var lastUpdateId = updates[updates.length - 1].update_id;
  return { groups: orderedGroups, lastUpdateId: lastUpdateId };
}

function acknowledge(cfg, lastUpdateId) {
  tgCall(cfg, "getUpdates", { offset: lastUpdateId + 1, timeout: 0 });
}

function downloadPhoto(cfg, fileId) {
  var fileInfo = tgCall(cfg, "getFile", { file_id: fileId });
  var url = "https://api.telegram.org/file/bot" + cfg.telegramToken + "/" + fileInfo.file_path;
  var res = UrlFetchApp.fetch(url, { muteHttpExceptions: true });
  return res.getBlob();
}

function sendMessage(cfg, chatId, text) {
  try {
    tgCall(cfg, "sendMessage", { chat_id: chatId, text: text });
  } catch (e) {
    Logger.log("No se pudo responder a " + chatId + ": " + e.message);
  }
}

// ---- OpenRouter (visión) ----

function analyzeImage(cfg, blob) {
  var base64 = Utilities.base64Encode(blob.getBytes());
  var mediaType = blob.getContentType() || "image/jpeg";

  var res = UrlFetchApp.fetch("https://openrouter.ai/api/v1/chat/completions", {
    method: "post",
    contentType: "application/json",
    headers: { "Authorization": "Bearer " + cfg.openrouterKey },
    payload: JSON.stringify({
      model: cfg.openrouterModel,
      max_tokens: 4096,
      messages: [{
        role: "user",
        content: [
          { type: "text", text: VISION_PROMPT },
          { type: "image_url", image_url: { url: "data:" + mediaType + ";base64," + base64 } }
        ]
      }]
    }),
    muteHttpExceptions: true
  });

  var code = res.getResponseCode();
  if (code !== 200) {
    Logger.log("OpenRouter HTTP " + code + ": " + res.getContentText().slice(0, 300));
    return null;
  }

  var data = JSON.parse(res.getContentText());
  var raw = data.choices[0].message.content.trim();
  raw = raw.replace(/^```json/i, "").replace(/^```/, "").replace(/```$/, "").trim();
  try {
    return JSON.parse(raw);
  } catch (e) {
    Logger.log("Error JSON: " + e + " | raw: " + raw.slice(0, 200));
    return null;
  }
}

function mergeField(analyses, key) {
  var best = null;
  analyses.forEach(function (a) {
    var f = a[key];
    if (!f || !f.valor) return;
    var rank = CERT_RANK[(f.certeza || "").toLowerCase()] || 0;
    if (!best || rank > best.rank) best = { valor: f.valor, certeza: f.certeza || "bajo", rank: rank };
  });
  return best ? { valor: best.valor, certeza: best.certeza } : { valor: "", certeza: "" };
}

function mergeAnalyses(analyses) {
  var out = {};
  ["material", "estado", "motivo", "anio_edificio", "color_acabado", "herraje", "ref_herreria"].forEach(function (k) {
    out[k] = mergeField(analyses, k);
  });
  var notas = analyses.map(function (a) { return a.notas; }).filter(Boolean);
  out.notas = notas.filter(function (n, i) { return notas.indexOf(n) === i; }).join(" | ");
  return out;
}

function overallCertainty(merged) {
  var ranks = ["material", "estado", "motivo", "anio_edificio", "color_acabado", "herraje"]
    .map(function (k) { return CERT_RANK[(merged[k].certeza || "").toLowerCase()] || 0; })
    .filter(Boolean);
  if (!ranks.length) return "";
  var avg = ranks.reduce(function (a, b) { return a + b; }, 0) / ranks.length;
  return avg >= 2.5 ? "alto" : avg >= 1.5 ? "medio" : "bajo";
}

// ---- Geocoding (Nominatim / OpenStreetMap, sin API key) ----

function geocodeAddress(address) {
  var url = "https://nominatim.openstreetmap.org/search?format=json&addressdetails=1&limit=1&q=" +
    encodeURIComponent(address + ", Ciudad Autónoma de Buenos Aires, Argentina");
  var res = UrlFetchApp.fetch(url, {
    muteHttpExceptions: true,
    headers: { "User-Agent": "gvdeco-relevamiento/1.0 (uso personal)" }
  });
  if (res.getResponseCode() !== 200) {
    Logger.log("Nominatim HTTP " + res.getResponseCode() + ": " + res.getContentText().slice(0, 200));
    return { lat: "", lng: "", barrio: "" };
  }
  var data;
  try {
    data = JSON.parse(res.getContentText());
  } catch (e) {
    Logger.log("Nominatim: respuesta no es JSON: " + res.getContentText().slice(0, 200));
    return { lat: "", lng: "", barrio: "" };
  }
  if (!data.length) return { lat: "", lng: "", barrio: "" };

  var addr = data[0].address || {};
  var barrio = addr.suburb || addr.neighbourhood || addr.city_district || addr.quarter || "";
  return { lat: data[0].lat, lng: data[0].lon, barrio: barrio };
}
