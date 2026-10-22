# Setup / Install

## Before you install

### Linux

| | Requirement | Notes |
|---|-------------|--------|
| **Required** | **zsh** + **[oh-my-zsh](https://ohmyz.sh/)** | Installer sources `linux/init.zsh` from your `~/.zshrc`. |
| **Required** | **Python 3.10+** | `python3` on PATH. |
| **Required** | **git** | Clone + install script. |
| **Required** | **[kitty](https://sw.kovidgoyal.net/kitty/)** | For **termbg** on Linux/macOS. Bedazzle (prompt, buddy, fetch) works in any terminal; termbg has nowhere to display without kitty. Installer appends the needed kitty.conf lines. |
| **Expected** | **[powerlevel10k](https://github.com/romkatv/powerlevel10k)** | Stays your default prompt. Shellwash layers on top. |
| **Installed by script** | **numpy** | Via system python or a repo-local `.venv/`. |

### macOS

macOS runs the same installer and the same `linux/` shell code — zsh is already
the default shell there, and kitty is supported. Requirements match Linux
(zsh + oh-my-zsh, Python 3.10+, git, kitty for termbg), with these notes:

| | Note |
|---|------|
| **Python** | `python3` is the Xcode Command Line Tools stub until you install it — run `xcode-select --install`, or `brew install python`. |
| **kitty** | Install via `brew install --cask kitty` (or the .dmg). The app bundle is not on `PATH` by default; both the installer and termbg fall back to `/Applications/kitty.app/Contents/MacOS/kitty`, so remote control still works. |
| **fetch panel** | System facts come from `sysctl`, `vm_stat` and `pmset` instead of `/proc` and `/sys`. The GPU lookup shells out to `system_profiler` once, then caches — the first login panel may pause a second. |
| **`nowplaying` termbg module** | Not available. It reads MPRIS via `playerctl`, which is Linux-only; the module falls back to its generated visuals. |

Everything else — prompt, buddy, themes, the other termbg modules, git-driven
art — behaves identically.

**Before trusting it on a Mac**, run the read-only smoke check — it installs
and changes nothing, and prints what shellwash parsed next to the raw tool
output so a wrong assumption is obvious:

```bash
bash tests/macos-smoke.sh
```

See [tests/README.md](../tests/README.md).

### Windows

| | Requirement | Notes |
|---|-------------|--------|
| **Required** | **PowerShell 5.1+** | |
| **Required** | **[Windows Terminal](https://github.com/microsoft/terminal)** | termbg sets `backgroundImage` in WT settings. |
| **Required** | **Python 3.10+** | On PATH as `python`. |
| **Required** | **git** | Clone + install script. |
| **Installed by script** | **numpy** | In repo-local `.venv/`. |

### Optional extras

None of these block install. They unlock specific features:

| Tool | Install (example) | Enables |
|------|-------------------|---------|
| **playerctl** *(Linux only)* | `sudo apt install playerctl` | `nowplaying` termbg module (MPRIS music). Test: `playerctl status`. |
| **Pillow** | `pip install Pillow` | Album-art pixels in `nowplaying` (falls back to a colored disc without it). |
| **curl** | usually preinstalled | Cached weather in fetch + prompt (`bedazzle on weather`). |
| **git** | usually preinstalled | Branch chip, `skyline` / `gitlife` termbg modules. |
| **GitHub CLI (`gh`)** | [cli.github.com](https://cli.github.com/) | Buddy **notify** reaction when PR review comments arrive (`pet_github` toggle, on by default). |

#### GitHub CLI setup

Only needed for the pet's PR-comment reaction (not for git prompt or git-themed backgrounds):

```bash
# install gh, then:
gh auth login
```

Follow the prompts (browser or token). Verify with `gh auth status`. The buddy
poll runs in the background every ~90s when `pet_github` is on.

---

## Install

The installer is idempotent (safe to re-run).

### One command

**Linux / macOS:**

```bash
curl -fsSL https://raw.githubusercontent.com/tonykorycki/shellwash/main/install.sh | bash
exec zsh
```

**Windows:**

```powershell
irm https://raw.githubusercontent.com/tonykorycki/shellwash/main/install-remote.ps1 | iex
```

Installs to `~/.local/share/shellwash` (Linux/macOS) or
`%LOCALAPPDATA%\shellwash` (Windows): Python deps, shell profile hooks, and kitty termbg settings (Linux/macOS).

### Manual

```bash
git clone https://github.com/tonykorycki/shellwash.git
cd shellwash && bash install.sh && exec zsh
```

Windows: clone, then `.\install.ps1`.

---

## What the installer does

1. Python / numpy (system or `.venv/`).
2. Shell profile block (`# >>> shellwash >>>`).
3. Login fetch panel before p10k instant prompt (Linux/macOS).
4. kitty.conf termbg snippet if kitty is installed (Linux/macOS).
5. Backups as `*.bak-before-shellwash` before first edit.

**Undo:** remove `# >>> shellwash … <<<` from `~/.zshrc` or `$PROFILE`.

---

## After install

1. **Linux/macOS:** fully **restart kitty** (all windows) if termbg is new to you.
2. Open a **new** terminal tab.
3. Run `bedazzle`, then `termbg on` if the background did not auto-start.

See [troubleshooting.md](troubleshooting.md) if termbg or the buddy does not appear.

---

## Config

Settings live in `bedazzle.config.json`. Use `bedazzle on/off <feature>` or see
[features.md](features.md).
