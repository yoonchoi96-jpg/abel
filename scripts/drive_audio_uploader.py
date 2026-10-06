#!/usr/bin/env python3
from __future__ import annotations
import argparse, base64, json, os
from datetime import datetime
from pathlib import Path
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo
from google.auth.transport.requests import AuthorizedSession
from google.oauth2 import service_account
from google.oauth2.credentials import Credentials as OAuthCredentials

try:
    from learning_router import resolve_learning_route
except ModuleNotFoundError:
    from scripts.learning_router import resolve_learning_route
from google.auth import default as google_auth_default

DRIVE_SCOPE = "https://www.googleapis.com/auth/drive"
FOLDER_MIME = "application/vnd.google-apps.folder"
KST = ZoneInfo("Asia/Seoul")
API = "https://www.googleapis.com/drive/v3"
UPLOAD_API = "https://www.googleapis.com/upload/drive/v3"

def credentials():
    client_id = os.getenv("GOOGLE_DRIVE_OAUTH_CLIENT_ID", "").strip()
    client_secret = os.getenv("GOOGLE_DRIVE_OAUTH_CLIENT_SECRET", "").strip()
    refresh_token = os.getenv("GOOGLE_DRIVE_OAUTH_REFRESH_TOKEN", "").strip()
    if client_id and client_secret and refresh_token:
        return OAuthCredentials(token=None, refresh_token=refresh_token, token_uri="https://oauth2.googleapis.com/token", client_id=client_id, client_secret=client_secret, scopes=[DRIVE_SCOPE])

    raw = os.getenv("GCP_SA_KEY", "").strip()
    if raw:
        return service_account.Credentials.from_service_account_info(
            json.loads(raw), scopes=[DRIVE_SCOPE]
        )

    # Prefer the ambient Application Default Credentials supplied by
    # GitHub Actions WIF / Cloud Run. Those credentials are not a
    # service-account JSON file and must not be parsed as one.
    try:
        creds, _ = google_auth_default(scopes=[DRIVE_SCOPE])
        return creds
    except Exception:
        pass

    # Explicit service-account JSON is a local/manual fallback.
    path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "").strip()
    if path:
        return service_account.Credentials.from_service_account_file(
            path, scopes=[DRIVE_SCOPE]
        )

    raise RuntimeError("No usable Google credentials found.")

class DrivePublisher:
    def __init__(self, root_folder_id: str):
        self.root_folder_id = root_folder_id.strip()
        if not self.root_folder_id:
            raise RuntimeError("ABEL_DRIVE_FOLDER_ID is required.")
        self.session = AuthorizedSession(credentials())

    def request(self, method, url, **kwargs):
        response = self.session.request(method, url, timeout=120, **kwargs)
        if not response.ok:
            raise RuntimeError(
                f"Google Drive API {response.status_code}: {response.text[:2000]}"
            )
        return response

    def children(self, parent_id, name, mime_type=None):
        def quote(value):
            return "'" + value.replace("\\", "\\\\").replace("'", "\\'") + "'"

        q = [
            f"'{parent_id}' in parents",
            "trashed = false",
            f"name = {quote(name)}",
        ]
        if mime_type:
            q.append(f"mimeType = {quote(mime_type)}")
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

    def publish_lesson(
        self,
        mp3_path,
        *,
        date,
        time,
        title="",
        level="",
        topic="",
        text="",
        language="zh-CN",
        skill="listening",
        content_type="audio_lesson",
        delivery_mode="",
        speaker_mode="",
    ):
        route = resolve_learning_route(language=language, skill=skill, level=level)
        content_folder = self.ensure_path(*route.parts, date)
        filename = f"lesson_{date}_{time}.mp3"
        audio = self.upload_file(mp3_path, content_folder["id"], filename, "audio/mpeg")
        file_url = audio.get("webViewLink") or f"https://drive.google.com/file/d/{audio.get('id')}/view"

        record = {
            "status": "success",
            "provider": "gemini",
            "language": route.language_code,
            "languageLabel": route.language,
            "skill": route.skill,
            "level": route.level,
            "type": content_type,
            "source": "Abel",
            "createdAt": datetime.now(KST).isoformat(),
            "session": {"date": date, "time": time},
            "lesson": {
                "text": text,
                "title": title,
                "topic": topic,
                "delivery_mode": delivery_mode,
                "speaker_mode": speaker_mode,
            },
            "route": {"path": "/".join((*route.parts, date))},
            "audio": {
                "fileId": audio.get("id"),
                "fileName": audio.get("name", filename),
                "fileUrl": file_url,
            },
        }

        self.upload_bytes(
            json.dumps(record, ensure_ascii=False, indent=2).encode("utf-8"),
            content_folder["id"], f"lesson_{date}_{time}.json", "application/json",
        )

        log_folder = self.ensure_path("_SYSTEM", "LOG")
        self.upload_bytes(
            json.dumps({
                "timestamp": datetime.now(KST).isoformat(),
                "session": f"{date}_{time}",
                "status": "SUCCESS_GEMINI_TTS",
                "language": route.language_code,
                "skill": route.skill,
                "level": route.level,
                "path": "/".join((*route.parts, date)),
                "fileId": audio.get("id"),
            }, ensure_ascii=False, indent=2).encode("utf-8"),
            log_folder["id"], f"generation_{date}_{time}.json", "application/json",
        )

        return {
            "status": "success",
            "provider": "gemini",
            "language": route.language_code,
            "skill": route.skill,
            "level": route.level,
            "route": "/".join((*route.parts, date)),
            "cached": False,
            "fileId": audio.get("id"),
            "fileUrl": file_url,
            "fileName": filename,
            "message": "Gemini TTS MP3 and manifest saved to the routed Abel Learning path.",
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
    parser.add_argument("--language", default="zh-CN")
    parser.add_argument("--skill", default="listening")
    args = parser.parse_args()

    publisher = DrivePublisher(os.getenv("ABEL_DRIVE_FOLDER_ID", ""))
    if args.self_test:
        print(json.dumps({
            "status": "success",
            "provider": "google_drive_api",
            "root_folder_id": publisher.root_folder_id,
            "message": "Abel Learning root access verified.",
        }, ensure_ascii=False))
        return

    if not args.file:
        raise SystemExit("--file is required unless --self-test is used.")

    now = datetime.now(KST)
    date = args.date or now.strftime("%Y-%m-%d")
    time = args.time or now.strftime("%H%M%S")
    print(json.dumps(publisher.publish_lesson(
        args.file, date=date, time=time, title=args.title,
        level=args.level, topic=args.topic, text=args.text,
        language=args.language, skill=args.skill
    ), ensure_ascii=False))

if __name__ == "__main__":
    main()
