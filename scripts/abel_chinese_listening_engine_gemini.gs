/**
 * Abel Chinese Listening Storage Bridge
 *
 * Gemini TTS generation is owned by the Python TTS router/renderer.
 * This Apps Script is storage-only: it accepts finished MP3 bytes and writes
 * them under the configured Chinese Drive folder.
 */

function doGet(e) {
  return jsonResponse({
    status: "online",
    engine: "Abel Chinese Listening Storage Bridge",
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

function chineseRootFolder() {
  var folderId = PropertiesService
    .getScriptProperties()
    .getProperty("ABEL_CHINESE_FOLDER_ID");

  if (!folderId) {
    throw new Error("ABEL_CHINESE_FOLDER_ID is missing from Script Properties.");
  }

  return DriveApp.getFolderById(folderId);
}

function getOrCreateChildFolder(parent, name) {
  var folders = parent.getFoldersByName(name);
  return folders.hasNext() ? folders.next() : parent.createFolder(name);
}

function chineseAudioFolder(date) {
  var root = chineseRootFolder();
  var audio = getOrCreateChildFolder(root, "AUDIO");
  return getOrCreateChildFolder(audio, date);
}

function chineseOutboxFolder() {
  return getOrCreateChildFolder(chineseRootFolder(), "OUTBOX");
}

function chineseLogFolder() {
  return getOrCreateChildFolder(chineseRootFolder(), "LOG");
}

function handleSaveGeminiLessonAudio(data) {
  var audioBase64 = data.audioBase64;
  if (!audioBase64) {
    return jsonResponse({status: "error", message: "Missing audioBase64."});
  }

  var now = new Date();
  var sessionDate = data.date || Utilities.formatDate(
    now, Session.getScriptTimeZone(), "yyyy-MM-dd"
  );
  var sessionTime = data.time || Utilities.formatDate(
    now, Session.getScriptTimeZone(), "HHmmss"
  );

  var folder = chineseAudioFolder(sessionDate);
  var fileName = data.fileName || ("lesson_" + sessionDate + "_" + sessionTime + ".mp3");

  var existingFiles = folder.getFilesByName(fileName);
  if (existingFiles.hasNext()) {
    var existingFile = existingFiles.next();
    return jsonResponse({
      status: "success",
      cached: true,
      provider: "gemini",
      fileId: existingFile.getId(),
      fileUrl: existingFile.getUrl(),
      fileName: existingFile.getName()
    });
  }

  var audioBlob = Utilities.newBlob(
    Utilities.base64Decode(audioBase64),
    data.mimeType || "audio/mpeg",
    fileName
  );
  var file = folder.createFile(audioBlob);

  saveOutboxJson(sessionDate, sessionTime, data, file);
  appendLog(sessionDate, sessionTime, "SUCCESS_GEMINI_TTS", file.getId());

  return jsonResponse({
    status: "success",
    cached: false,
    provider: "gemini",
    fileId: file.getId(),
    fileUrl: file.getUrl(),
    fileName: file.getName(),
    date: sessionDate,
    time: sessionTime,
    message: "Gemini TTS MP3 saved to the configured Chinese Drive folder."
  });
}

function saveOutboxJson(date, time, data, audioFile) {
  var folder = chineseOutboxFolder();
  var fileName = "lesson_" + date + "_" + time + ".json";
  var existing = folder.getFilesByName(fileName);

  while (existing.hasNext()) {
    existing.next().setTrashed(true);
  }

  var output = {
    status: "success",
    provider: "gemini",
    createdAt: new Date().toISOString(),
    session: {date: date, time: time},
    lesson: {
      action: data.action || "",
      text: data.text || "",
      title: data.title || "",
      level: data.level || "",
      topic: data.topic || ""
    },
    audio: {
      fileId: audioFile.getId(),
      fileName: audioFile.getName(),
      fileUrl: audioFile.getUrl()
    }
  };

  folder.createFile(
    fileName,
    JSON.stringify(output, null, 2),
    "application/json"
  );
}

function appendLog(date, time, status, fileId) {
  var folder = chineseLogFolder();
  var files = folder.getFilesByName("generation_log.json");
  var logData = [];
  var logFile;

  if (files.hasNext()) {
    logFile = files.next();
    try {
      logData = JSON.parse(logFile.getBlob().getDataAsString());
      if (!Array.isArray(logData)) logData = [];
    } catch (e) {
      logData = [];
    }
  } else {
    logFile = folder.createFile("generation_log.json", "[]", "application/json");
  }

  logData.push({
    timestamp: new Date().toISOString(),
    session: date + "_" + time,
    status: status,
    provider: "gemini",
    fileId: fileId || null
  });

  logFile.setContent(JSON.stringify(logData, null, 2));
}

function jsonResponse(data) {
  return ContentService
    .createTextOutput(JSON.stringify(data))
    .setMimeType(ContentService.MimeType.JSON);
}
