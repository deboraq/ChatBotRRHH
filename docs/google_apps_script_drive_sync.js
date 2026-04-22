/**
 * Google Apps Script — Sync Drive → ChatBot KB en tiempo real
 *
 * Detecta cambios en la carpeta CHATBOT de Drive y llama al webhook
 * del bot para actualizar la base de conocimiento automáticamente.
 *
 * INSTALACIÓN:
 *   1. Ir a https://script.google.com → Nuevo proyecto
 *   2. Pegar este código completo
 *   3. Ejecutar `setupTrigger` una vez (menú Ejecutar > setupTrigger)
 *   4. Aceptar los permisos que pide Google
 *   5. Listo — el script corre cada minuto automáticamente
 *
 * DESINSTALAR / CAMBIAR INTERVALO:
 *   Ejecutar `removeTriggers` para borrar el trigger existente,
 *   luego cambiar TRIGGER_MINUTES y volver a correr `setupTrigger`.
 */

// ─── Configuración ──────────────────────────────────────────────────────────

/** ID de la carpeta padre CHATBOT en Google Drive */
const PARENT_FOLDER_ID = "121tUalzQ0QoAI8Q_QoGqDGuaA_OkbwAh";

/** URL del webhook de sincronización */
const WEBHOOK_URL =
  "https://debo-chat.web.app/webhook/n8n/sync-knowledge";

/** Secret configurado en Cloud Run (N8N_WEBHOOK_SECRET) */
const WEBHOOK_SECRET =
  "265356307c3d7ab43397f1787960e8efa305ccbb0300d230b73740dd6a36638b";

/** Ventana de detección en minutos (debe ser >= TRIGGER_MINUTES + 1) */
const CHECK_WINDOW_MINUTES = 3;

/** Frecuencia del trigger en minutos (mínimo 1) */
const TRIGGER_MINUTES = 1;

// ────────────────────────────────────────────────────────────────────────────

/**
 * Función principal — corre cada TRIGGER_MINUTES minutos.
 * Busca archivos modificados recientemente dentro de cada subcarpeta
 * de empresa y llama al webhook correspondiente.
 */
function checkDriveChanges() {
  const cutoff = new Date(Date.now() - CHECK_WINDOW_MINUTES * 60 * 1000);

  let parentFolder;
  try {
    parentFolder = DriveApp.getFolderById(PARENT_FOLDER_ID);
  } catch (e) {
    Logger.log("ERROR: No se pudo acceder a la carpeta padre: " + e);
    return;
  }

  const triggered = {}; // folderId → true (para no duplicar llamadas)

  const subfolders = parentFolder.getFolders();
  while (subfolders.hasNext()) {
    const companyFolder = subfolders.next();
    const companyFolderId = companyFolder.getId();

    // Revisar archivos directamente en la subcarpeta de empresa
    if (_hasRecentChanges(companyFolder, cutoff)) {
      if (!triggered[companyFolderId]) {
        triggered[companyFolderId] = true;
        _callSync(companyFolderId, companyFolder.getName());
      }
      continue;
    }

    // Revisar sub-subcarpetas (por convenio, área, etc.)
    const subSubs = companyFolder.getFolders();
    while (subSubs.hasNext()) {
      const sub = subSubs.next();
      if (_hasRecentChanges(sub, cutoff)) {
        if (!triggered[companyFolderId]) {
          triggered[companyFolderId] = true;
          _callSync(companyFolderId, companyFolder.getName());
        }
        break; // ya disparamos para esta empresa, no seguir
      }
    }
  }

  if (Object.keys(triggered).length === 0) {
    Logger.log("Sin cambios detectados en los últimos " + CHECK_WINDOW_MINUTES + " min.");
  }
}

/**
 * Devuelve true si algún archivo dentro de `folder` fue modificado
 * después de `cutoff`.
 */
function _hasRecentChanges(folder, cutoff) {
  const files = folder.getFiles();
  while (files.hasNext()) {
    if (files.next().getLastUpdated() > cutoff) return true;
  }
  return false;
}

/**
 * Llama al webhook de sincronización para una carpeta de empresa.
 */
function _callSync(folderId, folderName) {
  Logger.log("Cambio detectado en: " + folderName + " (" + folderId + ")");

  const options = {
    method: "post",
    contentType: "application/json",
    headers: { "X-Webhook-Secret": WEBHOOK_SECRET },
    payload: JSON.stringify({ folder_id: folderId }),
    muteHttpExceptions: true,
  };

  try {
    const resp = UrlFetchApp.fetch(WEBHOOK_URL, options);
    const body = resp.getContentText();
    Logger.log(
      "Webhook response [" +
        resp.getResponseCode() +
        "] para " +
        folderName +
        ": " +
        body
    );
  } catch (e) {
    Logger.log("ERROR llamando webhook para " + folderName + ": " + e);
  }
}

// ─── Setup / teardown ───────────────────────────────────────────────────────

/**
 * Instala el trigger de tiempo. Ejecutar UNA VEZ manualmente.
 */
function setupTrigger() {
  removeTriggers(); // limpiar anteriores primero
  ScriptApp.newTrigger("checkDriveChanges")
    .timeBased()
    .everyMinutes(TRIGGER_MINUTES)
    .create();
  Logger.log(
    "✓ Trigger creado: checkDriveChanges cada " + TRIGGER_MINUTES + " minuto(s)."
  );
}

/**
 * Elimina todos los triggers del proyecto.
 */
function removeTriggers() {
  const triggers = ScriptApp.getProjectTriggers();
  triggers.forEach((t) => ScriptApp.deleteTrigger(t));
  Logger.log("Triggers eliminados: " + triggers.length);
}

/**
 * Prueba manual: simula una ventana de 60 minutos para verificar conectividad.
 */
function testSync() {
  const cutoff = new Date(Date.now() - 60 * 60 * 1000); // última hora
  Logger.log("=== TEST: buscando cambios en la última hora ===");

  const parentFolder = DriveApp.getFolderById(PARENT_FOLDER_ID);
  const subfolders = parentFolder.getFolders();
  while (subfolders.hasNext()) {
    const f = subfolders.next();
    if (_hasRecentChanges(f, cutoff)) {
      Logger.log("Llamando sync para: " + f.getName());
      _callSync(f.getId(), f.getName());
    } else {
      Logger.log("Sin cambios recientes en: " + f.getName());
    }
  }
  Logger.log("=== TEST finalizado ===");
}
