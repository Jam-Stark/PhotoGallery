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
from pathlib import Path
from typing import Dict, List

API_BASE = "https://www.googleapis.com/drive/v3/files"
DEFAULT_OUTPUT = "gallery-data.json"
DEFAULT_ASSETS_DIR = "photos"
DEFAULT_ASSET_WIDTH = 1200


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


def drive_thumbnail_url(file_id: str, width: int) -> str:
    return (
        "https://drive.google.com/thumbnail?"
        f"id={urllib.parse.quote(file_id)}&sz=w{width}"
    )


def sized_thumbnail_link(thumbnail_link: str, width: int) -> str:
    if "=s" in thumbnail_link:
        base, _sep, _size = thumbnail_link.rpartition("=s")
        return f"{base}=s{width}"
    return thumbnail_link


def cache_photo_asset(photo: Dict, assets_dir: str, width: int, refresh: bool) -> str | None:
    file_id = photo.get("id")
    if not file_id:
        return None

    asset_rel_path = f"{assets_dir.rstrip('/')}/{file_id}.jpg"
    asset_path = Path(asset_rel_path)

    if asset_path.exists() and asset_path.stat().st_size > 0 and not refresh:
        return asset_rel_path

    asset_path.parent.mkdir(parents=True, exist_ok=True)

    candidates = []
    thumbnail_link = photo.get("thumbnailLink")
    if thumbnail_link:
        candidates.append(sized_thumbnail_link(thumbnail_link, width))
    candidates.append(drive_thumbnail_url(file_id, width))

    for url in candidates:
        try:
            request = urllib.request.Request(
                url,
                headers={"User-Agent": "PhotoGallery/1.0"},
            )
            with urllib.request.urlopen(request, timeout=45) as resp:
                content_type = resp.headers.get("Content-Type", "")
                data = resp.read()

            if not data or not content_type.startswith("image/"):
                raise ValueError(f"unexpected content type: {content_type or 'unknown'}")

            tmp_path = asset_path.with_suffix(".tmp")
            tmp_path.write_bytes(data)
            os.replace(tmp_path, asset_path)
            return asset_rel_path
        except Exception as exc:
            print(f"Warning: failed to cache {file_id} from {url}: {exc}", file=sys.stderr)

    return asset_rel_path if asset_path.exists() and asset_path.stat().st_size > 0 else None


def prepare_static_photo(photo: Dict, assets_dir: str, width: int, refresh_assets: bool) -> None:
    asset_path = cache_photo_asset(photo, assets_dir, width, refresh_assets)
    if asset_path:
        photo["assetPath"] = asset_path

    # Keep thumbnailLink as a browser fallback while GitHub Pages cached assets
    # catch up. The frontend still prefers assetPath when it exists.


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
        if not photo.get("thumbnailLink"):
            continue

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
    assets_dir = os.getenv("ASSETS_DIR", DEFAULT_ASSETS_DIR)
    asset_width = int(os.getenv("ASSET_WIDTH", str(DEFAULT_ASSET_WIDTH)))
    refresh_assets = os.getenv("REFRESH_ASSETS", "").lower() in {"1", "true", "yes"}

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

    for photos in photos_by_album.values():
        for photo in photos:
            prepare_static_photo(photo, assets_dir, asset_width, refresh_assets)

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
