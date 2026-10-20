# Token Tools for Blood on the Clocktower

A simple fan-made utility to help create custom tokens for the game Blood on the Clocktower.

![An example of tokens made by this utility](https://github.com/Tsubashi/botc_tokens-Examples/blob/31b118fc96e0f2aaa6b20d7547f2923a6c73ff34/example.jpg?raw=true)

## Installation

### Standalone binaries (no Python or ImageMagick needed)

Every [release](https://github.com/Tsubashi/botc_tokens/releases) comes with ready-to-run builds for Windows (x86_64),
macOS (Apple Silicon and Intel), and Linux (x86_64). They bundle their own copy of ImageMagick, so nothing else needs
to be installed. Download the archive for your platform, unpack it, and run the `botc-tokens` program inside the
unpacked `botc_tokens` folder:

```bash
tar xzf botc_tokens-*-macos-arm64.tar.gz      # or unzip the .zip on Windows
./botc_tokens/botc-tokens version
./botc_tokens/botc-tokens create my-script.json -o printables
```

Notes:

- The macOS builds need macOS 11 or newer and are not code-signed, so Gatekeeper will refuse to open them the first
  time. Either right-click the `botc-tokens` program and choose *Open*, or clear the quarantine flag with
  `xattr -dr com.apple.quarantine botc_tokens` after unpacking.
- Windows SmartScreen may warn about an unrecognised program for the same reason; choose *More info*, then *Run anyway*.
- Setting `MAGICK_HOME` makes the binary use that ImageMagick instead of the bundled one.
- The `THIRD_PARTY_LICENSES` folder in each archive lists the licenses of the bundled libraries.

### Python package

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

The tool is run through its entrypoint `botc_tokens`. There are four working commands (`create`, `dump`, `migrate`,
and `pad-icons`) plus `version`. Use `--help` on any of them to see every option.

### Quick start

To get started, pick a script you want to print. Run the `create` command and give it the script JSON (either as a local file path or a URL). That's it! It will produce a set of print-ready PDFs in the directory of your choosing.

**Example:**

```bash
botc_tokens create https://example.com/my-script.json -o printables
```

This command would write `roles.pdf` and `reminders.pdf` into the `printables/` directory. Characters listed by bare ID (such as
`"washerwoman"`) are filled in from the official data, and their icons are downloaded automatically.

### Creating the Script JSON

You can use the [official script tool](https://script.bloodontheclocktower.com/) or any of the
community-maintained tools to make your script json. Characters you define yourself are used as written. You can also modify official characters by specifying a partial entry; any field you leave out of an official character (Such as its ability text) is
filled in from the official data.

If you built your script in [Bloodstar](https://bloodstar.clocktica.com), pass its save file instead. The format will be detected automatically:

```bash
botc_tokens create my-bloodstar-save.json -o printables
```

The tool expects character icons to carry transparent padding around the artwork just like the official icons do. If your script has tightly cropped icons, we will add padding automatically when they are fetched, so homebrew art should work without any preparation.

### Sizing

By default, we create tokens matching the physical tokens sold with the original game, printed on letter sized paper, printed at 300 dpi. The tool is customizable, however, allowing you to print custom sized tokens on any size of paper.

All distance measurements are given in mm, modulated by the `--dpi` setting.

You can pick a paper preset with `--paper-type` (`letter`, `legal`, `a4`, or `a5`) or give exact dimensions with `--paper-size WIDTH HEIGHT`.

```bash
botc_tokens create script.json -o printables --paper-type a4
botc_tokens create script.json -o printables --paper-size 215.9 279.4 --margin-horizontal 5 --padding 1
```

Change the size of the tokens with `--role-diameter` and `--reminder-diameter`, or adjust the layout with
`--margin-horizontal`, `--margin-vertical`, `--padding`, `--grid`. You can even ditch much of the token text with the aptly named `--skip-ability-text`.

### Keeping intermediate files and caching

When we create the printables, we first have to fetch the icons and generate individual token images. If you use the default args, these get thrown away once the PDFs are made. You can pass `-m` to keep them:

```bash
botc_tokens create script.json -o printables -m work
```

This creates `work/icons/<role_id>.png` with one icon per role and `work/tokens_<script name>/` with one token PNG per role and a number of reminder token PNGs for each one.
It is handy if you want the individual images for other uses, or if you want to use the `--incremental` mode to reuse what is already there instead of downloading and drawing everything again:

```bash
botc_tokens create script.json -o printables -m work --incremental
```

**Caching caveat:** the icon cache is keyed by role ID only. If two scripts share one `-m` folder and both define a
homebrew character with the same ID, whichever icon was cached first is reused. Likewise, changing a character's
`image` URL will not refresh an icon that is already cached. To refresh an icon, delete `icons/<role_id>.png` from the
`-m` folder (or run once without `--incremental`).

### Custom components

The pieces that make up the token art (backgrounds, leaves, fonts) are grouped together in what we call a component pack. You can make your own to customize your tokens. To start from the built-in one, dump it, edit the files, and pass the folder (or a zip of it) back in:

```bash
botc_tokens dump components my_components
botc_tokens create script.json -o printables --components my_components
```

When creating your own packs, you can just include the parts you want to change. Any file you leave out will automaically fall back to the built-in one, and `create` prints which ones it
used. Check out [my Ko.Fi](https://ko-fi.com/tsubashi/shop/componentpack) for some pre-made packs.

### Overriding duplicates and icons

Some roles need several tokens printed (the Imp, for example, is printed four times by default). We control this
through a known-duplicates file. If your script has characters like this, you can dump the built-in table, change it, and pass it back in to apply this same effect to your custom characters:

```bash
botc_tokens dump duplicates my_defaults
botc_tokens create script.json -o printables --duplicates my_defaults/duplicates.json
```

Roles that do not specify an `image` in the json get their icon from a built-in lookup table. This primarily includes the official entires, but you can add or replace entries with a JSON file that maps role IDs to URLs, `data:` URIs, or local paths (relative to that file):

```bash
botc_tokens dump icon-lookup my_defaults
botc_tokens create script.json -o printables --icon-lookup my_defaults/icon_lookup.json
```

An icon given in the script itself always wins over the table. A role with no icon at all gets a token without one,
and a warning. `botc_tokens dump all` writes the components, duplicates, and icon lookup files together.

### Migrating from older versions

Earlier versions of the tool used a different workflow built around the `update`, `create`, and `group` commands. The update command in particular produced a folder of per-role JSON files that could be used to create custom scripts.
That workflow is gone now, but you can convert your old input folders into a unified script JSON folder, plus a shared `icons/` folder using the new `convert` command:

```bash
botc_tokens migrate -i /path/to/old/inputs new_scripts
botc_tokens create new_scripts/my_script.json -o printables
```

### Preparing hand-made icons

While the `create` command will pad icons automatically, you might want to inspect or pre-pad your own artwork. The new `pad-icons` command can help you out. It finds every PNG and WebP in a specified folder and adds the transparent padding to make the official icons (icons that already have it are left alone). Without `-i` the results are saved beside the originals as `<name>_padded`; with `-i` the originals are overwritten:

```bash
botc_tokens pad-icons /path/to/icons --in-place
```

## And that's it!

You can now print your tokens and use them in your games. Remember, this is a fan-made utility and is not
affiliated with the official game in any way. We do not own the rights to the game, and we do not claim to. We are just
fans who want to make the game more accessible to everyone. Please support the creators by
[buying the game](https://bloodontheclocktower.com/buy)!
