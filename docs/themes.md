# Themes & Accent

## The theme manager

bedazzle treats the prompt as three cases:

| Theme | What it is |
|-------|-----------|
| `p10k` (a.k.a. `powerlevel10k`) | **The default.** Your existing powerlevel10k config drives the prompt; bedazzle only layers addons (corner buddy, hooks, termbg feed) on top. |
| `bedazzle` | The minimal one-accent prompt: shortened path (+git +venv) on the left; duration · status · clock · battery · weather right-aligned. |
| any other name | Treated as an **oh-my-zsh theme** — the manager looks for `<name>.zsh-theme` in `$ZSH_CUSTOM/themes`, `$ZSH/custom/themes`, and `$ZSH/themes`. |

Switch with `bedazzle theme <name>`. `bedazzle theme random` rolls among
`bedazzle`, `p10k`, and every installed omz theme (the omz `example`
placeholder is excluded). `bedazzle theme` / `bedazzle theme list` prints the
options plus your available omz themes and marks the current one.

### Linux vs Windows

- **Linux.** Changing theme is persisted and then the shell is re-exec'd
  (`exec zsh`) so the handoff between p10k and another theme is clean.
  `init.zsh` re-applies your saved choice at startup.
- **Windows.** The bedazzle prompt is always active (there is no p10k on
  Windows). Theme switching is a Linux-only feature.

## The accent color

`bedazzle accent <name|hue>` sets a single hue (0–360) that drives:

- The bedazzle prompt's accent color
- The fetch panel's accent strip
- The buddy's tint (for pets that use it)
- The `accent` termbg palette
- p10k segment tinting (Linux only, when `accent_p10k` is on)

Named hues: `blue`(215) `violet`(270) `green`(140) `amber`(45) `red`(2)
`cyan`(185) `pink`(330), or any number `0–360`.

```
bedazzle accent violet
bedazzle accent 330
```

The accent is persisted in `bedazzle.config.json`.
