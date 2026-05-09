"""Context-menu entry point. Forwards the focused item to the plugin."""

import urllib.parse

import xbmc


_PLUGIN = "plugin://plugin.video.cinematic.collections/"


def main() -> None:
    dbid = xbmc.getInfoLabel("ListItem.DBID")
    dbtype = xbmc.getInfoLabel("ListItem.DBType")
    if not dbid or dbtype not in ("movie", "tvshow"):
        return
    qs = urllib.parse.urlencode({
        "action": "add_to_collection",
        "dbtype": dbtype,
        "dbid": dbid,
    })
    xbmc.executebuiltin(f"RunPlugin({_PLUGIN}?{qs})")


if __name__ == "__main__":
    main()
