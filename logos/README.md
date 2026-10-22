# Fetch logos

Text logos for the `fetch` panel, in fastfetch's format:

- `$1` … `$9` switch color. A color carries over to the next line.
- `$$` prints a literal `$`.
- Every other character prints as-is; lines are padded to the widest one.

Colors are tinted from the bedazzle accent, not fixed: `$1` accent, `$2` the
secondary hue (+55°), `$3`/`$4` light and deep accent, `$5`/`$6` light and deep
secondary, `$7`/`$8` light and dim grey, `$9` the complementary hue.
`bedazzle logo bands on` ignores the marks and stripes each logo instead.

Keep a logo at most 48 columns wide so the info column still fits beside it.

Personal logos go in `~/.config/shellwash/logos/<name>.txt`; a file there with
the same name as one here overrides it.

`tux arch debian gentoo apple puffy freebsd ubuntu rhel slackware` are from
[fastfetch](https://github.com/fastfetch-cli/fastfetch/tree/dev/src/logo/ascii),
MIT-licensed (see `LICENSE.fastfetch`). Any other fastfetch logo drops in as-is.
