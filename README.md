# ghostty-illogical-impulse

The terminal half of [end-4/dots-hyprland](https://github.com/end-4/dots-hyprland)
(illogical-impulse), ported to **Ghostty on macOS** — with zsh instead of fish.

Wallpaper-driven Material You colours, a two-line capsule prompt, and a `matcolor`
command that repaints every open terminal instantly.

## Install

```sh
git clone https://github.com/<you>/ghostty-illogical-impulse.git
cd ghostty-illogical-impulse
./install.sh
```

It installs `starship`, `eza` and JetBrains Mono Nerd Font via Homebrew, creates an
isolated Python venv for the colour generator, symlinks the configs, and appends a
block to `~/.zshrc`. Nothing is overwritten without a `.bak` copy first.

## Retheming

```sh
matcolor                              # current macOS wallpaper
matcolor ~/Pictures/wallpaper.jpg     # a specific image (HEIC/JPG/PNG/RAW)
matcolor --color '#8A8F98'            # an explicit accent, no image
matcolor --scheme scheme-neutral      # nine Material schemes; see --help
matcolor --mode light                 # default follows the macOS appearance
```

Open terminals repaint immediately via OSC sequences; new windows read the generated
theme file at launch.

> Apple's *Aerial* (video) wallpapers are streamed, not stored, so there is no image for
> `matcolor` to sample. Pass a file or use `--color` if your desktop is one.

## How it works

1. The image is quantised, a dominant colour is scored, and a Material 3 dynamic scheme
   is built around it.
2. The Gruvbox (dark) / Monokai Pro (light) base palette from upstream is *harmonised* —
   every hue rotated towards the accent, capped at `--harmonize-threshold` degrees.
3. Material roles are written into the unused tail of the 256-colour cube:

   | slot | role | slot | role |
   |---|---|---|---|
   | 255 | primary | 245 | outlineVariant |
   | 254 | primaryContainer | 244 | error |
   | 253 | secondary | 243 | primary |
   | 252 | secondaryContainer | 240 | onPrimary |
   | 251 | tertiary | 235 | onSecondaryContainer |

   `starship.toml` is written against those indices (`bg:252 fg:235`), so the prompt
   re-themes itself without ever being regenerated. That trick is upstream's, and it is
   the neatest idea in the whole project.

## If the pill caps go square

The round ends of each pill are two Private Use Area characters, **U+E0B6** and
**U+E0B4**, sitting inside the empty-looking brackets in `starship/starship.toml`.
Plenty of editors and tools silently drop that range when rewriting a file, which leaves
`[]` empty and the pill renders as a bare rectangle. Check with:

```sh
python3 -c "s=open('starship/starship.toml',encoding='utf-8').read(); \
print('caps:', s.count(chr(0xE0B6)), s.count(chr(0xE0B4)))"   # expect: caps: 5 5
```

## Deviations from upstream

- **Bright-colour boost.** Upstream multiplies HCT tone by `1 + 0.35` in dark mode. The
  Gruvbox bright colours already sit at tone 73-80, so that clamps them all to 100 and
  bright green, yellow and cyan render as identical pure white. This port interpolates
  the remaining headroom instead. `--legacy-fg-boost` restores bit-exact upstream output.
- **zsh, not fish** — same prompt, same `eza` aliases.
- **No `cursor_trail`**; Ghostty has no equivalent to kitty's trailing cursor.
- **Titlebar** is `transparent` rather than absent. `macos-titlebar-style = hidden` gives
  the fully chrome-less Hyprland look, at the cost of the window buttons.
- **Opaque background**, matching upstream's `term_alpha=100`. `background-opacity` and
  `background-blur` are commented out in `ghostty/config`.
- **`window-padding-balance` must stay false** — balancing spreads the grid's leftover
  space across all four sides, quietly inflating the top padding.

## Credit

All of the design, and the colour-generation approach, is [end-4](https://github.com/end-4)'s.
This is a port, not original work.

## Licence

MIT, matching upstream.
