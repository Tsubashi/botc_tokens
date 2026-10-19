# Token Tools for Blood on the Clocktower
A simple fan-made utility to help create custom tokens for the game Blood on the Clocktower.

![An example of tokens made by this utility](https://github.com/Tsubashi/botc_tokens-Examples/blob/31b118fc96e0f2aaa6b20d7547f2923a6c73ff34/example.jpg?raw=true)

## Installation
To use this tool, you will need to have Python 3.10 or newer installed on your computer. You can download it from the
[official website](https://www.python.org/downloads/).

Once you have Python installed, you can install these scripts using `pip`:
```bash
pip install botc_tokens
```
or manually by cloning this repository and running the following command in the root folder:
```bash
pip install .
```

We use [Wand](https://docs.wand-py.org/en/0.6.13/) to handle image manipulation, which requires the [ImageMagick](https://imagemagick.org/index.php) library to be installed on your 
system. Check the [wand install guide](https://docs.wand-py.org/en/0.6.13/guide/install.html) for details on how to get that set up.

**Note for Apple Silicon:** When running on Apple Silicon, Wand will not auto-detect the ImageMagick installation. 
You will need to set the `MAGICK_HOME` environment variable to your homebrew root, like so:
```bash
export MAGICK_HOME=/opt/homebrew/
```

## Usage
**For a full walkthrough and for more component packages, see the 
[example repository](https://github.com/Tsubashi/botc_tokens-Examples).**

The tool is run through its entrypoint `botc_tokens`. There are four working commands (`create`, `dump`, `migrate`,
and `pad-icons`) plus `version`. Use `--help` on any of them to see every option.

### Quick start
Give `create` a script JSON (a file or a URL) and it produces print-ready PDFs. You can export a script from the
[official script tool](https://script.bloodontheclocktower.com/) and pass its URL or the downloaded file:
```bash
botc_tokens create https://example.com/my-script.json -o printables
```
This writes `roles.pdf` and `reminders.pdf` into `printables/`. Characters listed by bare ID (such as
`"washerwoman"`) are filled in from the official data, and their icons are downloaded automatically. Characters you
define yourself are used as written; any field you leave out of an official character (its ability text, say) is
filled in from the official data.

If you build your script in Bloodstar, pass its save file instead. The format is detected
automatically:
```bash
botc_tokens create my-bloodstar-save.json -o printables
```

Icons are expected to carry transparent padding around the artwork, as the official icons do. Tightly cropped icons
are padded automatically when they are fetched, so homebrew art works without any preparation.

### Paper and sizes
All sizes are in millimeters. Pick a paper preset with `--paper-type` (`letter`, `legal`, `a4`, or `a5`; the default
is `letter`) or give exact dimensions with `--paper-size WIDTH HEIGHT`. The two options cannot be combined.
```bash
botc_tokens create script.json -o printables --paper-type a4
botc_tokens create script.json -o printables --paper-size 215.9 279.4 --margin-horizontal 5 --padding 1
```
Other options include `--dpi` (default 300), `--role-diameter` (46 mm), `--reminder-diameter` (26 mm),
`--margin-horizontal`, `--margin-vertical`, `--padding`, `--grid` (use a grid layout instead of close packing), and
`--skip-ability-text`.

### Keeping intermediate files and caching
By default the icons and individual token images are thrown away once the PDFs are made. Pass `-m` to keep them:
```bash
botc_tokens create script.json -o printables -m work
```
This leaves `work/icons/<role_id>.png` and `work/tokens_<script name>/` (one PNG per role and per reminder token),
which is handy if you want the individual images. Add `--incremental` to reuse what is already there instead of
downloading and drawing everything again:
```bash
botc_tokens create script.json -o printables -m work --incremental
```
**Caching caveat:** the icon cache is keyed by role ID only. If two scripts share one `-m` folder and both define a
homebrew character with the same ID, whichever icon was cached first is reused. Likewise, changing a character's
`image` URL will not refresh an icon that is already cached. To refresh an icon, delete `icons/<role_id>.png` from the
`-m` folder (or run once without `--incremental`).

### Custom components
Token art (backgrounds, leaves, fonts) is called a component pack. To start from the built-in one, dump it, edit
the files, and pass the folder (or a zip of it) back in:
```bash
botc_tokens dump components my_components
botc_tokens create script.json -o printables --components my_components
```
Packs may be sparse: any file you leave out falls back to the built-in one, and `create` prints which ones it
used. See the [example repository](https://github.com/Tsubashi/botc_tokens-Examples) for ready-made packs.

### Overriding duplicates and icons
Some roles need several tokens (the Imp, for example, is printed four times by default). Dump the built-in table,
change it, and pass it back in:
```bash
botc_tokens dump duplicates my_defaults
botc_tokens create script.json -o printables --duplicates my_defaults/duplicates.json
```
Roles that do not give an `image` get their icon from a built-in table of official icons. You can add or replace
entries with a JSON file that maps role IDs to URLs, `data:` URIs, or local paths (relative to that file):
```bash
botc_tokens dump icon-lookup my_defaults
botc_tokens create script.json -o printables --icon-lookup my_defaults/icon_lookup.json
```
An icon given in the script itself always wins over the table. A role with no icon at all gets a token without one,
and a warning. `botc_tokens dump all` writes the components, duplicates, and icon lookup together.

### Migrating from older versions
Earlier versions used `update`, `create`, and `group` with a folder of per-role JSON files. Those commands are gone.
Convert an old input folder into one script JSON per script, plus a shared `icons/` folder:
```bash
botc_tokens migrate -i /path/to/old/inputs new_scripts
botc_tokens create new_scripts/my_script.json -o printables
```

### Preparing hand-made icons
`create` pads icons automatically, but if you want to inspect or pre-pad your own artwork, `pad-icons` finds every
PNG and WebP in a folder and adds the transparent padding the official icons have (icons that already have it are
left alone). Without `-i` the results are saved beside the originals as `<name>_padded`; with `-i` the originals are
overwritten:
```bash
botc_tokens pad-icons /path/to/icons --in-place
```

## And that's it!
You can now print your tokens and use them in your games. Remember, this is a fan-made utility and is not
affiliated with the official game in any way. We do not own the rights to the game, and we do not claim to. We are just
fans who want to make the game more accessible to everyone. Please support the creators by 
[buying the game](https://bloodontheclocktower.com/buy). It is absolutely worth it!
