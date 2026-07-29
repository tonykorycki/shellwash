# Commands Reference

Every user-facing command. Unless noted, commands behave the same on Linux and
Windows. Run `bedazzle` on its own for a live cheat-sheet.

---

## `bedazzle` — the control command

| Invocation | What it does |
|-----------|--------------|
| `bedazzle` (or `bedazzle help` / `list`) | Show every feature with its on/off state, plus the command cheat-sheet. |
| `bedazzle on <feature>` | Turn a feature on (persisted). |
| `bedazzle off <feature>` | Turn a feature off (persisted). |
| `bedazzle theme <name\|random\|list>` | Switch prompt theme. See below. |
| `bedazzle accent <name\|hue>` | Set the accent color. |
| `bedazzle sprite <name>` | Choose your buddy (`buddy` shows the roster). |
| `bedazzle hat <name>` | Choose a hat: `daily`, `none`, or a specific hat. |
| `bedazzle stats` | Session stats. |

**Features** (for `on`/`off`): `fetch sprite rightinfo git venv shortpath title
airy battery weather spirits rule` — plus, on **Linux only**: `accent_p10k
pet_github termbg_auto`. See [features.md](features.md) for what each does.

**`bedazzle theme`**
- `bedazzle theme` or `bedazzle theme list` — list themes and available omz
  themes, marking the current one.
- `bedazzle theme p10k` — your powerlevel10k config (the default).
- `bedazzle theme bedazzle` — the minimal accent prompt.
- `bedazzle theme <omz-name>` — any oh-my-zsh theme in your themes dir.
- `bedazzle theme random` — roll a random theme.
- On Linux, switching theme **re-execs the shell** (`exec zsh`) so the handoff
  between p10k and another theme is clean; `init.zsh` re-applies your saved
  choice at startup. See [themes.md](themes.md).

**`bedazzle accent`** — named hues: `blue`(215) `violet`(270) `green`(140)
`amber`(45) `red`(2) `cyan`(185) `pink`(330), or any number `0–360`.

```
bedazzle accent violet
bedazzle accent 330
bedazzle on weather
bedazzle off airy
bedazzle theme bedazzle
bedazzle sprite dragon
bedazzle hat wizard
```

**`bedazzle stats`**
- Linux: prints theme, accent (with swatch), and current sprite.
- Windows: prints session length, command count, failures, and a duration
  sparkline of the last 30 commands.

---

## `buddy` — the pet roster & gacha

| Invocation | What it does |
|-----------|--------------|
| `buddy` | Show the full buddy gallery, the hats with rarity colors, the roll odds, and today's buddy/hat. |
| `buddy roll` | Gacha roll: randomly assign a new buddy **and** roll for a hat, then save it as your current sprite/hat. |

`bedazzle sprite <name>` picks a buddy directly; `bedazzle hat daily` returns to
the daily hat draw. See [buddy.md](buddy.md) for the roster and odds.

---

## `pet` — the live corner buddy

| Invocation | What it does |
|-----------|--------------|
| `pet` | Toggle the corner buddy (flips whichever state it's in). |
| `pet on` | Show the corner buddy. |
| `pet off` | Hide the corner buddy. |

- **Linux:** the buddy is painted inline in the top-right corner once per
  prompt, in **every** theme (not an async daemon). `pet` toggles the `sprite`
  feature; any stale daemon from an older version is killed. `pet` and
  `bedazzle on/off sprite` are equivalent.
- **Windows:** `pet` pins a live `pet.py` daemon in the top-right corner that
  repaints and reacts in real time (the inline prompt buddy returns when it's
  off).

See [buddy.md](buddy.md) for reactions.

---

## `fetch` — system panel

```
fetch
```
A fastfetch-style panel in your accent hue (host/OS/kernel/uptime/etc., plus
cached weather if enabled). Printed automatically on login (Linux via a `.zshrc`
top block that honors the `fetch` toggle; Windows on shell start).

---

## `lava` — corner lava lamp

| Invocation | What it does |
|-----------|--------------|
| `lava` | Toggle the metaballs lamp daemon in a screen corner. |
| `lava on` | Start it. |
| `lava off` | Stop it. |

Running `lava` while it's flowing turns it off.

---

## `hr` — gradient divider

```
hr
```
Prints one full-width horizontal rule with a random-hue gradient. No args.

---

## `termbg` — the living background

| Invocation | What it does |
|-----------|--------------|
| `termbg` (or `termbg status`) | Show current module/palette/overlay/opacity, running state, and the full list of modules and palettes with swatches. |
| `termbg on` | Start the daemon — the background evolves once per command. Renders one frame immediately and surfaces backend errors. |
| `termbg freeze` | Stop evolving but keep the current image on screen. `termbg on` resumes. |
| `termbg off` | Stop and remove the background. |
| `termbg once` | Paint a single fresh frame with no daemon (or nudge the running daemon for one). |
| `termbg use <module>` | Switch the visual module. |
| `termbg palette <name>` | Switch the color palette. |
| `termbg opacity <0.05–0.6>` | How strongly the art shows through. |
| `termbg overlay <exitcode\|none>` | Reaction overlay: `exitcode` flashes a red vignette on a failed command; `none` disables it. |

```
termbg on
termbg use skyline
termbg palette tokyonight
termbg opacity 0.3
termbg overlay none
termbg freeze
termbg off
```

See [termbg.md](termbg.md) for the display model, all modules, and all palettes.

---

## `wall` — one-shot background

| Invocation | What it does |
|-----------|--------------|
| `wall` | Paint one fresh termbg frame (no daemon) — same as `termbg once`. |
| `wall off` | Remove the background — same as `termbg off`. |
