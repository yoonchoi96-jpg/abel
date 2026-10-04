/**
 * Abel Chinese Listening Engine
 * Gemini TTS (Python) → Apps Script storage → Google Drive
 *
 * Drive structure:
 * Abel/
 * ├── AUDIO/
 * │   └── YYYY-MM-DD/
 * │       └── lesson_YYYY-MM-DD_HHMM.mp3
 * ├── OUTBOX/
 * │   └── lesson_YYYY-MM-DD_HHMM.json
 * └── LOG/
 *     └── generation_log.json
 */


/* =========================================================
   1. GET TEST
   ========================================================= */

function doGet(e) {
  return jsonResponse({
    status: "online",
    engine: "Abel Chinese Education Engine",
    version: "1.0.0",
    message: "Automation server is running."
  });
}


/* =========================================================
   2. POST ENTRY POINT
   Gemini → Apps Script
   ========================================================= */

function doPost(e) {
  try {

    if (!e || !e.postData || !e.postData.contents) {
      return jsonResponse({
        status: "error",
        message: "No POST body received."
      });
    }

    var data = JSON.parse(e.postData.contents);

    if (!data.action) {
      return jsonResponse({
        status: "error",
        message: "Missing action."
      });
    }

    if (data.action === "generate-lesson-audio") {
      return handleGenerateLessonAudio(data);
    }

    if (data.action === "save-gemini-lesson-audio") {
      return handleSaveGeminiLessonAudio(data);
    }

    return jsonResponse({
      status: "error",
      message: "Unknown action: " + data.action
    });

  } catch (error) {

    return jsonResponse({
      status: "error",
      message: error.toString(),
      stack: error.stack || ""
    });
  }
}


/* =========================================================
   3. MAIN AUDIO GENERATION
   ========================================================= */

function handleGenerateLessonAudio(data) {

  // -----------------------------
  // Validate input
  // -----------------------------

  var lessonText = data.text;

  if (!lessonText || lessonText.trim() === "") {
    return jsonResponse({
      status: "error",
      message: "Missing lesson text."
    });
  }

  // -----------------------------
  // Date / Time
  // -----------------------------

  var now = new Date();

  var sessionDate =
    data.date ||
    Utilities.formatDate(
      now,
      Session.getScriptTimeZone(),
      "yyyy-MM-dd"
    );

  var sessionTime =
    data.time ||
    Utilities.formatDate(
      now,
      Session.getScriptTimeZone(),
      "HHmm"
    );

  // -----------------------------
  // Folder
  // -----------------------------

  var folder = getOrCreateFolder(
    "Abel/AUDIO/" + sessionDate
  );

  // -----------------------------
  // Filename
  // -----------------------------

  var fileName =
    "lesson_" +
    sessionDate +
    "_" +
    sessionTime +
    ".mp3";

  // -----------------------------
  // Duplicate protection
  // -----------------------------

  var existingFiles =
    folder.getFilesByName(fileName);

  if (existingFiles.hasNext()) {

    var existingFile =
      existingFiles.next();

    return jsonResponse({
      status: "success",
      cached: true,
      fileId: existingFile.getId(),
      fileUrl: existingFile.getUrl(),
      fileName: existingFile.getName(),
      message: "File already exists."
    });
  }

  // -----------------------------
  // Google Cloud TTS
  // -----------------------------

  var mp3Blob =
    callGoogleCloudTTS(lessonText);

  // -----------------------------
  // Save MP3
  // -----------------------------

  mp3Blob.setName(fileName);

  var file =
    folder.createFile(mp3Blob);

  // -----------------------------
  // Save OUTBOX JSON
  // -----------------------------

  saveOutboxJson(
    sessionDate,
    sessionTime,
    data,
    file
  );

  // -----------------------------
  // Save LOG
  // -----------------------------

  appendLog(
    sessionDate,
    sessionTime,
    "SUCCESS",
    file.getId()
  );

  // -----------------------------
  // Response
  // -----------------------------

  return jsonResponse({
    status: "success",
    cached: false,
    fileId: file.getId(),
    fileUrl: file.getUrl(),
    fileName: file.getName(),
    date: sessionDate,
    time: sessionTime,
    message: "MP3 successfully generated and saved to Google Drive."
  });
}


