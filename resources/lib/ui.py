"""Listing builders for the plugin's directory views."""

import random
import sys
import urllib.parse

import xbmcgui
import xbmcplugin
import xbmcaddon

from . import library, storage


_ADDON = xbmcaddon.Addon()
_HANDLE = int(sys.argv[1]) if len(sys.argv) > 1 else -1
_BASE = sys.argv[0] if sys.argv else "plugin://plugin.video.cinematic.collections/"


def _t(string_id: int) -> str:
    return _ADDON.getLocalizedString(string_id)


def _url(**params) -> str:
    return f"{_BASE}?{urllib.parse.urlencode(params)}"


def _menu_refresh_collection(cid: str) -> tuple:
    return (_t(30116),
            f"RunPlugin({_url(action='refresh_collection', cid=cid)})")


def _menu_refresh_item(cid: str, dbtype: str, dbid: int) -> tuple:
    return (_t(30116),
            f"RunPlugin({_url(action='refresh_item', cid=cid, dbtype=dbtype, dbid=dbid)})")


def show_collections() -> None:
    """Top-level: list of collections + 'create new' entry."""
    collections = storage.list_collections()

    if not collections:
        create_li = xbmcgui.ListItem(label=f"[B]+ {_t(30101)}[/B]")
        create_li.setArt({"icon": "DefaultAddSource.png"})
        xbmcplugin.addDirectoryItem(
            handle=_HANDLE,
            url=_url(action="create_collection"),
            listitem=create_li,
            isFolder=False,
        )

    for col in collections:
        li = xbmcgui.ListItem(label=col["name"])
        li.setArt(_collection_art(col))
        li.addContextMenuItems([
            (_t(30101),
             f"RunPlugin({_url(action='create_collection')})"),
            _menu_refresh_collection(col["id"]),
            (_t(30108),
             f"RunPlugin({_url(action='rename_collection', cid=col['id'])})"),
            (_t(30109),
             f"RunPlugin({_url(action='delete_collection', cid=col['id'])})"),
        ])
        xbmcplugin.addDirectoryItem(
            handle=_HANDLE,
            url=_url(action="show_collection", cid=col["id"]),
            listitem=li,
            isFolder=True,
        )

    xbmcplugin.addSortMethod(_HANDLE, xbmcplugin.SORT_METHOD_NONE)
    xbmcplugin.endOfDirectory(_HANDLE)


def show_collection(cid: str) -> None:
    """Show items of a single collection in user-defined order.

    Renders from cached metadata in the JSON store — no per-item JSON-RPC.
    Watched/progress state is layered on top from two cheap bulk RPCs that
    only request playcount/lastplayed-style fields.

    Items added before metadata caching (legacy) are auto-migrated on first
    render: we resolve them once via the heavier bulk fetch, write their
    metadata back to the JSON, and continue. Subsequent renders are instant.
    """
    col = storage.get_collection(cid)
    if not col:
        xbmcplugin.endOfDirectory(_HANDLE, succeeded=False)
        return

    if not col["items"]:
        empty = xbmcgui.ListItem(label=f"[I]{_t(30112)}[/I]")
        empty.setArt({"icon": "DefaultFolder.png"})
        xbmcplugin.addDirectoryItem(
            handle=_HANDLE,
            url=_url(action="noop"),
            listitem=empty,
            isFolder=False,
        )

    # Bulk-fetch watched-state only — small payload, fresh every render.
    watched_movies = (
        library.get_watched_movies_indexed()
        if any(it["type"] == "movie" for it in col["items"]) else {}
    )
    watched_tvshows = (
        library.get_watched_tvshows_indexed()
        if any(it["type"] == "tvshow" for it in col["items"]) else {}
    )

    total = len(col["items"])
    for idx, item in enumerate(col["items"]):
        meta = item.get("metadata") or {}
        if not meta:
            # Migration didn't recover this one → library entry is gone.
            li = _stub_listitem(item)
            url = _url(action="noop")
            is_folder = False
        elif item["type"] == "movie":
            watched = watched_movies.get(item["dbid"], {})
            li = _movie_listitem(item, meta, watched)
            url = meta.get("file", "")
            is_folder = False
        else:
            watched = watched_tvshows.get(item["dbid"], {})
            li = _tvshow_listitem(item, meta, watched)
            url = f"videodb://tvshows/titles/{item['dbid']}/"
            is_folder = True

        ctx = []
        if idx > 0:
            ctx.append((
                _t(30106),
                f"RunPlugin({_url(action='move_item', cid=cid, dbtype=item['type'], dbid=item['dbid'], dir='-1')})",
            ))
        if idx < total - 1:
            ctx.append((
                _t(30107),
                f"RunPlugin({_url(action='move_item', cid=cid, dbtype=item['type'], dbid=item['dbid'], dir='1')})",
            ))
        ctx.append((
            _t(30105),
            f"RunPlugin({_url(action='remove_item', cid=cid, dbtype=item['type'], dbid=item['dbid'])})",
        ))
        ctx.append(_menu_refresh_item(cid, item["type"], item["dbid"]))
        ctx.append(_menu_refresh_collection(cid))
        li.addContextMenuItems(ctx)

        xbmcplugin.addDirectoryItem(
            handle=_HANDLE, url=url, listitem=li, isFolder=is_folder,
        )

    # SORT_METHOD_NONE preserves the order in which we added items.
    xbmcplugin.addSortMethod(_HANDLE, xbmcplugin.SORT_METHOD_NONE)
    # Declare 'movies' so skins offer the rich view modes (Posters, Wall,
    # Fanart, …). Mixed movie+tvshow items still render correctly: each
    # ListItem carries its own mediatype and art.
    xbmcplugin.setContent(_HANDLE, "movies")
    xbmcplugin.endOfDirectory(_HANDLE)


