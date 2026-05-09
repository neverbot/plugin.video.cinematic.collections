"""Plugin entry point. Routes URL params to the appropriate handler."""

import sys
import urllib.parse

import xbmc
import xbmcplugin

from resources.lib import actions, ui


def _parse_params() -> dict:
    qs = sys.argv[2][1:] if len(sys.argv) > 2 and sys.argv[2].startswith("?") else ""
    if not qs:
        return {}
    return {k: v[0] for k, v in urllib.parse.parse_qs(qs).items() if v}


def main() -> None:
    params = _parse_params()
    action = params.get("action")

    if not action:
        ui.show_collections()
        return

    if action == "show_collection":
        ui.show_collection(params["cid"])
        return

    if action == "create_collection":
        actions.create_collection()
        # Folder click renders the listing; RunPlugin (handle == -1) refreshes
        # the active container in place.
        if int(sys.argv[1]) >= 0:
            ui.show_collections()
        else:
            xbmc.executebuiltin("Container.Refresh")
        return

    if action == "rename_collection":
        actions.rename_collection(params["cid"])
        return

    if action == "delete_collection":
        actions.delete_collection(params["cid"])
        return

    if action == "add_to_collection":
        actions.add_to_collection(params["dbtype"], int(params["dbid"]))
        return

    if action == "remove_item":
        actions.remove_item(params["cid"], params["dbtype"], int(params["dbid"]))
        return

    if action == "move_item":
        actions.move_item(
            params["cid"], params["dbtype"], int(params["dbid"]),
            int(params["dir"]),
        )
        return

    if action == "refresh_item":
        actions.refresh_item(params["cid"], params["dbtype"], int(params["dbid"]))
        return

    if action == "refresh_collection":
        actions.refresh_collection(params["cid"])
        return

    if action == "noop":
        xbmcplugin.endOfDirectory(int(sys.argv[1]), succeeded=False)
        return


if __name__ == "__main__":
    main()
