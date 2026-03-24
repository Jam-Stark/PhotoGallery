#!/usr/bin/env python3
"""Generate static gallery data from Google Drive for frontend consumption.

Usage:
  GDRIVE_API_KEY=... ROOT_FOLDER_ID=... python scripts_generate_gallery_data.py
"""

from __future__ import annotations

import json
import os
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Dict, List

API_BASE = "https://www.googleapis.com/drive/v3/files"
DEFAULT_OUTPUT = "gallery-data.json"


def _require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        print(f"Missing required environment variable: {name}", file=sys.stderr)
        sys.exit(1)
    return value


def drive_files_query(api_key: str, query: str, fields: str, order_by: str, page_size: int = 200) -> List[Dict]:
    all_files: List[Dict] = []
    page_token = None

    while True:
        params = {
            "key": api_key,
            "q": query,
            "fields": f"nextPageToken, files({fields})",
            "orderBy": order_by,
            "supportsAllDrives": "true",
            "includeItemsFromAllDrives": "true",
            "pageSize": str(page_size),
        }
        if page_token:
            params["pageToken"] = page_token

        url = f"{API_BASE}?{urllib.parse.urlencode(params)}"
        with urllib.request.urlopen(url) as resp:
            payload = json.loads(resp.read().decode("utf-8"))

        all_files.extend(payload.get("files", []))
        page_token = payload.get("nextPageToken")
        if not page_token:
            break

    return all_files


def list_albums(api_key: str, root_folder_id: str) -> List[Dict]:
    query = (
        f"'{root_folder_id}' in parents and "
        "mimeType = 'application/vnd.google-apps.folder' and trashed = false"
    )
    albums = drive_files_query(
        api_key=api_key,
        query=query,
        fields="id,name",
        order_by="name_natural",
    )
    return [{"id": album["id"], "name": album["name"]} for album in albums]


def list_photos(api_key: str, folder_id: str) -> List[Dict]:
    query = f"'{folder_id}' in parents and mimeType contains 'image/' and trashed = false"
    photos = drive_files_query(
        api_key=api_key,
        query=query,
        fields="id,createdTime,imageMediaMetadata(width,height),thumbnailLink",
        order_by="createdTime desc",
    )

    normalized = []
    for photo in photos:
        metadata = photo.get("imageMediaMetadata") or {}
        normalized.append(
            {
                "id": photo.get("id"),
                "createdTime": photo.get("createdTime"),
                "thumbnailLink": photo.get("thumbnailLink"),
                "imageMediaMetadata": {
                    "width": metadata.get("width"),
                    "height": metadata.get("height"),
                },
            }
        )
    return normalized


def main() -> None:
    api_key = _require_env("GDRIVE_API_KEY")
    root_folder_id = _require_env("ROOT_FOLDER_ID")
    output_path = os.getenv("OUTPUT_PATH", DEFAULT_OUTPUT)

    albums = list_albums(api_key, root_folder_id)

    photos_by_album: Dict[str, List[Dict]] = {}
    all_photos: Dict[str, Dict] = {}

    root_photos = list_photos(api_key, root_folder_id)
    photos_by_album[root_folder_id] = root_photos
    for photo in root_photos:
        if photo["id"]:
            all_photos[photo["id"]] = photo

    for album in albums:
        photos = list_photos(api_key, album["id"])
        photos_by_album[album["id"]] = photos
        for photo in photos:
            if photo["id"]:
                all_photos[photo["id"]] = photo

    data = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "rootFolderId": root_folder_id,
        "albums": albums,
        "photosByAlbum": photos_by_album,
        "allPhotos": sorted(
            all_photos.values(),
            key=lambda item: item.get("createdTime") or "",
            reverse=True,
        ),
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")

    print(f"Wrote {output_path} with {len(data['albums'])} albums and {len(data['allPhotos'])} photos.")


if __name__ == "__main__":
    main()