def _movie_listitem(item: dict, meta: dict, watched: dict) -> xbmcgui.ListItem:
    li = xbmcgui.ListItem(label=meta.get("title") or meta.get("originaltitle") or "")
    li.setIsFolder(False)
    li.setProperty("IsPlayable", "true")
    li.setArt(_normalize_art(meta.get("art") or {}))
    tag = li.getVideoInfoTag()
    tag.setMediaType("movie")
    tag.setDbId(int(item["dbid"]))
    _apply_common(tag, meta)
    if meta.get("tagline"):
        tag.setTagLine(meta["tagline"])
    if meta.get("runtime"):
        tag.setDuration(int(meta["runtime"]))
    _apply_watched(tag, watched)
    return li


def _tvshow_listitem(item: dict, meta: dict, watched: dict) -> xbmcgui.ListItem:
    li = xbmcgui.ListItem(label=meta.get("title") or "")
    li.setIsFolder(True)
    li.setArt(_normalize_art(meta.get("art") or {}))
    tag = li.getVideoInfoTag()
    tag.setMediaType("tvshow")
    tag.setDbId(int(item["dbid"]))
    _apply_common(tag, meta)
    total_eps = watched.get("episode") or meta.get("episode")
    watched_eps = watched.get("watchedepisodes")
    if total_eps is not None:
        tag.setEpisode(int(total_eps))
    if watched_eps is not None:
        # Skin-side progress display ("12/24 watched") reads these properties.
        li.setProperty("TotalEpisodes", str(int(total_eps or 0)))
        li.setProperty("WatchedEpisodes", str(int(watched_eps)))
        unwatched = max(0, int(total_eps or 0) - int(watched_eps))
        li.setProperty("UnWatchedEpisodes", str(unwatched))
    _apply_watched(tag, watched)
    return li


def _apply_common(tag, meta: dict) -> None:
    if meta.get("title"):
        tag.setTitle(meta["title"])
    if meta.get("originaltitle"):
        tag.setOriginalTitle(meta["originaltitle"])
    if meta.get("year"):
        tag.setYear(int(meta["year"]))
    if meta.get("plot"):
        tag.setPlot(meta["plot"])
    if meta.get("plotoutline"):
        tag.setPlotOutline(meta["plotoutline"])
    if meta.get("genre"):
        tag.setGenres(list(meta["genre"]))
    if meta.get("rating"):
        tag.setRating(float(meta["rating"]))
    if meta.get("mpaa"):
        tag.setMpaa(meta["mpaa"])
    if meta.get("studio"):
        tag.setStudios(list(meta["studio"]))
    if meta.get("director"):
        tag.setDirectors(list(meta["director"]))
    if meta.get("writer"):
        tag.setWriters(list(meta["writer"]))
    if meta.get("premiered"):
        tag.setPremiered(meta["premiered"])
    uniq = meta.get("uniqueid") or {}
    if uniq:
        tag.setUniqueIDs({k: str(v) for k, v in uniq.items() if v})


def _apply_watched(tag, watched: dict) -> None:
    if not watched:
        return
    if watched.get("playcount") is not None:
        tag.setPlaycount(int(watched["playcount"]))
    if watched.get("lastplayed"):
        tag.setLastPlayed(watched["lastplayed"])
    resume = watched.get("resume") or {}
    pos = resume.get("position", 0)
    total = resume.get("total", 0)
    if pos and total:
        tag.setResumePoint(float(pos), float(total))


def _collection_art(col: dict) -> dict:
    """Pick a random item with cached metadata and use its art.

    Reads from our JSON cache only — no JSON-RPC. Re-rendered on every visit,
    so artwork rotates naturally without a background service. Falls back to
    the default playlist icon if no items have cached art yet (legacy items
    added before metadata caching was introduced).
    """
    default = {"icon": "DefaultVideoPlaylists.png",
               "thumb": "DefaultVideoPlaylists.png"}
    candidates = [it for it in (col.get("items") or [])
                  if (it.get("metadata") or {}).get("art")]
    if not candidates:
        return default
    chosen = random.choice(candidates)
    return _normalize_art(chosen["metadata"]["art"]) or default


def _normalize_art(art: dict) -> dict:
    """Fill in missing keys that some skins look up first.

    Kodi's GetMovieDetails returns 'poster' and 'fanart' but rarely 'thumb' /
    'icon'. Without those, list-view skins fall back to the video file's
    auto-generated frame thumbnail. We alias poster→thumb (and thumb→icon)
    so any skin gets a poster wherever it expects art.
    """
    out = dict(art)
    fallback = (out.get("poster") or out.get("landscape")
                or out.get("banner") or out.get("thumb"))
    if fallback:
        # Force-overwrite (not setdefault): when the URL is a file path with
        # IsPlayable, Kodi auto-generates a frame thumbnail and uses it for
        # 'thumb' unless we explicitly set our own.
        out["thumb"] = fallback
        out["icon"] = fallback
    return out


def _stub_listitem(item: dict) -> xbmcgui.ListItem:
    title = item.get("title") or _t(30115)
    label = f"[COLOR red]{title}[/COLOR] {_t(30113)}"
    li = xbmcgui.ListItem(label=label)
    li.setArt({"icon": "DefaultIconError.png"})
    return li