/* =========================================================
   4. GEMINI TTS AUDIO STORAGE
   Gemini generates the MP3 outside Apps Script.
   Apps Script only stores the finished MP3 in Drive.
   ========================================================= */

function handleSaveGeminiLessonAudio(data) {

  var audioBase64 = data.audioBase64;

  if (!audioBase64) {
    return jsonResponse({
      status: "error",
      message: "Missing audioBase64."
    });
  }

  var now = new Date();

  var sessionDate =
    data.date ||
    Utilities.formatDate(
      now,
      Session.getScriptTimeZone(),
      "yyyy-MM-dd"
    );

  var sessionTime =
    data.time ||
    Utilities.formatDate(
      now,
      Session.getScriptTimeZone(),
      "HHmm"
    );

  var folder = getOrCreateFolder(
    "Abel/AUDIO/" + sessionDate
  );

  var fileName =
    data.fileName ||
    "lesson_" +
    sessionDate +
    "_" +
    sessionTime +
    ".mp3";

  var existingFiles =
    folder.getFilesByName(fileName);

  if (existingFiles.hasNext()) {
    var existingFile = existingFiles.next();
    return jsonResponse({
      status: "success",
      cached: true,
      provider: "gemini",
      fileId: existingFile.getId(),
      fileUrl: existingFile.getUrl(),
      fileName: existingFile.getName(),
      message: "File already exists."
    });
  }

  var audioBytes =
    Utilities.base64Decode(audioBase64);

  var mimeType =
    data.mimeType || "audio/mpeg";

  var audioBlob =
    Utilities.newBlob(
      audioBytes,
      mimeType,
      fileName
    );

  var file =
    folder.createFile(audioBlob);

  saveOutboxJson(
    sessionDate,
    sessionTime,
    data,
    file
  );

  appendLog(
    sessionDate,
    sessionTime,
    "SUCCESS_GEMINI_TTS",
    file.getId()
  );

  return jsonResponse({
    status: "success",
    cached: false,
    provider: "gemini",
    fileId: file.getId(),
    fileUrl: file.getUrl(),
    fileName: file.getName(),
    date: sessionDate,
    time: sessionTime,
    message: "Gemini TTS MP3 saved to Google Drive."
  });
}


/* =========================================================
   4. GOOGLE CLOUD TEXT-TO-SPEECH
   ========================================================= */

function callGoogleCloudTTS(text) {

  // -----------------------------
  // Get API Key
  // -----------------------------

  var apiKey =
    PropertiesService
      .getScriptProperties()
      .getProperty("GCP_TTS_API_KEY");

  if (!apiKey) {
    throw new Error(
      "GCP_TTS_API_KEY is missing from Script Properties."
    );
  }

  // -----------------------------
  // Google TTS endpoint
  // -----------------------------

  var url =
    "https://texttospeech.googleapis.com/v1/text:synthesize?key=" +
    encodeURIComponent(apiKey);

  // -----------------------------
  // TTS request
  // -----------------------------
  //
  // Mandarin Chinese
  // Google Cloud supported voice
  //
  // cmn-CN-Wavenet-D
  //
  // -----------------------------

  var payload = {

    input: {
      text: text
    },

    voice: {
      languageCode: "cmn-CN",
      name: "cmn-CN-Wavenet-D",
      ssmlGender: "FEMALE"
    },

    audioConfig: {
      audioEncoding: "MP3"
    }
  };

  // -----------------------------
  // HTTP request
  // -----------------------------

  var options = {

    method: "post",

    contentType: "application/json",

    payload: JSON.stringify(payload),

    muteHttpExceptions: true
  };

  var response =
    UrlFetchApp.fetch(
      url,
      options
    );

  var responseCode =
    response.getResponseCode();

  var responseText =
    response.getContentText();

  // -----------------------------
  // Error handling
  // -----------------------------

  if (responseCode !== 200) {

    throw new Error(
      "Google Cloud TTS API error (" +
      responseCode +
      "): " +
      responseText
    );
  }

  var json =
    JSON.parse(responseText);

  if (!json.audioContent) {

    throw new Error(
      "Google Cloud TTS returned no audioContent."
    );
  }

  // -----------------------------
  // Base64 → MP3 Blob
  // -----------------------------

  var audioBytes =
    Utilities.base64Decode(
      json.audioContent
    );

  return Utilities.newBlob(
    audioBytes,
    "audio/mpeg",
    "temp.mp3"
  );
}


