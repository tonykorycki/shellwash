# bedazzle + termbg

A shell upgrade and a living terminal background.

- **bedazzle** — prompt theme, reactive ASCII buddy, fetch panel, feature toggles
- **termbg** — pixel-art background behind your text that evolves as you work

Cross-platform: **Windows** (PowerShell + Windows Terminal) and **Linux**
(zsh + oh-my-zsh, coexisting with powerlevel10k).

## Documentation

Full docs in [`docs/`](docs/):
[overview](docs/README.md) ·
[install](docs/install.md) ·
[commands](docs/commands.md) ·
[feature toggles](docs/features.md) ·
[themes](docs/themes.md) ·
[termbg modules & palettes](docs/termbg.md) ·
[the buddy](docs/buddy.md) ·
[troubleshooting](docs/troubleshooting.md)

## Quick start — Linux (zsh + oh-my-zsh)

```bash
git clone <this-repo> ascii-art && cd ascii-art
bash linux/install.sh        # numpy check + one guarded block in ~/.zshrc, idempotent
exec zsh                     # or open a new terminal
```

The installer keeps **powerlevel10k as your default prompt** and layers bedazzle
on top. Type `bedazzle` to see (and toggle) everything; `buddy` for the pet
roster; `fetch`, `lava`, `hr`, `termbg` anywhere. Switch the prompt with
`bedazzle theme bedazzle` (and `bedazzle theme p10k` / `random` to switch back
or roll). The corner **buddy** works in every theme.

**Undo:** remove the `# >>> bedazzle >>>` block (and the `bedazzle login` block)
from `~/.zshrc`.

### termbg backgrounds need kitty (one-time setup)

VTE/GNOME Terminal can't hot-reload a background image, so termbg targets
**kitty**. Append the repo's ready-made snippet to your kitty config, then
fully restart kitty:

```bash
cat docs/kitty.conf.snippet >> ~/.config/kitty/kitty.conf
# then QUIT kitty entirely (all windows) and reopen — required for the socket
sudo apt install playerctl   # optional: enables the 'nowplaying' module
```

`termbg` auto-starts on login and evolves each command; run `termbg` alone for
the full module/palette menu. Under any non-kitty terminal the render engine
still works — it just reports it has nowhere to display.

## Quick start — Windows (PowerShell + Windows Terminal)

```powershell
git clone <this-repo> ascii-art
cd ascii-art
.\install.ps1     # venv + numpy + profile hook, idempotent
```

Requirements: Windows Terminal, Python 3.10+, PowerShell 5.1+. On Windows the
buddy lives in the prompt corner and termbg drives Windows Terminal's
`backgroundImage` (no kitty needed).

**Undo:** delete the marked block at the bottom of `$PROFILE`.

---

## bedazzle

Dot-sourced from your shell profile. Type **`bedazzle`** to see every feature
and toggle it on/off — config persists in `bedazzle.config.json`.

**The prompt** (minimal, one accent color):
`~\ascii-art  ⎇ main  ⚡venv` on the left; `842ms · ✓ · 23:51 · 100% · +17°C`
right-aligned (duration, exit status, clock, battery, cached weather).
Fish-style path shortening, git from `.git/HEAD`, merge/rebase state flagged.

**The buddy:** an ASCII pet in the top-right that reacts to failures, long
tasks, idle time, and blinks otherwise. `buddy` shows the roster; `pet` toggles
the corner buddy in any theme.

**fetch** — fastfetch-style system panel on startup and on demand.

**lava** — metaballs lamp in a screen corner (`bgfx.py`). `lava` toggles it.

Also: `bedazzle accent`, `bedazzle stats`, `hr` (gradient divider), theme
manager (`bedazzle theme p10k|bedazzle|random|<omz-theme>`).

## termbg

A regenerating pixel-art background *behind your text*. The prompt feeds shell
events to a background daemon; the active module advances one step per command
and per `cd`:

```
termbg                 full colored help: modules, palette swatches, state
termbg on              start — background evolves per command
termbg freeze          stop evolving, keep the current image on screen
termbg off             stop and remove the background
termbg use <module>    metaballs · automaton · tetris · attractor · …
termbg palette <name>  nord · gruvbox · dracula · sunset · accent · …
termbg opacity <0-0.6> how strongly it shows through
termbg overlay <o>     exitcode (red vignette on failure) · none
termbg once            single fresh frame, no daemon
```

16 visual modules, 12 palettes. See [docs/termbg.md](docs/termbg.md) for the
full list. `wall` = one fresh frame; `wall off` = `termbg off`.

On Windows, termbg edits Windows Terminal's `settings.json` (hot-reloads).
On Linux, it drives kitty over the remote-control socket.

## Are these two separate tools?

Yes, but they plug together:

| | **bedazzle** | **termbg** |
|---|-------------|-----------|
| What | Shell skin: prompt, buddy, fetch, lava, config | Background engine: evolving pixel art |
| Entry point | `bedazzle` command + profile hooks | `termbg` command + background daemon |
| Can run alone? | Yes (without termbg) | Yes (without bedazzle's prompt — but hooks normally feed it events) |

bedazzle's hooks write shell events (command count, cwd, exit code) that termbg
reads. The `termbg_auto` toggle (on by default) starts termbg at login.
termbg's `accent` palette follows your bedazzle accent hue. Everything else —
buddy, fetch, lava, the minimal prompt — is bedazzle only.
