# Tests

Two layers, because they answer different questions.

```bash
bash tests/run.sh            # fixture suites — run anywhere, no Mac needed
bash tests/macos-smoke.sh    # run ON a Mac; read-only, changes nothing
```

## `run.sh` — fixture suites

| File | Covers |
|------|--------|
| `test_fetch_macos.py` | The macOS system-fact parsers in `linux/fetch.py` — `sysctl`, `vm_stat`, `pmset`, `system_profiler` — against verbatim output fixtures. Plus a Linux regression check. |
| `test_prompt.zsh` | The battery chip in `linux/prompt.zsh`: sysfs on Linux, `pmset` on macOS, and the 60s cache. Both paths run on any platform via `$AD_BAT_SYSFS` and a stub `pmset`. |

These pin **how output is parsed**. They cannot tell you whether the real
tools on a real Mac emit that output — see the smoke check for that half.

Fixtures worth knowing about, because they encode things that have bitten:

- `vm_stat` on Apple Silicon uses **16 KiB** pages, Intel uses 4 KiB. The page
  size must be read from the header, never assumed.
- `kern.boottime` contains both `sec` and `usec` — a loose regex latches onto
  the wrong one.
- `pmset` on a desktop Mac prints no percentage at all. That must yield "no
  battery", not `0`.
- `ad_battery_pct` keeps its cache in globals, so calling it as
  `$(ad_battery_pct)` silently defeats the cache and forks `pmset` on every
  prompt. `test_prompt.zsh` asserts this directly.

### Keeping them honest

The suites were checked by mutation — deliberately breaking the source and
confirming a test goes red. All 11 mutants tried are caught:

| Mutation | Caught by |
|----------|-----------|
| `##*[^0-9]` → `#*[^0-9]` (digit extraction) | 5 assertions |
| stale-value reset dropped | `no battery -> empty, not stale value` |
| sysfs branch falls through to `pmset` | `reads capacity from sysfs` |
| cache window 60s → 0s | `5 more calls still one fork` |
| cache timestamp never stamped | `cache timestamp persisted in caller` |
| `(N)` glob qualifier dropped | `no-battery path is silent on stderr` |
| Apple Silicon no longer skips `system_profiler` | `test_gpu_apple_silicon_skips_system_profiler` |
| page size assumed instead of parsed | `test_mem_falls_back_to_4k_pages_without_header` |
| `used` no longer capped at total | `test_mem_used_never_exceeds_total` |
| boottime regex matches `usec` | `test_uptime_matches_sec_not_usec` |
| wired pages omitted from "used" | `test_mem_apple_silicon_16k_pages` |

If you add a parser, add a mutant and check it goes red before trusting it.

Two harness traps found while building this, worth not re-introducing:

- `setopt err_return` turns an assertion failure into a **silent abort with no
  output**, which reads like a pass. `test_prompt.zsh` deliberately does not
  set it, and asserts return codes explicitly instead.
- An unmatched glob **terminates a zsh script outright**. The `(N)` assertion
  runs in a subshell so the abort can't take the suite with it, and `run.sh`
  treats a suite that exits without printing its summary as a failure.

## `macos-smoke.sh` — the part fixtures can't do

Run on any Mac. It installs nothing, writes nothing outside a temp file, and
touches no config. It prints raw tool output next to what shellwash parsed
from it, so a wrong assumption is visible by eye, and flags the specific
portability hazards (BSD `mktemp`, `zstat` availability, kitty's app bundle,
which `kitty.conf` is live).

Compare `memory` against Activity Monitor's "Memory Used" and the rest
against About This Mac. Send back the whole output.
