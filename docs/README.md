# Shellwash

A shell upgrade and a living terminal background.

- **bedazzle** - prompt theme, reactive buddy, fetch panel, feature toggles
- **termbg** - pixel-art background that repaints as you work

Runs on **Windows** (PowerShell + Windows Terminal, `bedazzle.ps1`) and
**Linux** (zsh + oh-my-zsh + powerlevel10k, `linux/*.zsh`).

On Linux, powerlevel10k stays your default prompt. Shellwash layers addons on
top and only replaces the prompt if you switch to the `bedazzle` theme.

## What each piece is

| Piece | What it is |
|-------|-----------|
| **bedazzle** | Control command: feature toggles, themes, accent, buddy/hat, stats. |
| **buddy / pet** | Reactive ASCII pet. `buddy` = roster + gacha; `pet` = corner toggle. |
| **termbg** | Living background (16 modules, 12 palettes). kitty on Linux, WT on Windows. |
| **fetch** | fastfetch-style system panel on login and on demand. |
| **lava** | Metaballs lamp in a screen corner. |
| **hr** | Gradient horizontal rule. |
| **wall** | One termbg frame, no daemon. |

## Documentation

| Doc | Contents |
|-----|----------|
| [install.md](install.md) | Linux and Windows setup, kitty settings. |
| [commands.md](commands.md) | Every command and subcommand. |
| [features.md](features.md) | Feature toggles in config. |
| [themes.md](themes.md) | Theme manager and accent color. |
| [termbg.md](termbg.md) | Background engine: modules, palettes, overlays. |
| [buddy.md](buddy.md) | Pet roster, hats, reactions. |
| [troubleshooting.md](troubleshooting.md) | Common fixes. |
| [kitty.conf.snippet](kitty.conf.snippet) | Required kitty.conf lines for termbg. |

## Quick start

- **Linux:** [install.md](install.md) for prerequisites, then install.
- **Windows:** [install.md](install.md), then `.\install.ps1`.
