# Troubleshooting

## termbg shows nothing

On **kitty** (Linux), termbg drives the background over kitty's remote-control
socket. If nothing appears, or `termbg on` prints "kitty remote control
unreachable":

1. Make sure `kitty.conf` has **both**:
   ```
   allow_remote_control    yes
   listen_on               unix:/tmp/kitty
   ```
   plus `background_tint 0.0` and `background_image_layout scaled`
   (see [kitty.conf.snippet](kitty.conf.snippet)).
2. **Fully restart kitty** — close every window. A config reload / SIGUSR1 is
   **not** enough for `listen_on` to bind the socket.
3. Confirm with `termbg once` — it renders a single frame and prints the exact
   backend error if it can't reach kitty.

On **Windows Terminal**, termbg edits `settings.json`. If it doesn't show,
confirm WT is the default profile (termbg writes to `profiles.defaults`) and
that WT can hot-reload `settings.json`.

## Background stops after opening/closing tabs or windows

termbg uses **one shared daemon** for all shells. It now broadcasts each frame to
**every live kitty listen socket** under `/tmp/kitty*` (not just the tab that
started the daemon). If the background still vanishes or freezes:

1. **Fully quit kitty** (all windows), reopen, then run:
   ```
   termbg off && termbg on
   ```
2. Confirm remote control works: `termbg once` should print success, not a
   socket/remote-control error.
3. Avoid leaving orphaned kitty processes running — each gets its own socket
   (`/tmp/kitty-<pid>` on kitty 0.32+). Stale sockets are skipped automatically,
   but a full kitty restart clears confusion fastest.

Only **one** termbg daemon should run (guarded by `termbg.pid`). Starting a new
shell/tab does not start another; it feeds events to the same daemon.

## p10k "instant prompt" warning at startup

powerlevel10k warns if anything prints to the console during initialization.
bedazzle avoids this by design:

- The login **panel** (`fetch`) is printed from a small block prepended to the
  **top** of `~/.zshrc`, *before* p10k's instant prompt — the installer sets
  this up. If you see the warning, make sure the `# >>> bedazzle login >>>`
  block is at the very top of `~/.zshrc` (above the instant-prompt line), not
  in the main source block.
- The corner buddy **skips the first prompt** for the same reason.

If you still see it, run `p10k configure` and, if prompted, let it silence the
warning — the panel is intentionally printed before instant prompt.

## Buddy not showing

- The buddy needs the `sprite` feature on: `pet on` (or `bedazzle on sprite`).
- On Linux, the corner buddy is **skipped on the very first prompt** — run one
  command and it appears.
- Confirm your terminal supports truecolor and cursor save/restore (kitty,
  Windows Terminal, and most modern emulators do).

## nowplaying not reacting

The `nowplaying` termbg module reads your music over MPRIS via **playerctl**:

- Install it: `sudo apt install playerctl`.
- Your player must expose MPRIS (most do). Test with `playerctl status` — it
  should print `Playing`/`Paused`.
- Album-art *pixels* additionally need **Pillow** (`pip install Pillow`);
  without it the module falls back to a colored "vinyl" disc.
- Without playerctl entirely, the module still draws but stays idle (no track
  data).

## Nothing happens after install

Open a **new** terminal/tab (or run `reload` on Linux) — the profile/zshrc block
only takes effect in shells started after install. Then run `bedazzle` to
confirm it loaded.