/* =========================================================
   5. DRIVE FOLDER CREATION
   ========================================================= */

function getOrCreateFolder(path) {

  var parts =
    path.split("/");

  var folder =
    DriveApp.getRootFolder();

  for (var i = 0; i < parts.length; i++) {

    var subFolders =
      folder.getFoldersByName(
        parts[i]
      );

    if (subFolders.hasNext()) {

      folder =
        subFolders.next();

    } else {

      folder =
        folder.createFolder(
          parts[i]
        );
    }
  }

  return folder;
}


/* =========================================================
   6. OUTBOX JSON
   ========================================================= */

function saveOutboxJson(
  date,
  time,
  data,
  audioFile
) {

  var folder =
    getOrCreateFolder(
      "Abel/OUTBOX"
    );

  var fileName =
    "lesson_" +
    date +
    "_" +
    time +
    ".json";

  var output = {

    status: "success",

    createdAt:
      new Date().toISOString(),

    session: {
      date: date,
      time: time
    },

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

  // 기존 동일 파일 삭제
  var existing =
    folder.getFilesByName(
      fileName
    );

  while (existing.hasNext()) {
    existing.next().setTrashed(true);
  }

  folder.createFile(
    fileName,
    JSON.stringify(
      output,
      null,
      2
    ),
    "application/json"
  );
}


/* =========================================================
   7. LOG
   ========================================================= */

function appendLog(
  date,
  time,
  status,
  fileId
) {

  var folder =
    getOrCreateFolder(
      "Abel/LOG"
    );

  var files =
    folder.getFilesByName(
      "generation_log.json"
    );

  var logData = [];

  var logFile;

  if (files.hasNext()) {

    logFile =
      files.next();

    try {

      logData =
        JSON.parse(
          logFile
            .getBlob()
            .getDataAsString()
        );

      if (!Array.isArray(logData)) {
        logData = [];
      }

    } catch (e) {

      logData = [];
    }

  } else {

    logFile =
      folder.createFile(
        "generation_log.json",
        "[]",
        "application/json"
      );
  }

  logData.push({

    timestamp:
      new Date().toISOString(),

    session:
      date + "_" + time,

    status:
      status,

    fileId:
      fileId || null
  });

  logFile.setContent(
    JSON.stringify(
      logData,
      null,
      2
    )
  );
}


/* =========================================================
   8. JSON RESPONSE
   ========================================================= */

function jsonResponse(data) {

  return ContentService
    .createTextOutput(
      JSON.stringify(data)
    )
    .setMimeType(
      ContentService.MimeType.JSON
    );
}


/* =========================================================
   9. LOCAL TEST
   ========================================================= */

function testGenerateLessonAudio() {

  var data = {

    action:
      "generate-lesson-audio",

    text:
      "大家好，今天我们来练习汉语听力。虽然这个问题看起来很简单，但是如果仔细分析，就会发现其中还有很多值得注意的地方。",

    date:
      "2026-10-02",

    time:
      "1520",

    title:
      "HSK6 Listening Test",

    level:
      "HSK6",

    topic:
      "Daily Life"
  };

  var result =
    handleGenerateLessonAudio(
      data
    );

  Logger.log(
    result.getContent()
  );
}