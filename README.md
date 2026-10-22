# Shellwash

A shell upgrade and a living terminal background.

- **bedazzle** - prompt theme, reactive ASCII buddy, fetch panel, feature toggles
- **termbg** - pixel-art background behind your text that evolves as you work

Cross-platform: **Windows** (PowerShell + Windows Terminal), **Linux** and
**macOS** (zsh + oh-my-zsh + kitty for termbg). See [install](docs/install.md)
for full prerequisites (Python, git, optional playerctl / gh).

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

## Quick start (Linux / macOS)

**One command** (clone + install + kitty config):

```bash
curl -fsSL https://raw.githubusercontent.com/tonykorycki/shellwash/main/install.sh | bash
exec zsh
```

Or from a clone:

```bash
git clone https://github.com/tonykorycki/shellwash.git && cd shellwash
bash install.sh
exec zsh
```

Type `bedazzle` to see everything. termbg auto-starts on login in kitty or
Windows Terminal. **Restart kitty fully** after a first install so termbg can
connect. On macOS the same script applies — see
[install](docs/install.md#macos) for the two features that differ.

**Undo:** remove `# >>> shellwash >>>` and `# >>> shellwash login >>>` from
`~/.zshrc`.

## Quick start (Windows)

```powershell
irm https://raw.githubusercontent.com/tonykorycki/shellwash/main/install-remote.ps1 | iex
```

Or clone and run `.\install.ps1`. Requires Windows Terminal and Python 3.10+.

**Undo:** delete `# >>> shellwash >>>` from `$PROFILE`.

---

## bedazzle

Dot-sourced from your shell profile. Type **`bedazzle`** to toggle features.
Config lives in `bedazzle.config.json`.

**Prompt** (minimal, one accent color): shortened path + git + venv on the left;
duration, exit status, clock, battery, weather on the right.

**Buddy:** ASCII pet in the top-right. `buddy` shows the roster; `pet` toggles
it in any theme.

**fetch** - system panel on startup. **lava** - corner metaballs lamp.

Also: `bedazzle accent`, `bedazzle stats`, `hr`, and `bedazzle theme …`.

## termbg

Regenerating pixel-art *behind your text*. One step per command and per `cd`:

```
termbg                 modules, palettes, state
termbg on              start (evolves per command)
termbg freeze          stop evolving, keep image
termbg off             stop and remove background
termbg use <module>    metaballs, automaton, tetris, …
termbg palette <name>  nord, dracula, accent, …
termbg opacity <0-0.6>
termbg overlay <name>  exitcode | none
termbg once            one frame, no daemon
```

See [docs/termbg.md](docs/termbg.md). `wall` = `termbg once`; `wall off` =
`termbg off`.

## How the pieces fit

| | **bedazzle** | **termbg** |
|---|-------------|-----------|
| Role | Shell skin: prompt, buddy, fetch, lava, config | Background engine: evolving pixel art |
| Commands | `bedazzle`, `buddy`, `pet`, `fetch`, `lava` | `termbg`, `wall` |

bedazzle hooks write shell events that termbg reads. `termbg_auto` (on by
default) starts the daemon at login. The `accent` palette follows your bedazzle
hue.
