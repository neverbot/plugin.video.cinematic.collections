"""Actions invoked via RunPlugin from the context menu and from listings.

These do their work and refresh the current container; they don't render
their own listings.
"""

import xbmc
import xbmcgui
import xbmcaddon

from . import library, storage


_ADDON = xbmcaddon.Addon()


def _t(string_id: int) -> str:
    return _ADDON.getLocalizedString(string_id)


def _notify(message: str) -> None:
    xbmcgui.Dialog().notification(_ADDON.getAddonInfo("name"), message,
                                  xbmcgui.NOTIFICATION_INFO, 3000)


def _refresh() -> None:
    xbmc.executebuiltin("Container.Refresh")


def create_collection() -> None:
    """Prompt for a name and persist a new collection.

    Caller is responsible for refreshing or re-rendering the listing.
    """
    name = xbmcgui.Dialog().input(_t(30102))
    if not name:
        return
    storage.create_collection(name)


def rename_collection(cid: str) -> None:
    col = storage.get_collection(cid)
    if not col:
        return
    name = xbmcgui.Dialog().input(_t(30102), defaultt=col["name"])
    if not name or name == col["name"]:
        return
    storage.rename_collection(cid, name)
    _refresh()


def delete_collection(cid: str) -> None:
    col = storage.get_collection(cid)
    if not col:
        return
    if not xbmcgui.Dialog().yesno(_ADDON.getAddonInfo("name"),
                                  _t(30110) % col["name"]):
        return
    storage.delete_collection(cid)
    _refresh()


def add_to_collection(dbtype: str, dbid: int) -> None:
    """Triggered from the global context menu on a movie/tvshow."""
    if dbtype not in ("movie", "tvshow") or not dbid:
        return

    if dbtype == "movie":
        details = library.get_movie(dbid)
    else:
        details = library.get_tvshow(dbid)
    if not details:
        _notify(_t(30115))
        return

    collections = storage.list_collections()
    create_label = f"[B]+ {_t(30101)}[/B]"
    options = [create_label] + [c["name"] for c in collections]

    selected = xbmcgui.Dialog().select(_t(30100), options)
    if selected < 0:
        return

    if selected == 0:
        name = xbmcgui.Dialog().input(_t(30102))
        if not name:
            return
        col = storage.create_collection(name)
    else:
        col = collections[selected - 1]

    item = {
        "type": dbtype,
        "dbid": int(dbid),
        "uniqueid": details.get("uniqueid") or {},
        "title": details.get("title") or details.get("originaltitle") or "",
        "year": details.get("year"),
        "metadata": library.extract_metadata(details, dbtype),
    }
    result = storage.add_item(col["id"], item)
    if result == "added":
        _notify(_t(30103) % col["name"])
    elif result == "duplicate":
        _notify(_t(30104) % col["name"])


def remove_item(cid: str, dbtype: str, dbid: int) -> None:
    storage.remove_item(cid, dbtype, int(dbid))
    _refresh()


def move_item(cid: str, dbtype: str, dbid: int, direction: int) -> None:
    storage.move_item(cid, dbtype, int(dbid), int(direction))
    _refresh()


def refresh_item(cid: str, dbtype: str, dbid: int) -> None:
    """Re-query the library for one item and overwrite its cached metadata."""
    if dbtype == "movie":
        details = library.get_movie(int(dbid))
    elif dbtype == "tvshow":
        details = library.get_tvshow(int(dbid))
    else:
        return
    if not details:
        _notify(_t(30115))
        return
    metadata = library.extract_metadata(details, dbtype)
    if storage.set_item_metadata(cid, dbtype, int(dbid), metadata):
        _notify(_t(30117))
        _refresh()


def refresh_collection(cid: str) -> None:
    """Re-query every item in the collection in one bulk pair of RPCs.

    Shows a non-blocking background progress dialog while the heavy bulk
    fetch is in flight, so the user gets immediate feedback that something
    is happening (otherwise the addon appears frozen for ~1 s).
    """
    col = storage.get_collection(cid)
    if not col:
        return

    progress = xbmcgui.DialogProgressBG()
    progress.create(_ADDON.getAddonInfo("name"), _t(30119) % col["name"])
    try:
        progress.update(15)
        needs_movies = any(it["type"] == "movie" for it in col["items"])
        needs_tvshows = any(it["type"] == "tvshow" for it in col["items"])
        movie_idx = library.get_all_movies_indexed() if needs_movies else {}
        progress.update(55)
        tvshow_idx = library.get_all_tvshows_indexed() if needs_tvshows else {}
        progress.update(80)

        updates = {}
        for it in col["items"]:
            idx = movie_idx if it["type"] == "movie" else tvshow_idx
            details = library.resolve(it, movie_idx, tvshow_idx) if idx else None
            if details:
                updates[(it["type"], it["dbid"])] = library.extract_metadata(
                    details, it["type"]
                )
        n = storage.bulk_set_metadata(cid, updates)
        progress.update(100)
    finally:
        progress.close()

    _notify(_t(30118) % n)
    _refresh()
