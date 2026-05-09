# Cinematic Collections

Kodi addon that lets you build your own collections mixing movies and TV shows
from your library, in the order you choose. Useful for franchises that span
both formats — Marvel Cinematic Universe, Star Wars, the Wizarding World, the
DC Extended Universe — or for any custom list you want to keep around (a
"to-watch with my partner" list, "best of the year", etc.).

Built and tested on Kodi Omega (v21).

## What it does

- Adds a context-menu entry "Add to collection…" on every movie and TV show
  in your library.
- Provides a video plugin (Add-ons → Video add-ons → Cinematic Collections)
  where you create, browse, rename and delete collections.
- A collection's contents are rendered as a normal Kodi list — movies play
  directly, TV shows drill down into seasons/episodes like in the standard
  library. Watched state is always fresh.
- Items keep the order in which you add them; reorder via "Move up" / "Move
  down" in the context menu of each item.

## Installing

Until this is published in a Kodi addon repository, install from a zip:

1. Download a release zip from the
   [Releases page](https://github.com/neverbot/plugin.video.cinematic.collections/releases)
   (or `git archive` your own).
2. In Kodi: Settings → Add-ons → Install from zip file → pick the file.
3. Kodi will install the addon and its context-menu hook automatically.

You can also drop the repository directly into Kodi's `addons/` directory
and restart Kodi (handy for development — see below).

## Using

**Create your first collection**: in the Kodi library, navigate to any movie
or TV show, open its context menu (key `c`, right-click, or the equivalent on
your remote), pick "Add to collection…", then "+ Create new collection". Give
it a name. The item is added.

**Add more items**: same context menu on any movie/TV show, pick the
collection from the list.

**Browse a collection**: Add-ons → Video add-ons → Cinematic Collections →
pick a collection. Movies and TV shows show up mixed in the order you added
them.

**Reorder**: open the context menu on an item inside a collection. "Move up"
and "Move down" reorder it relative to its neighbours.

**Remove an item**: same context menu, "Remove from collection".

**Refresh metadata**: artwork, plot, etc. are cached when you add an item.
If you re-scrape something and want the collection to reflect the new data,
right-click the item or the whole collection and pick "Refresh metadata".

## How it stores things

A single JSON file under your Kodi profile:

```
<profile>/addon_data/plugin.video.cinematic.collections/collections.json
```

Each item caches enough metadata (title, year, art, plot, file path, etc.) to
render the listing without hitting the library every time. Watched state is
read fresh on every open via two cheap bulk JSON-RPC calls — so the watched
indicators are always current, but everything else is cached and the addon
opens instantly even on Kodi setups using a remote MariaDB shared library.

## Development

```sh
git clone git@github.com:neverbot/plugin.video.cinematic.collections.git
ln -s "$PWD/plugin.video.cinematic.collections" \
      "$HOME/Library/Application Support/Kodi/addons/plugin.video.cinematic.collections"
```

(Adjust the addon path for your platform.) Restart Kodi or use Settings →
Add-ons → My add-ons → Cinematic Collections → Disable / Enable to pick up
Python changes — Kodi caches `.pyc` files in memory.

## License

MIT — see [LICENSE](LICENSE).
