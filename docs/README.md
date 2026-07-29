# bedazzle + termbg

A shell upgrade and a living terminal background.

- **bedazzle** — prompt theme, reactive buddy, fetch panel, feature toggles
- **termbg** — pixel-art background that repaints as you work

Runs on **both** platforms:

- **Windows** — PowerShell + Windows Terminal, driven by `bedazzle.ps1`.
- **Linux** — zsh + oh-my-zsh + powerlevel10k, driven by `linux/*.zsh`.

On Linux, powerlevel10k stays your default prompt; bedazzle layers its addons
on top and only takes over the prompt if you switch to the `bedazzle` theme.

## What each piece is

| Piece | What it is |
|-------|-----------|
| **bedazzle** | The control command. Toggles every feature, switches themes, sets accent color, picks buddy/hat, shows stats. |
| **buddy / pet** | A reactive ASCII pet. `buddy` shows the roster + gacha roll; `pet` toggles the live corner buddy. |
| **termbg** | A living terminal background (16 visual modules, 12 palettes). kitty on Linux, Windows Terminal on Windows. |
| **fetch** | A fastfetch-style system info panel, printed on login and on demand. |
| **lava** | A small metaballs lamp daemon painted in a screen corner. |
| **hr** | A one-line gradient horizontal rule / divider. |
| **wall** | One-shot background paint (a single termbg frame, no daemon). |

## Documentation

| Doc | Contents |
|-----|----------|
| [install.md](install.md) | Step-by-step setup for Linux and Windows, plus the required kitty settings. |
| [commands.md](commands.md) | Every user-facing command and subcommand, with args and examples. |
| [features.md](features.md) | Every feature toggle in the config and what it does. |
| [themes.md](themes.md) | The theme manager (p10k / bedazzle / any omz theme / random) and accent recoloring. |
| [termbg.md](termbg.md) | The living background: display model, all 16 modules, all 12 palettes, overlays. |
| [buddy.md](buddy.md) | The pet: full roster, hats, gacha odds, reactions, and how it renders. |
| [troubleshooting.md](troubleshooting.md) | Common problems and fixes. |
| [kitty.conf.snippet](kitty.conf.snippet) | Copy-pasteable kitty.conf lines required for termbg. |

## Quick start

- **Linux:** `bash linux/install.sh`, open a new terminal, run `bedazzle`.
- **Windows:** `.\install.ps1`, open a new tab, run `bedazzle`.

Run `bedazzle` on its own at any time to see the full feature list and command
cheat-sheet.
