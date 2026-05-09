"""Persistent storage for collections.

The store is a single JSON file under the addon profile directory:
    special://profile/addon_data/plugin.video.cinematic.collections/collections.json

Schema (version 1):
    {
        "version": 1,
        "collections": [
            {
                "id": "<uuid4>",
                "name": "<user string>",
                "created_at": "<iso8601>",
                "items": [
                    {
                        "type": "movie" | "tvshow",
                        "dbid": <int>,
                        "uniqueid": {"imdb": "...", "tmdb": "..."},
                        "title": "<str>",
                        "year": <int|null>,
                        "added_at": "<iso8601>"
                    },
                    ...
                ]
            },
            ...
        ]
    }
"""

import json
import os
import threading
import time
import uuid
from datetime import datetime, timezone

import xbmcaddon
import xbmcvfs


_ADDON = xbmcaddon.Addon()
_PROFILE = xbmcvfs.translatePath(_ADDON.getAddonInfo("profile"))
_STORE_PATH = os.path.join(_PROFILE, "collections.json")
_LOCK = threading.Lock()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _ensure_profile() -> None:
    if not os.path.isdir(_PROFILE):
        os.makedirs(_PROFILE, exist_ok=True)


def load() -> dict:
    _ensure_profile()
    if not os.path.isfile(_STORE_PATH):
        return {"version": 1, "collections": []}
    try:
        with open(_STORE_PATH, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return {"version": 1, "collections": []}
    data.setdefault("version", 1)
    data.setdefault("collections", [])
    return data


def save(data: dict) -> None:
    _ensure_profile()
    tmp = f"{_STORE_PATH}.tmp.{os.getpid()}.{int(time.time() * 1000)}"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
    os.replace(tmp, _STORE_PATH)


def list_collections() -> list:
    return load()["collections"]


def get_collection(cid: str) -> dict | None:
    for c in list_collections():
        if c["id"] == cid:
            return c
    return None


def create_collection(name: str) -> dict:
    name = (name or "").strip()
    if not name:
        raise ValueError("empty name")
    with _LOCK:
        data = load()
        col = {
            "id": uuid.uuid4().hex,
            "name": name,
            "created_at": _now_iso(),
            "items": [],
        }
        data["collections"].append(col)
        save(data)
        return col


def rename_collection(cid: str, new_name: str) -> bool:
    new_name = (new_name or "").strip()
    if not new_name:
        return False
    with _LOCK:
        data = load()
        for c in data["collections"]:
            if c["id"] == cid:
                c["name"] = new_name
                save(data)
                return True
        return False


def delete_collection(cid: str) -> bool:
    with _LOCK:
        data = load()
        before = len(data["collections"])
        data["collections"] = [c for c in data["collections"] if c["id"] != cid]
        if len(data["collections"]) == before:
            return False
        save(data)
        return True


def add_item(cid: str, item: dict) -> str:
    """Append item to collection. Returns 'added', 'duplicate' or 'no_collection'."""
    with _LOCK:
        data = load()
        for c in data["collections"]:
            if c["id"] != cid:
                continue
            for existing in c["items"]:
                if existing["type"] == item["type"] and existing["dbid"] == item["dbid"]:
                    return "duplicate"
            entry = dict(item)
            entry["added_at"] = _now_iso()
            c["items"].append(entry)
            save(data)
            return "added"
        return "no_collection"


def remove_item(cid: str, dbtype: str, dbid: int) -> bool:
    with _LOCK:
        data = load()
        for c in data["collections"]:
            if c["id"] != cid:
                continue
            before = len(c["items"])
            c["items"] = [
                it for it in c["items"]
                if not (it["type"] == dbtype and it["dbid"] == dbid)
            ]
            if len(c["items"]) == before:
                return False
            save(data)
            return True
        return False


def set_item_metadata(cid: str, dbtype: str, dbid: int, metadata: dict) -> bool:
    """Replace the cached metadata for a single item."""
    with _LOCK:
        data = load()
        for c in data["collections"]:
            if c["id"] != cid:
                continue
            for it in c["items"]:
                if it["type"] == dbtype and it["dbid"] == dbid:
                    it["metadata"] = metadata
                    save(data)
                    return True
        return False


def bulk_set_metadata(cid: str, metadata_by_key: dict) -> int:
    """Update metadata for many items in one shot.

    `metadata_by_key` keys are (dbtype, dbid) tuples; values are metadata dicts.
    Returns the number of items updated.
    """
    if not metadata_by_key:
        return 0
    with _LOCK:
        data = load()
        updated = 0
        for c in data["collections"]:
            if c["id"] != cid:
                continue
            for it in c["items"]:
                key = (it["type"], it["dbid"])
                if key in metadata_by_key:
                    it["metadata"] = metadata_by_key[key]
                    updated += 1
            if updated:
                save(data)
            return updated
        return 0


def move_item(cid: str, dbtype: str, dbid: int, direction: int) -> bool:
    """direction: -1 (up) or +1 (down)."""
    if direction not in (-1, 1):
        return False
    with _LOCK:
        data = load()
        for c in data["collections"]:
            if c["id"] != cid:
                continue
            items = c["items"]
            for idx, it in enumerate(items):
                if it["type"] == dbtype and it["dbid"] == dbid:
                    new_idx = idx + direction
                    if new_idx < 0 or new_idx >= len(items):
                        return False
                    items[idx], items[new_idx] = items[new_idx], items[idx]
                    save(data)
                    return True
        return False
