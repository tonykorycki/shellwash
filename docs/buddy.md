# The Buddy

Reactive ASCII pet in the top-right corner.

- `buddy` - gallery, hats, roll odds.
- `buddy roll` - gacha buddy + hat.
- `bedazzle sprite <name>` / `bedazzle hat <name>` - pick directly.
- `pet` - toggle corner buddy (`bedazzle on/off sprite` is the same).

## The roster (18)

`duck · goose · blob · cat · dragon · octopus · owl · penguin · turtle · snail ·
ghost · axolotl · capybara · cactus · robot · rabbit · mushroom · chonk`

Default buddy: `cat`. `bedazzle sprite random` picks one at random. Each buddy
has its own color and its own eye art for the reaction states.

## Hats & rarity

Hats are drawn from a gacha pool. Each has a rarity, shown in its rarity color
in the `buddy` gallery.

| Hat | Rarity |
|-----|--------|
| `beanie` | uncommon |
| `propeller` | uncommon |
| `tophat` | rare |
| `tinyduck` | rare |
| `crown` | epic |
| `wizard` | epic |
| `halo` | legendary |

## Roll odds

`buddy roll` (and the daily hat) draw from this table:

| Result | Chance | Hats in tier |
|--------|:------:|--------------|
| **common** (bare-headed) | 60% | — |
| **uncommon** | 25% | beanie, propeller |
| **rare** | 10% | tophat, tinyduck |
| **epic** | 4% | crown, wizard |
| **legendary** | 1% | halo |

The buddy itself in a roll is chosen uniformly from the roster; only the hat is
rarity-weighted.

## The daily hat

With `bedazzle hat daily` (the default), a hat is rolled once per day using the
same odds, seeded by the calendar date plus your username — so everyone's daily
hat is a fresh surprise, stable for that whole day. `bedazzle hat <name>` pins a
specific hat; `bedazzle hat none` goes bare-headed; `bedazzle hat daily` returns
to the daily draw.

## Reactions

The buddy picks a face each prompt based on the last command and recent state:

| State | Trigger | Look |
|-------|---------|------|
| `fail` | Last command exited non-zero (holds ~7s) | Startled eyes + `!` |
| `notify` | Your open-PR review-comment count just climbed (needs `pet_github` + `gh`) | Happy eyes + `✉!` |
| `happy` | The last command ran longer than 10s (holds ~7s) | `^ ^` eyes |
| `sleep` | Idle 4+ minutes | Closed eyes + `zZ` |
| `blink` | Occasional random blink | Closed eyes for one tick |
| `idle` | Otherwise | Normal eyes |

## How it renders

- **Linux — inline corner buddy.** `ad_buddy_precmd` (a precmd hook in
  `linux/hooks.zsh`) paints the buddy in the top-right corner once per prompt,
  in **every** theme (p10k included). It saves/restores the cursor so it
  overlays without consuming a prompt line, and wipes a fixed box first so the
  current buddy is always clean; old copies just scroll into history. The buddy
  art is pre-rendered once by `pet.py render` and cached in zsh (rebuilt when
  the sprite/hat/accent changes), so there's no per-prompt Python and no fragile
  re-encoding of the art in the shell. It is **skipped on the very first
  prompt** so it never trips p10k's instant-prompt "console output" warning.
- **Windows — pinned daemon.** `pet` launches `pet.py` as a background daemon
  that repaints one buddy at a fixed top-right spot and animates in real time
  (blinks, tail flicks, reactions), reading `pet.json` which the prompt writes
  after each command. Only glyphs are painted and it erases exactly what it
  painted, so there are no duplicates in scrollback.

Both paths use the exact same roster and art (defined once in `pet.py`
`BUDDIES`), so a buddy looks identical inline and pinned.
