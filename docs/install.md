# Setup / Install

## Before you install

### Linux

| | Requirement | Notes |
|---|-------------|--------|
| **Required** | **zsh** + **[oh-my-zsh](https://ohmyz.sh/)** | Installer sources `linux/init.zsh` from your `~/.zshrc`. |
| **Required** | **Python 3.10+** | `python3` on PATH. |
| **Required** | **git** | Clone + install script. |
| **Required** | **[kitty](https://sw.kovidgoyal.net/kitty/)** | For **termbg** on Linux. Bedazzle (prompt, buddy, fetch) works in any terminal; termbg has nowhere to display without kitty. Installer appends the needed kitty.conf lines. |
| **Expected** | **[powerlevel10k](https://github.com/romkatv/powerlevel10k)** | Stays your default prompt. Shellwash layers on top. |
| **Installed by script** | **numpy** | Via system python or a repo-local `.venv/`. |

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
| **playerctl** | `sudo apt install playerctl` | `nowplaying` termbg module (MPRIS music). Test: `playerctl status`. |
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

**Linux:**

```bash
curl -fsSL https://raw.githubusercontent.com/tonykorycki/shellwash/main/install.sh | bash
exec zsh
```

**Windows:**

```powershell
irm https://raw.githubusercontent.com/tonykorycki/shellwash/main/install-remote.ps1 | iex
```

Installs to `~/.local/share/shellwash` (Linux) or `%LOCALAPPDATA%\shellwash`
(Windows): Python deps, shell profile hooks, and kitty termbg settings (Linux).

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
3. Login fetch panel before p10k instant prompt (Linux).
4. kitty.conf termbg snippet if kitty is installed (Linux).
5. Backups as `*.bak-before-shellwash` before first edit.

**Undo:** remove `# >>> shellwash … <<<` from `~/.zshrc` or `$PROFILE`.

---

## After install

1. **Linux:** fully **restart kitty** (all windows) if termbg is new to you.
2. Open a **new** terminal tab.
3. Run `bedazzle`, then `termbg on` if the background did not auto-start.

See [troubleshooting.md](troubleshooting.md) if termbg or the buddy does not appear.

---

## Config

Settings live in `bedazzle.config.json`. Use `bedazzle on/off <feature>` or see
[features.md](features.md).
