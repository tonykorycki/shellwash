# termbg

`termbg` paints regenerating pixel-art *behind your terminal text*. The
Shellwash hooks append one line per command to `termbg.events`
(`ok|<count>|<cwd>`). A background daemon polls that file, advances module
state, renders, and hands the image to the terminal.

See [commands.md](commands.md#termbg--the-living-background) for the command
surface. This page is the reference for the display model and the catalog.

## Display model

- **Per-command evolution.** Each command advances the module one step
  (e.g. metaballs drift, tetris drops a row, a cellular automaton ticks). The
  daemon throttles renders (default ~900ms) so a burst of commands doesn't
  thrash. Some modules only re-render when you `cd` (see the table).
- **Chunky pixels.** Modules render a small grid (e.g. 160×90) that is
  nearest-neighbor upscaled with *cover* scaling — it always fills the whole
  window, never letterboxes.
- **Opacity.** How strongly the art shows through, `0.05–0.6` (config default
  ~0.4). On kitty the opacity is **baked into the PNG** by termbg; on Windows
  Terminal, WT does the blend itself via `backgroundImageOpacity`.
- **Per-directory seeding.** Many modules are seeded from the current directory,
  so each folder gets its own artwork.

### Backends

| Backend | How it displays | Opacity |
|---------|-----------------|---------|
| **kitty** (Linux) | `kitty @ set-background-image` via listen socket. Needs snippet in [install.md](install.md). | Baked into PNG. |
| **Windows Terminal** | Edits `settings.json` (`backgroundImage`, `backgroundImageOpacity`), which WT hot-reloads. Backs up to `settings.json.bak-shellwash`; restores on `off`. | WT blends. |

The backend is auto-detected (`KITTY_WINDOW_ID`/`xterm-kitty` → kitty;
`WT_SESSION` or a found `settings.json` → wt).

## Modules (16)

Switch with `termbg use <name>`. The default is `metaballs`.

| Module | Description | Reacts to |
|--------|-------------|-----------|
| `metaballs` | Lava blobs drift one step per command; flinch on a failed command. | exit code |
| `automaton` | Conway's Life; cells age cool→hot; reseeds when the population dies out. | — |
| `tetris` | Plays itself in a docked board — one gravity tick per command. | — |
| `skyline` | Git city: repo+branch color the sky, commit count raises the towers, recent commits light the windows, tags become stars, dirty files fly as birds. | **git** |
| `attractor` | A de Jong attractor; each directory gets its own artwork (cached). | cd (per-directory) |
| `truchet` | Quarter-circle tiles; a few reroll each command (shimmer). | — |
| `contour` | Topographic noise map; unique per directory. | cd (per-directory) |
| `moire` | Interference rings; phase drifts per command. | — |
| `subdivision` | Mondrian rectangles; unique per directory. | cd (per-directory) |
| `phyllotaxis` | Sunflower spiral; rotates slowly per command. | — |
| `circadian` | A sky that tracks the real time of day; a sun/moon arcs across it. | **time of day** |
| `pulse` | Metaballs that get hotter and faster as system load climbs. | **system load**, exit code |
| `storm` | A cute pixel sea with sailboats — calm and sunny when idle, clouds/rain/lightning under load. | **system load** |
| `aurora` | Shimmering northern-lights curtains; drifts per command. | — |
| `gitlife` | Conway's Life whose starting population *is* your git diff — a clean tree seeds a couple of oscillators; the more lines changed, the busier it starts. Reseeds as you edit. | **git diff** |
| `nowplaying` | Your music, personalized: pixelated album art, your buddy in headphones bobbing to the beat, a per-song equalizer, and a progress bar. | **music** |

### What each reactive module needs

| Reacts to | Modules | Needs |
|-----------|---------|-------|
| git branch/commits/dirty/tags | `skyline` | `git` on PATH; a git repo |
| git diff | `gitlife` | `git` on PATH; a git repo |
| system load | `pulse`, `storm` | `os.getloadavg()` (Linux; falls back to a constant elsewhere) |
| time of day | `circadian` | — (uses the system clock) |
| your music | `nowplaying` | `playerctl` (MPRIS) for track/status/position; **Pillow** for album-art pixels (falls back to a colored "vinyl" disc without it) |

## Palettes (12)

Switch with `termbg palette <name>`.

| Palette | Description |
|---------|-------------|
| `accent` | Follows your bedazzle accent hue — the most colorful; recolors live when you change the accent. |
| `nord` | Cool arctic blues, muted and calm. |
| `gruvbox` | Warm retro browns and golds. |
| `dracula` | Purple and pink on near-black. |
| `sunset` | Plum through crimson to peach. |
| `neon` | Electric purple/magenta/cyan — maximum pop. |
| `ember` | Fire: rust, orange, gold. |
| `catppuccin` | Soft pastel mocha — easy on the eyes. |
| `tokyonight` | Deep indigo night with neon blues. |
| `rosepine` | Muted rose, pine, and foam. |
| `everforest` | Warm forest greens and tans. |
| `solarized` | The classic balanced blue-green base. |

(The default palette is `nord`.)

## Overlay

Set with `termbg overlay <name>`.

| Overlay | Effect |
|---------|--------|
| `exitcode` (default) | A red vignette flashes around the edges when a command fails, then fades over the next few commands. |
| `none` | Just the module, no reactions. |

## Files it manages

- `termbg.config.json` — module/palette/overlay/opacity/backend/resolution.
- `termbg.state/` — per-module persistent state (so animations continue across
  commands) plus `global.json`.
- `termbg.events` — the per-command feed the daemon polls.
- `termbg-<timestamp>.png` — rendered frames (only the two newest are kept).
- `termbg.pid` — the daemon pidfile.
