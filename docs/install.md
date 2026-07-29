# Setup / Install

bedazzle installs the same way on both platforms: clone the repo anywhere,
run the installer, open a fresh shell. The only Python dependency is
**numpy** (`requirements.txt`). Everything else is optional and degrades
gracefully.

---

## Linux (zsh + oh-my-zsh + powerlevel10k)

### 1. Run the installer

```bash
bash linux/install.sh
```

The installer is **idempotent** (safe to re-run) and does three things:

1. **Python / numpy.** If your system `python3` already imports `numpy`, it is
   used as-is (offline-friendly, no venv). Otherwise it creates `.venv/` in the
   repo and `pip install`s `requirements.txt`. Requires Python 3.10+.
2. **`~/.zshrc` source block.** Appends a marked block that sources
   `linux/init.zsh`. It is added **after** oh-my-zsh / p10k so **powerlevel10k
   stays your default prompt**; bedazzle only layers its addons on top. A
   backup is written to `~/.zshrc.bak-before-bedazzle`.
3. **Login panel block.** Prepends a small block to the **top** of `~/.zshrc`
   (before p10k's instant prompt) that prints the `fetch` login panel. This
   ordering is deliberate — printing a banner after instant-prompt starts would
   trip p10k's "console output during initialization" warning. The block calls
   `fetch.py --login`, which self-checks the `fetch` toggle and needs no numpy.

**Undo:** remove the two marked blocks (`# >>> bedazzle ... <<<` and
`# >>> bedazzle login ... <<<`) from `~/.zshrc`.

Then open a new terminal (or run `reload`) and try `bedazzle`, `buddy`,
`pet`, `fetch`, `termbg on`.

### 2. Configure kitty (required for `termbg`)

`termbg` drives kitty's background image over kitty's remote-control socket.
Without the right settings it shows nothing. Append the contents of
[`kitty.conf.snippet`](kitty.conf.snippet) to `~/.config/kitty/kitty.conf`:

```
allow_remote_control    yes
listen_on               unix:/tmp/kitty
background_tint          0.0
background_image_layout  scaled
```

- `allow_remote_control yes` **and** `listen_on unix:/tmp/kitty` — the termbg
  daemon runs backgrounded with no controlling window, so it can only reach
  kitty through the listen socket.
- `background_tint 0.0` — termbg bakes opacity into the PNG itself, so kitty
  must not dim/tint the image.
- `background_image_layout scaled` — the image is scaled to fill the window.

After editing, **fully restart kitty** — close every window. A config reload
(SIGUSR1 / `ctrl+shift+F5`) is **not** enough for `listen_on` to bind the
socket.

### 3. Optional extras (`sudo apt install`)

| Package | Enables |
|---------|---------|
| `playerctl` | The `nowplaying` termbg module (reads your music over MPRIS). |
| `python3-pil` / `pip install Pillow` | Album-art pixels in `nowplaying` (falls back to a colored "vinyl" disc without it). |
| `git`, `gh` | The `skyline`/`gitlife` termbg modules and the pet's GitHub reactions. `gh` must be authenticated for PR-comment reactions. |
| `curl` | Cached wttr.in weather in the panel / prompt. |

### powerlevel10k coexistence

- p10k remains the default prompt after install. The bedazzle theme is opt-in
  via `bedazzle theme bedazzle`.
- The always-on hooks (command timing, pet feed, termbg feed, corner buddy)
  run under **every** theme, p10k included — they are cheap file writes with no
  Python in the prompt hot path.
- If `accent_p10k` is enabled, a few p10k segments (dir, vcs-clean, virtualenv,
  prompt char) are tinted with your accent hue. This is best-effort; p10k
  configs vary.

---

## Windows (PowerShell + Windows Terminal)

### 1. Run the installer

```powershell
.\install.ps1
```

Idempotent. It:

1. Creates `.venv\` and `pip install`s `requirements.txt` (needs Python 3.10+
   on PATH).
2. Appends a marked block to your PowerShell `$PROFILE` that dot-sources
   `bedazzle.ps1`. A backup is written to `$PROFILE.bak-before-bedazzle`.

**Undo:** delete the `# >>> bedazzle >>> ... <<<` block from `$PROFILE`.

Open a new tab and try `bedazzle`, `buddy`, `fetch`, `lava`, `termbg on`.

### 2. termbg on Windows Terminal

No manual config needed. `termbg` edits Windows Terminal's `settings.json`
(`profiles.defaults.backgroundImage` + `backgroundImageOpacity`), which WT
hot-reloads. termbg backs up the original `settings.json` to
`settings.json.bak-bedazzle` and restores your background color on `termbg off`.

---

## Config file

Both platforms share one config file, `bedazzle.config.json`, at the repo root.
You normally never edit it by hand — the `bedazzle` command reads and writes it.
See [features.md](features.md) for every key.
