# Commands Reference

Every user-facing command. Run `bedazzle` alone for a live cheat-sheet.

---

## `bedazzle`

| Invocation | What it does |
|-----------|--------------|
| `bedazzle` (or `help` / `list`) | Feature list with on/off state + cheat-sheet. |
| `bedazzle on <feature>` | Turn a feature on (persisted). |
| `bedazzle off <feature>` | Turn a feature off (persisted). |
| `bedazzle theme <name\|random\|list>` | Switch prompt theme. |
| `bedazzle accent <name\|hue>` | Set accent color. |
| `bedazzle sprite <name>` | Choose buddy (`buddy` shows roster). |
| `bedazzle hat <name>` | Choose hat: `daily`, `none`, or a name. |
| `bedazzle stats` | Session stats. |
| `bedazzle logo [name\|random]` | Pick the fetch image (Linux/macOS). |

**Features** (for `on`/`off`): `fetch sprite rightinfo git venv shortpath title
airy battery weather spirits rule`, plus on **Linux only**: `accent_p10k
pet_github termbg_auto`. See [features.md](features.md).

**`bedazzle theme`**
- `bedazzle theme` / `list` - themes and available omz themes.
- `bedazzle theme p10k` - powerlevel10k (default).
- `bedazzle theme bedazzle` - minimal accent prompt.
- `bedazzle theme <omz-name>` - any oh-my-zsh theme.
- `bedazzle theme random` - roll a theme.
- On Linux, switching re-execs the shell (`exec zsh`). See [themes.md](themes.md).

**`bedazzle accent`**: `blue`(215) `violet`(270) `green`(140) `amber`(45)
`red`(2) `cyan`(185) `pink`(330), or any hue `0–360`.

**`bedazzle logo`** (Linux/macOS)
- `bedazzle logo` - list logos, the current one, and the random pool.
- `bedazzle logo <name>` - always use that logo.
- `bedazzle logo random` - roll a logo from the pool on every launch.
- `bedazzle logo pool <names…>` - set the pool; `pool add|rm <names…>` edits it,
  `pool all` resets it to every logo.
- `bedazzle logo gallery` - preview every logo side by side; pool members in accent.

Logos: `planet synthwave blackhole scope torus mushroom`, all tinted to the accent.
Adding one: write a function `hue -> grid` in `linux/logos.py` and register it in `LOGOS`.

**`bedazzle stats`**
- Linux: theme, accent swatch, current sprite.
- Windows: session length, command count, failures, duration sparkline.

---

## `buddy`

| Invocation | What it does |
|-----------|--------------|
| `buddy` | Gallery, hats, roll odds, today's buddy/hat. |
| `buddy roll` | Gacha: random buddy + hat, saved as current. |

See [buddy.md](buddy.md).

---

## `pet`

| Invocation | What it does |
|-----------|--------------|
| `pet` | Toggle corner buddy. |
| `pet on` / `pet off` | Show or hide. |

Linux: inline corner buddy every prompt. Windows: pinned `pet.py` daemon.
Equivalent to `bedazzle on/off sprite`.

---

## `fetch`

```
fetch                  panel with the configured logo
fetch --logo <name>    panel with a specific logo, without saving it
fetch --gallery        every logo side by side
```

fastfetch-style panel in your accent hue. On login when the `fetch` toggle is on.
The image comes from `bedazzle logo`.

---

## `lava`

| Invocation | What it does |
|-----------|--------------|
| `lava` | Toggle corner metaballs lamp. |
| `lava on` / `lava off` | Start or stop. |

---

## `hr`

```
hr
```

Full-width gradient rule. No args.

---

## `termbg`

| Invocation | What it does |
|-----------|--------------|
| `termbg` / `termbg status` | Current state, modules, palettes. |
| `termbg on` | Start daemon; evolves per command. |
| `termbg freeze` | Stop evolving; keep image. |
| `termbg off` | Stop and remove background. |
| `termbg once` | One frame, no daemon. |
| `termbg use <module>` | Switch visual module. |
| `termbg palette <name>` | Switch palette. |
| `termbg opacity <0.05–0.6>` | Show-through strength. |
| `termbg overlay <exitcode\|none>` | Failure vignette or none. |

See [termbg.md](termbg.md).

---

## `wall`

| Invocation | What it does |
|-----------|--------------|
| `wall` | Same as `termbg once`. |
| `wall off` | Same as `termbg off`. |
