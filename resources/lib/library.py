"""Thin wrapper around Kodi's JSON-RPC for the bits we need."""

import json
from datetime import datetime, timezone

import xbmc


_MOVIE_PROPS = [
    "title", "year", "genre", "rating", "plot", "plotoutline",
    "runtime", "playcount", "lastplayed", "art", "uniqueid",
    "file", "dateadded", "mpaa", "studio", "director", "writer",
    "originaltitle", "tagline",
]
_TVSHOW_PROPS = [
    "title", "year", "genre", "rating", "plot", "playcount",
    "lastplayed", "art", "uniqueid", "file", "dateadded",
    "mpaa", "studio", "originaltitle", "premiered", "episode",
    "season",
]


def _rpc(method: str, params: dict) -> dict:
    payload = {
        "jsonrpc": "2.0",
        "method": method,
        "params": params,
        "id": 1,
    }
    raw = xbmc.executeJSONRPC(json.dumps(payload))
    try:
        return json.loads(raw)
    except ValueError:
        return {}


def get_movie(dbid: int) -> dict | None:
    res = _rpc("VideoLibrary.GetMovieDetails",
               {"movieid": int(dbid), "properties": _MOVIE_PROPS})
    return res.get("result", {}).get("moviedetails")


def get_tvshow(dbid: int) -> dict | None:
    res = _rpc("VideoLibrary.GetTVShowDetails",
               {"tvshowid": int(dbid), "properties": _TVSHOW_PROPS})
    return res.get("result", {}).get("tvshowdetails")


# Properties needed to render watched/progress state. Cheap to fetch in bulk.
_WATCHED_MOVIE_PROPS = ["playcount", "lastplayed", "resume"]
_WATCHED_TVSHOW_PROPS = ["playcount", "lastplayed", "watchedepisodes", "episode"]


def get_watched_movies_indexed() -> dict:
    """Bulk-fetch only watched-state fields for every movie in the library.

    Tiny payload (~30 bytes/item) compared to a full GetMovies fetch.
    """
    res = _rpc("VideoLibrary.GetMovies", {"properties": _WATCHED_MOVIE_PROPS})
    return {m["movieid"]: m for m in res.get("result", {}).get("movies", []) or []}


def get_watched_tvshows_indexed() -> dict:
    res = _rpc("VideoLibrary.GetTVShows", {"properties": _WATCHED_TVSHOW_PROPS})
    return {s["tvshowid"]: s for s in res.get("result", {}).get("tvshows", []) or []}


def extract_metadata(details: dict, kind: str) -> dict:
    """Pick the static fields worth caching in our JSON.

    Excludes anything that changes with viewing (playcount, lastplayed, resume) —
    those come from get_watched_*_indexed at render time.
    """
    common = [
        "title", "originaltitle", "year", "plot", "plotoutline", "genre",
        "rating", "mpaa", "studio", "uniqueid", "art", "premiered",
    ]
    out = {k: details[k] for k in common if k in details}
    if kind == "movie":
        for k in ("tagline", "runtime", "director", "writer", "file"):
            if k in details:
                out[k] = details[k]
    elif kind == "tvshow":
        for k in ("episode", "season"):
            if k in details:
                out[k] = details[k]
    out["cached_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    return out


def get_all_movies_indexed() -> dict:
    """Return all movies as a dict keyed by movieid.

    One bulk call instead of N. Used to render listings of many items
    without N+1 round trips against MariaDB.
    """
    res = _rpc("VideoLibrary.GetMovies", {"properties": _MOVIE_PROPS})
    return {m["movieid"]: m for m in res.get("result", {}).get("movies", []) or []}


def get_all_tvshows_indexed() -> dict:
    res = _rpc("VideoLibrary.GetTVShows", {"properties": _TVSHOW_PROPS})
    return {s["tvshowid"]: s for s in res.get("result", {}).get("tvshows", []) or []}


def find_movie_by_uniqueid(uniqueid: dict, index: dict | None = None) -> dict | None:
    """Search every movie in the library for a matching uniqueid.

    Used as a fallback when a cached dbid no longer resolves. If `index`
    is provided (already-fetched movies dict), avoids an extra RPC.
    """
    if not uniqueid:
        return None
    movies = list(index.values()) if index is not None else (
        _rpc("VideoLibrary.GetMovies", {"properties": _MOVIE_PROPS})
        .get("result", {}).get("movies", []) or []
    )
    for m in movies:
        u = m.get("uniqueid", {}) or {}
        for key in ("imdb", "tmdb"):
            if key in uniqueid and key in u and uniqueid[key] and uniqueid[key] == u[key]:
                return m
    return None


def find_tvshow_by_uniqueid(uniqueid: dict, index: dict | None = None) -> dict | None:
    if not uniqueid:
        return None
    shows = list(index.values()) if index is not None else (
        _rpc("VideoLibrary.GetTVShows", {"properties": _TVSHOW_PROPS})
        .get("result", {}).get("tvshows", []) or []
    )
    for s in shows:
        u = s.get("uniqueid", {}) or {}
        for key in ("imdb", "tmdb", "tvdb"):
            if key in uniqueid and key in u and uniqueid[key] and uniqueid[key] == u[key]:
                return s
    return None


def resolve(item: dict,
            movie_index: dict | None = None,
            tvshow_index: dict | None = None) -> dict | None:
    """Look up the live library entry for a stored collection item.

    When the indexes are passed, the lookup is in-memory (no RPC). Without
    them, falls back to per-item RPC + a slow scan if the dbid drifted.
    """
    dbtype = item.get("type")
    dbid = item.get("dbid")
    uniqueid = item.get("uniqueid") or {}
    if dbtype == "movie":
        if movie_index is not None:
            cached = movie_index.get(dbid)
            if cached and _uniqueid_matches(cached.get("uniqueid"), uniqueid):
                return cached
            return find_movie_by_uniqueid(uniqueid, movie_index)
        details = get_movie(dbid) if dbid else None
        if details and _uniqueid_matches(details.get("uniqueid"), uniqueid):
            return details
        return find_movie_by_uniqueid(uniqueid)
    if dbtype == "tvshow":
        if tvshow_index is not None:
            cached = tvshow_index.get(dbid)
            if cached and _uniqueid_matches(cached.get("uniqueid"), uniqueid):
                return cached
            return find_tvshow_by_uniqueid(uniqueid, tvshow_index)
        details = get_tvshow(dbid) if dbid else None
        if details and _uniqueid_matches(details.get("uniqueid"), uniqueid):
            return details
        return find_tvshow_by_uniqueid(uniqueid)
    return None


def _uniqueid_matches(a: dict | None, b: dict | None) -> bool:
    if not a or not b:
        return True  # nothing to compare with → trust dbid
    for k in ("imdb", "tmdb", "tvdb"):
        if k in a and k in b and a[k] and b[k]:
            return a[k] == b[k]
    return True
