/**
 * Abel Learning Drive Bridge
 *
 * Gemini TTS generation is owned by the Python TTS router/renderer.
 * This Apps Script is storage-only: it accepts finished MP3 bytes and writes
 * them under the configured Abel Learning root.
 */

function doGet(e) {
  return jsonResponse({
    status: "online",
    engine: "Abel Learning Drive Bridge",
    provider: "gemini",
    message: "Storage bridge is running. TTS synthesis is disabled here."
  });
}

function doPost(e) {
  try {
    if (!e || !e.postData || !e.postData.contents) {
      return jsonResponse({status: "error", message: "No POST body received."});
    }

    var data = JSON.parse(e.postData.contents);

    if (data.action === "generate-lesson-audio") {
      return jsonResponse({
        status: "error",
        provider: "gemini",
        message: "TTS generation is owned by Abel's Python Gemini TTS router. Use the generated MP3 with save-gemini-lesson-audio."
      });
    }

    if (data.action === "save-gemini-lesson-audio") {
      return handleSaveGeminiLessonAudio(data);
    }

    return jsonResponse({
      status: "error",
      message: "Unknown action: " + (data.action || "")
    });
  } catch (error) {
    return jsonResponse({
      status: "error",
      message: error.toString(),
      stack: error.stack || ""
    });
  }
}

function learningRootFolder() {
  var folderId = PropertiesService.getScriptProperties().getProperty("ABEL_LEARNING_FOLDER_ID");
  if (!folderId) throw new Error("ABEL_LEARNING_FOLDER_ID is missing from Script Properties.");
  return DriveApp.getFolderById(folderId);
}

function getOrCreateChildFolder(parent, name) {
  var folders = parent.getFoldersByName(name);
  return folders.hasNext() ? folders.next() : parent.createFolder(name);
}

function routedFolder(language, skill, level, date) {
  var root = learningRootFolder();
  return [language || "Unknown", skill || "General", level || "General", date]
    .reduce(function(parent, name) { return getOrCreateChildFolder(parent, name); }, root);
}

function logFolder() {
  return getOrCreateChildFolder(getOrCreateChildFolder(learningRootFolder(), "_SYSTEM"), "LOG");
}

function handleSaveGeminiLessonAudio(data) {
  var audioBase64 = data.audioBase64;
  if (!audioBase64) return jsonResponse({status: "error", message: "Missing audioBase64."});

  var now = new Date();
  var sessionDate = data.date || Utilities.formatDate(now, Session.getScriptTimeZone(), "yyyy-MM-dd");
  var sessionTime = data.time || Utilities.formatDate(now, Session.getScriptTimeZone(), "HHmmss");
  var folder = routedFolder(data.languageLabel || data.language || "Unknown", data.skill || "General", data.level || "General", sessionDate);
  var fileName = data.fileName || ("lesson_" + sessionDate + "_" + sessionTime + ".mp3");

  var existingFiles = folder.getFilesByName(fileName);
  if (existingFiles.hasNext()) {
    var existingFile = existingFiles.next();
    return jsonResponse({status:"success", cached:true, provider:"gemini", fileId:existingFile.getId(), fileUrl:existingFile.getUrl(), fileName:existingFile.getName()});
  }

  var audioBlob = Utilities.newBlob(Utilities.base64Decode(audioBase64), data.mimeType || "audio/mpeg", fileName);
  var file = folder.createFile(audioBlob);

  var manifest = {
    status: "success", provider: "gemini", createdAt: new Date().toISOString(),
    language: data.language || "", languageLabel: data.languageLabel || "",
    skill: data.skill || "", level: data.level || "", type: data.type || "audio_lesson",
    route: data.route || "", lesson: data.lesson || {},
    audio: {fileId:file.getId(), fileName:file.getName(), fileUrl:file.getUrl()}
  };
  folder.createFile("lesson_" + sessionDate + "_" + sessionTime + ".json",
                    JSON.stringify(manifest, null, 2), "application/json");

  var log = {
    timestamp:new Date().toISOString(), session:sessionDate + "_" + sessionTime,
    status:"SUCCESS_GEMINI_TTS", language:data.language || "", skill:data.skill || "",
    level:data.level || "", path:data.route || "", fileId:file.getId()
  };
  logFolder().createFile("generation_" + sessionDate + "_" + sessionTime + ".json",
                         JSON.stringify(log, null, 2), "application/json");

  return jsonResponse({
    status:"success", cached:false, provider:"gemini", fileId:file.getId(),
    fileUrl:file.getUrl(), fileName:file.getName(), date:sessionDate, time:sessionTime,
    route:data.route || "", message:"Gemini TTS MP3 saved to routed Abel Learning Drive."
  });
}

function jsonResponse(data) {
  return ContentService
    .createTextOutput(JSON.stringify(data))
    .setMimeType(ContentService.MimeType.JSON);
}
