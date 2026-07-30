# Feature Toggles

Every feature is individually togglable and persisted in `bedazzle.config.json`.
Toggle with `bedazzle on <feature>` / `bedazzle off <feature>`, and see all
current states with `bedazzle`.

## The flags

| Feature | Default | What it does |
|---------|:-------:|--------------|
| `fetch` | on | Prints the fastfetch-style system panel on login/startup. |
| `sprite` | on | Shows the inline corner buddy in the prompt. |
| `rightinfo` | on | Right-aligned duration + exit-status + clock (+ battery/weather) block. Bedazzle theme. |
| `git` | on | Branch name (+ merge/rebase state) in the prompt. |
| `venv` | on | Python virtualenv chip (⚡name). |
| `shortpath` | on | Fish-style path compression (first-letters the middle segments). |
| `title` | on | Window / tab title follows the current folder. |
| `airy` | on | Adds a blank line of breathing room above the prompt. |
| `battery` | on | Battery % in the right-info block, when a battery is present (red under 20%). |
| `weather` | on | Cached wttr.in temperature in the panel and right-info block (needs `curl`). |
| `spirits` | **off** | Kaomoji "visitors" (v1 legacy). |
| `rule` | **off** | Full-width gradient rule line above the prompt (v1 legacy). |

### Linux-only flags

These three exist only in the Linux config (`linux/adconf.py`); Windows has no
equivalent.

| Feature | Default | What it does |
|---------|:-------:|--------------|
| `accent_p10k` | **off** | Tint powerlevel10k's key segments (dir, clean VCS, virtualenv, prompt char) with your accent hue. Best-effort; p10k configs vary. Only applies while the theme is p10k. |
| `pet_github` | on | Pet reacts to git state and GitHub PR comments. Needs `gh auth login`. |
| `termbg_auto` | on | Auto-start termbg on login when kitty or WT is present. |

## Notes

- Many of these (`rightinfo`, `git`, `venv`, `shortpath`, `airy`, `battery`,
  `weather`) shape the **bedazzle** prompt specifically. If you're on p10k, its
  own config governs the prompt; only `sprite`, `title`, and (on Linux)
  `accent_p10k` / `pet_github` / `termbg_auto` still act.
- `weather` is cached to `bedazzle.weather.txt` and refreshed in the background
  at most every 30 minutes.
- Changes take effect on the next prompt (some, like theme, re-exec the shell on
  Linux — see [themes.md](themes.md)).
