# Troubleshooting

## termbg shows nothing

On **kitty**, termbg drives the background over remote control. If nothing
appears, or `termbg on` prints "kitty remote control unreachable":

1. Confirm `kitty.conf` has:
   ```
   allow_remote_control    yes
   listen_on               unix:/tmp/kitty
   background_tint          0.0
   background_image_layout  scaled
   ```
   (see [kitty.conf.snippet](kitty.conf.snippet)).
2. **Fully restart kitty** (close every window). Reload/SIGUSR1 is not enough.
3. Run `termbg once` to surface the exact backend error.

On **Windows Terminal**, termbg edits `settings.json`. Confirm WT hot-reloads
it and termbg writes to `profiles.defaults`.

## Background stops after opening/closing tabs

termbg uses one shared daemon. It broadcasts each frame to every live kitty
socket under `/tmp/kitty*`. If the background still vanishes:

1. Quit kitty completely, reopen, then:
   ```
   termbg off && termbg on
   ```
2. Run `termbg once` and confirm no socket error.
3. Avoid orphaned kitty processes (each gets `/tmp/kitty-<pid>` on kitty 0.32+).

Only one daemon runs (`termbg.pid`). New tabs feed the same daemon via
`termbg.events`.

## p10k "instant prompt" warning

powerlevel10k warns if anything prints during initialization. Shellwash avoids
this by printing the fetch panel from a block at the **top** of `~/.zshrc`,
before instant prompt. If you see the warning, move `# >>> shellwash login >>>`
above the instant-prompt line.

The corner buddy skips the first prompt for the same reason.

## Buddy not showing

- Enable the sprite feature: `pet on` or `bedazzle on sprite`.
- On Linux, the buddy appears after the first command (not the first prompt).
- Needs truecolor and cursor save/restore (kitty, WT, most modern terminals).

## Pet not reacting to GitHub PR comments

Needs the **`pet_github`** feature on (default) and an authenticated **GitHub CLI**:

```bash
gh auth login
gh auth status
```

The poll runs every ~90s in git repos. Plain `git` is not enough for this
feature; `gh` must be logged in.

## nowplaying not reacting

Needs **playerctl** for MPRIS music control:

```bash
sudo apt install playerctl   # Debian/Ubuntu
playerctl status             # should print Playing/Paused
```

Your music player must expose MPRIS (Spotify, VLC, and most Linux players do).
**Pillow** (`pip install Pillow`) optional for album-art pixels; without it you
get a colored vinyl disc instead.

## Nothing happens after install

Open a **new** terminal (or `reload` on Linux). Then run `bedazzle` to confirm
it loaded.
