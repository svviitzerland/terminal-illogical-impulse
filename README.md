# terminal-illogical-impulse

The terminal look of [end-4/dots-hyprland](https://github.com/end-4/dots-hyprland)
(illogical-impulse), ported to **macOS Terminal.app** — with zsh instead of fish.

Wallpaper-driven Material You colours, a two-line capsule starship prompt, and a
`matcolor` command that repaints every open terminal instantly.

> Earlier versions of this repo targeted Ghostty. That is gone; the design is the same,
> the target is now the stock Terminal.app. The Ghostty config is still in the git
> history if you want it back.

## Install

```sh
git clone https://github.com/<you>/terminal-illogical-impulse.git
cd terminal-illogical-impulse
./install.sh
```

Installs `starship`, `eza` and JetBrains Mono Nerd Font via Homebrew, creates an
isolated Python venv for the colour generator, links the configs, and appends a block to
`~/.zshrc`. Anything it replaces is backed up with a timestamped `.bak` first.

## Retheming

```sh
matcolor                              # current macOS wallpaper
matcolor ~/Pictures/wallpaper.jpg     # a specific image (HEIC/JPG/PNG/RAW)
matcolor --color '#8A8F98'            # an explicit accent, no image
matcolor --background '#1A1A1A'       # pin the background exactly
matcolor --scheme scheme-neutral      # nine Material schemes; see --help
matcolor --mode light                 # default follows the macOS appearance
```

Open windows repaint immediately. `matcolor` also rewrites your Terminal.app profile,
which new windows pick up — see below for why both are needed.

Baseline flags live in one line near the top of `matyou/matcolor`:

```sh
: "${MATYOU_DEFAULTS:=--scheme scheme-neutral --background #1A1A1A}"
```

Flags passed on the command line still win, since argparse takes the last occurrence.

> Apple's *Aerial* (video) wallpapers are streamed, not stored, so there is no image for
> `matcolor` to sample. Pass a file or use `--color` if your desktop is one.

## Why Terminal.app needs two mechanisms

Terminal.app honours **OSC 4**, so the sixteen ANSI colours plus the hijacked 232–255
slots are set by escape sequences that `~/.zshrc` emits at every shell start. That is
what repaints already-open windows.

It does **not** honour OSC 10/11 for its own default background and text colour — those
live in the profile, and Terminal.app has no config file for them. So `matcolor` also
drives the profile over AppleScript. Without that half, the font stays SF Mono and every
Nerd Font glyph renders as tofu.

Skip it with `--no-terminal-app`, or target a specific profile with
`--terminal-profile "Basic"`.

## How the colours work

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

## Stray `[` and `]` around the command you just ran

Terminal.app auto-marks every prompt line and draws that mark as a bracket pair at the
far left and far right of the line. With a two-line prompt it reads as a stray `[` and
`]` wrapping your command. They are drawn decoration, not text — they never appear in
the scrollback buffer, which is what makes this confusing to chase.

`set-default-terminal.sh` turns it off, or do it by hand:

```sh
defaults write com.apple.Terminal AutoMarkPromptLines -bool false
```

Quit Terminal.app completely (Cmd-Q) afterwards. There is no key that keeps the marks
while hiding the indicator, so the cost is that Cmd-Up / Cmd-Down prompt navigation and
Cmd-L "clear to previous mark" lose their automatic anchors.

## If the pill caps go square

The round ends of each pill are two Private Use Area characters, **U+E0B6** and
**U+E0B4**, sitting inside the empty-looking brackets in `starship/starship.toml`.
Plenty of editors and tools silently drop that range when rewriting a file, which leaves
`[]` empty and the pill renders as a bare rectangle. Check with:

```sh
python3 -c "s=open('starship/starship.toml',encoding='utf-8').read(); \
print('caps:', s.count(chr(0xE0B6)), s.count(chr(0xE0B4)))"   # expect: caps: 5 5
```

## Default terminal

```sh
./set-default-terminal.sh
```

Sets the LaunchServices handler for `.sh`, `.zsh`, `.command`, `.tool` and unix
executables to Terminal.app. Two things it cannot do: `.bash` (Terminal.app does not
declare `public.bash-script`, so LaunchServices refuses it), and Finder's *New Terminal
at Folder* service, which macOS hardcodes.

## Deviations from upstream

- **Bright-colour boost.** Upstream multiplies HCT tone by `1 + 0.35` in dark mode. The
  Gruvbox bright colours already sit at tone 73–80, so that clamps them all to 100 and
  bright green, yellow and cyan render as identical pure white. This port interpolates
  the remaining headroom instead. `--legacy-fg-boost` restores bit-exact upstream output.
- **zsh, not fish** — same prompt, same `eza` aliases.
- **Pinned background.** `--background` overrides the derived surface tint, which
  otherwise pulls the background towards the accent and fights a neutral palette.

## Credit

All of the design, and the colour-generation approach, is [end-4](https://github.com/end-4)'s.
This is a port, not original work.

## Licence

MIT, matching upstream.
