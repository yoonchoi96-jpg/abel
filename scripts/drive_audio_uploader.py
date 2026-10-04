#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, os
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
from google.auth.transport.requests import AuthorizedSession
from google.oauth2 import service_account

DRIVE_SCOPE = "https://www.googleapis.com/auth/drive"
FOLDER_MIME = "application/vnd.google-apps.folder"
KST = ZoneInfo("Asia/Seoul")
API = "https://www.googleapis.com/drive/v3"
UPLOAD_API = "https://www.googleapis.com/upload/drive/v3"

def credentials():
    raw = os.getenv("GCP_SA_KEY", "").strip()
    if raw:
        return service_account.Credentials.from_service_account_info(
            json.loads(raw), scopes=[DRIVE_SCOPE]
        )
    path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "").strip()
    if not path:
        raise RuntimeError("GCP_SA_KEY or GOOGLE_APPLICATION_CREDENTIALS is required.")
    return service_account.Credentials.from_service_account_file(
        path, scopes=[DRIVE_SCOPE]
    )

class DrivePublisher:
    def __init__(self, root_folder_id: str):
        if not root_folder_id:
            raise RuntimeError("ABEL_DRIVE_FOLDER_ID is required.")
        self.root_folder_id = root_folder_id
        self.session = AuthorizedSession(credentials())

    def request(self, method, url, **kwargs):
        response = self.session.request(method, url, timeout=120, **kwargs)
        if not response.ok:
            raise RuntimeError(
                f"Google Drive API {response.status_code}: {response.text[:2000]}"
            )
        return response

    def children(self, parent_id, name, mime_type=None):
        q = [
            f"'{parent_id}' in parents",
            "trashed = false",
            f"name = {json.dumps(name)}",
        ]
        if mime_type:
            q.append(f"mimeType = {json.dumps(mime_type)}")
        params = {
            "q": " and ".join(q),
            "pageSize": 20,
            "fields": "files(id,name,mimeType,webViewLink)",
            "supportsAllDrives": "true",
            "includeItemsFromAllDrives": "true",
        }
        return self.request("GET", f"{API}/files", params=params).json().get("files", [])

    def ensure_folder(self, parent_id, name):
        found = self.children(parent_id, name, FOLDER_MIME)
        if found:
            return found[0]
        return self.request(
            "POST",
            f"{API}/files",
            params={"supportsAllDrives": "true", "fields": "id,name,mimeType,webViewLink"},
            json={"name": name, "mimeType": FOLDER_MIME, "parents": [parent_id]},
        ).json()

    def ensure_path(self, *parts):
        current = {"id": self.root_folder_id}
        for part in parts:
            current = self.ensure_folder(current["id"], part)
        return current

    def find_file(self, parent_id, name):
        found = self.children(parent_id, name)
        return found[0] if found else None

    def upload_file(self, path, parent_id, name, mime_type):
        existing = self.find_file(parent_id, name)
        data = Path(path).read_bytes()

        if existing:
            file_id = existing["id"]
        else:
            created = self.request(
                "POST",
                f"{API}/files",
                params={"supportsAllDrives": "true", "fields": "id,name,mimeType"},
                json={"name": name, "mimeType": mime_type, "parents": [parent_id]},
            ).json()
            file_id = created["id"]

        return self.request(
            "PATCH",
            f"{UPLOAD_API}/files/{file_id}",
            params={
                "uploadType": "media",
                "fields": "id,name,mimeType,size,webViewLink",
                "supportsAllDrives": "true",
            },
            headers={"Content-Type": mime_type},
            data=data,
        ).json()

    def upload_bytes(self, content, parent_id, name, mime_type):
        tmp = Path("/tmp") / f"abel-drive-{os.getpid()}-{name}"
        tmp.write_bytes(content)
        try:
            return self.upload_file(tmp, parent_id, name, mime_type)
        finally:
            tmp.unlink(missing_ok=True)

    def publish_lesson(self, mp3_path, *, date, time, title="", level="", topic="", text=""):
        audio_folder = self.ensure_path("AUDIO", date)
        filename = f"lesson_{date}_{time}.mp3"
        audio = self.upload_file(mp3_path, audio_folder["id"], filename, "audio/mpeg")

        outbox_folder = self.ensure_path("OUTBOX")
        record = {
            "status": "success",
            "provider": "gemini",
            "createdAt": datetime.now(KST).isoformat(),
            "session": {"date": date, "time": time},
            "lesson": {"text": text, "title": title, "level": level, "topic": topic},
            "audio": {
                "fileId": audio.get("id"),
                "fileName": audio.get("name", filename),
                "fileUrl": audio.get("webViewLink") or f"https://drive.google.com/file/d/{audio.get('id')}/view",
            },
        }
        self.upload_bytes(
            json.dumps(record, ensure_ascii=False, indent=2).encode("utf-8"),
            outbox_folder["id"], f"lesson_{date}_{time}.json", "application/json",
        )

        log_folder = self.ensure_path("LOG")
        self.upload_bytes(
            json.dumps({
                "timestamp": datetime.now(KST).isoformat(),
                "session": f"{date}_{time}",
                "status": "SUCCESS_GEMINI_TTS",
                "fileId": audio.get("id"),
            }, ensure_ascii=False, indent=2).encode("utf-8"),
            log_folder["id"], f"generation_{date}_{time}.json", "application/json",
        )

        return {
            "status": "success",
            "provider": "gemini",
            "cached": False,
            "fileId": audio.get("id"),
            "fileUrl": record["audio"]["fileUrl"],
            "fileName": filename,
            "message": "Gemini TTS MP3 generated and saved directly to Google Drive.",
        }

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--file", default="")
    parser.add_argument("--date", default="")
    parser.add_argument("--time", default="")
    parser.add_argument("--title", default="")
    parser.add_argument("--level", default="HSK6")
    parser.add_argument("--topic", default="")
    parser.add_argument("--text", default="")
    args = parser.parse_args()

    publisher = DrivePublisher(os.getenv("ABEL_DRIVE_FOLDER_ID", ""))
    if args.self_test:
        folder = publisher.ensure_path("AUDIO")
        print(json.dumps({
            "status": "success",
            "provider": "google_drive_api",
            "root_folder_id": publisher.root_folder_id,
            "audio_folder_id": folder["id"],
            "message": "Drive access verified.",
        }, ensure_ascii=False))
        return

    if not args.file:
        raise SystemExit("--file is required unless --self-test is used.")

    now = datetime.now(KST)
    date = args.date or now.strftime("%Y-%m-%d")
    time = args.time or now.strftime("%H%M%S")
    print(json.dumps(publisher.publish_lesson(
        args.file, date=date, time=time, title=args.title,
        level=args.level, topic=args.topic, text=args.text
    ), ensure_ascii=False))

if __name__ == "__main__":
    main()
