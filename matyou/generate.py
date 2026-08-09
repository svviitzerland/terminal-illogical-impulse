#!/usr/bin/env python3
"""
Material You colour generation for Ghostty on macOS.

Port of end-4/dots-hyprland's `generate_colors_material.py` + `applycolor.sh`
(illogical-impulse). Extracts an accent colour from an image, builds a Material 3
dynamic scheme, harmonises a base terminal palette towards that accent, then emits:

  ~/.config/ghostty/themes/material-you   Ghostty theme file (new windows)
  ~/.local/state/matyou/sequences.txt     OSC escape sequences (live + new shells)
  ~/.local/state/matyou/colors.json       every Material colour, for other tools

The clever bit inherited from the original: ANSI slots 232-255 (the rarely-used
greys at the tail of the 256-colour cube) are overwritten with Material roles, so
a starship prompt written against `bg:252 fg:235` re-themes itself for free.
"""

import argparse
import json
import warnings
import math
import os
import subprocess
import sys
from pathlib import Path

# Pillow 14 renames getdata(); materialyoucolor still calls the old name.
warnings.filterwarnings("ignore", category=DeprecationWarning)

from PIL import Image
from materialyoucolor.quantize import QuantizeCelebi
from materialyoucolor.score.score import Score
from materialyoucolor.hct import Hct
from materialyoucolor.dynamiccolor.material_dynamic_colors import MaterialDynamicColors
from materialyoucolor.utils.color_utils import rgba_from_argb, argb_from_rgb
from materialyoucolor.utils.math_utils import (
    sanitize_degrees_double,
    difference_degrees,
    rotation_direction,
)

HOME = Path.home()
SHARE_DIR = HOME / ".local/share/matyou"
STATE_DIR = HOME / ".local/state/matyou"
THEME_FILE = HOME / ".config/ghostty/themes/material-you"
SEQ_FILE = STATE_DIR / "sequences.txt"
JSON_FILE = STATE_DIR / "colors.json"
TERMSCHEME = SHARE_DIR / "scheme-base.json"

SCHEMES = {
    "scheme-content": "scheme_content.SchemeContent",
    "scheme-expressive": "scheme_expressive.SchemeExpressive",
    "scheme-fidelity": "scheme_fidelity.SchemeFidelity",
    "scheme-fruit-salad": "scheme_fruit_salad.SchemeFruitSalad",
    "scheme-monochrome": "scheme_monochrome.SchemeMonochrome",
    "scheme-neutral": "scheme_neutral.SchemeNeutral",
    "scheme-rainbow": "scheme_rainbow.SchemeRainbow",
    "scheme-tonal-spot": "scheme_tonal_spot.SchemeTonalSpot",
    "scheme-vibrant": "scheme_vibrant.SchemeVibrant",
}

rgba_to_hex = lambda rgba: "#{:02X}{:02X}{:02X}".format(rgba[0], rgba[1], rgba[2])
argb_to_hex = lambda argb: "#{:02X}{:02X}{:02X}".format(*map(round, rgba_from_argb(argb)))
hex_to_argb = lambda h: argb_from_rgb(int(h[1:3], 16), int(h[3:5], 16), int(h[5:7], 16))
swatch = lambda h: "\x1b[48;2;{};{};{}m   \x1b[0m".format(*[int(h[i : i + 2], 16) for i in (1, 3, 5)])


# ---------------------------------------------------------------- colour maths

def calculate_optimal_size(width, height, bitmap_size):
    image_area = width * height
    bitmap_area = bitmap_size**2
    scale = math.sqrt(bitmap_area / image_area) if image_area > bitmap_area else 1
    return max(1, round(width * scale)), max(1, round(height * scale))


def harmonize(design_color, source_color, threshold=35, harmony=0.5):
    """Rotate a colour's hue towards the accent, capped at `threshold` degrees."""
    from_hct = Hct.from_int(design_color)
    to_hct = Hct.from_int(source_color)
    rotation = min(difference_degrees(from_hct.hue, to_hct.hue) * harmony, threshold)
    hue = sanitize_degrees_double(
        from_hct.hue + rotation * rotation_direction(from_hct.hue, to_hct.hue)
    )
    return Hct.from_hct(hue, from_hct.chroma, from_hct.tone).to_int()


def boost_chroma_tone(argb, chroma=1, tone=1):
    hct = Hct.from_int(argb)
    return Hct.from_hct(hct.hue, hct.chroma * chroma, hct.tone * tone).to_int()


def boost_fg(argb, boost, dark, legacy=False):
    """Push a palette entry away from the background.

    Upstream multiplies tone by (1 + boost). In dark mode that saturates: the
    Gruvbox bright colours already sit at tone 73-80, so x1.35 clamps them all to
    100 and bright green / yellow / cyan render as the same pure white. We instead
    interpolate the remaining headroom, which keeps the same direction and feel but
    never collapses distinct hues. --legacy-fg-boost restores the exact upstream maths.
    """
    hct = Hct.from_int(argb)
    if legacy:
        new_tone = hct.tone * (1 + boost * (1 if dark else -1))
    elif dark:
        new_tone = hct.tone + (100 - hct.tone) * boost
    else:
        new_tone = hct.tone * (1 - boost)
    return Hct.from_hct(hct.hue, hct.chroma, max(0.0, min(100.0, new_tone))).to_int()


def open_image(path):
    """Open any image macOS understands.

    Pillow cannot read HEIC, which is what every stock macOS wallpaper is, so fall
    back to `sips` — built in, and it also covers TIFF variants and RAW.
    """
    import tempfile

    try:
        return Image.open(path)
    except Exception:
        pass
    tmp = Path(tempfile.mkdtemp(prefix="matyou-conv-")) / "converted.png"
    result = subprocess.run(
        ["sips", "-s", "format", "png", str(path), "--out", str(tmp)],
        capture_output=True, timeout=120,
    )
    if result.returncode != 0 or not tmp.is_file():
        sys.exit(f"Could not decode image: {path}")
    return Image.open(tmp)


def image_colorfulness(path):
    """Hasler & Süsstrunk colourfulness metric — decides neutral vs tonal-spot."""
    import numpy as np

    img = open_image(path).convert("RGB")
    img.thumbnail((128, 128), Image.Resampling.LANCZOS)
    arr = np.asarray(img, dtype="float")
    R, G, B = arr[..., 0], arr[..., 1], arr[..., 2]
    rg = np.absolute(R - G)
    yb = np.absolute(0.5 * (R + G) - B)
    return math.sqrt(rg.std() ** 2 + yb.std() ** 2) + 0.3 * math.sqrt(
        rg.mean() ** 2 + yb.mean() ** 2
    )


# ------------------------------------------------------------- macOS interrupts

WALLPAPER_INDEX = HOME / "Library/Application Support/com.apple.wallpaper/Store/Index.plist"
AERIAL_DIRS = [
    Path("/Library/Application Support/com.apple.idleassetsd/Customer"),
    HOME / "Library/Application Support/com.apple.idleassetsd/Customer",
]


def _wallpaper_via_applescript():
    try:
        out = subprocess.run(
            ["osascript", "-e",
             'tell application "System Events" to tell current desktop to get picture'],
            capture_output=True, text=True, timeout=10,
        )
        path = out.stdout.strip()
        return path if path and path != "missing value" and os.path.isfile(path) else None
    except Exception:
        return None


def _wallpaper_choice():
    """Read the Sonoma+ wallpaper store, which AppleScript no longer reports."""
    import plistlib

    if not WALLPAPER_INDEX.is_file():
        return None
    try:
        data = plistlib.load(WALLPAPER_INDEX.open("rb"))
    except Exception:
        return None
    for key in ("AllSpacesAndDisplays", "SystemDefault"):
        linked = data.get(key, {}).get("Linked", {})
        for choice in linked.get("Content", {}).get("Choices", []):
            yield choice


def _wallpaper_via_store():
    for choice in _wallpaper_choice() or []:
        for f in choice.get("Files", []):
            path = f.get("relative", "") if isinstance(f, dict) else str(f)
            path = path.replace("file://", "")
            if path and os.path.isfile(path):
                return path
    return None


def _wallpaper_via_aerial():
    """Apple's Aerial wallpapers are .mov files; grab a poster frame via Quick Look."""
    import plistlib
    import tempfile

    asset_id = None
    for choice in _wallpaper_choice() or []:
        if "aerials" not in choice.get("Provider", ""):
            continue
        cfg = choice.get("Configuration")
        if isinstance(cfg, bytes):
            try:
                asset_id = plistlib.loads(cfg).get("assetID")
            except Exception:
                pass
    if not asset_id:
        return None

    movie = None
    for root in AERIAL_DIRS:
        if root.is_dir():
            for candidate in root.rglob(f"*{asset_id}*"):
                if candidate.suffix.lower() in (".mov", ".mp4", ".heic", ".jpg", ".png"):
                    movie = candidate
                    break
        if movie:
            break
    if not movie:
        return None
    if movie.suffix.lower() in (".heic", ".jpg", ".png"):
        return str(movie)

    out_dir = Path(tempfile.mkdtemp(prefix="matyou-aerial-"))
    subprocess.run(["qlmanage", "-t", "-s", "512", "-o", str(out_dir), str(movie)],
                   capture_output=True, timeout=60)
    thumbs = list(out_dir.glob("*.png"))
    return str(thumbs[0]) if thumbs else None


def macos_wallpaper():
    for resolver in (_wallpaper_via_applescript, _wallpaper_via_store, _wallpaper_via_aerial):
        try:
            path = resolver()
        except Exception:
            path = None
        if path:
            return path
    return None


def macos_dark_mode():
    out = subprocess.run(
        ["defaults", "read", "-g", "AppleInterfaceStyle"], capture_output=True, text=True
    )
    return out.stdout.strip() == "Dark"


def live_reload(seq_bytes):
    """Push the palette into every already-open terminal via its pty.

    Must be non-blocking: a plain open() on a pty slave waits for carrier and will
    hang forever on idle devices, and O_NOCTTY stops us adopting one as our own
    controlling terminal.
    """
    applied = 0
    for tty in sorted(Path("/dev").glob("ttys*")):
        fd = None
        try:
            fd = os.open(tty, os.O_WRONLY | os.O_NONBLOCK | os.O_NOCTTY)
            if not os.isatty(fd):
                continue
            os.write(fd, seq_bytes)
            applied += 1
        except OSError:
            pass  # not ours, nothing attached, or the write buffer is full
        finally:
            if fd is not None:
                try:
                    os.close(fd)
                except OSError:
                    pass
    return applied


# ------------------------------------------------------------------------- main

def main():
    p = argparse.ArgumentParser(description="Generate a Material You theme for Ghostty")
    src = p.add_mutually_exclusive_group()
    src.add_argument("image", nargs="?", help="image to derive colours from (default: current wallpaper)")
    src.add_argument("--color", help="use an explicit hex accent instead of an image, e.g. #7B4FA8")
    p.add_argument("--mode", choices=["dark", "light", "auto"], default="auto",
                   help="auto follows macOS appearance (default)")
    p.add_argument("--scheme", default="auto",
                   help="one of %s, or auto" % ", ".join(SCHEMES))
    p.add_argument("--size", type=int, default=128, help="quantisation bitmap size")
    p.add_argument("--harmony", type=float, default=0.6, help="0-1 hue shift towards accent")
    p.add_argument("--harmonize-threshold", type=float, default=100, help="0-180 max hue shift")
    p.add_argument("--term-fg-boost", type=float, default=0.35, help="push fg away from bg")
    p.add_argument("--legacy-fg-boost", action="store_true",
                   help="use upstream's tone multiply (blows bright colours out to white)")
    p.add_argument("--no-blend-bg-fg", action="store_true",
                   help="keep the base scheme's background instead of the Material surface")
    p.add_argument("--background", metavar="HEX",
                   help="pin the terminal background to an exact colour (e.g. '#1A1A1A') "
                        "instead of deriving it from surfaceContainerLow")
    p.add_argument("--opacity", type=int, default=100, help="background alpha 0-100 for OSC 11")
    p.add_argument("--no-reload", action="store_true", help="write files but don't touch open terminals")
    p.add_argument("--quiet", action="store_true")
    args = p.parse_args()

    dark = macos_dark_mode() if args.mode == "auto" else args.mode == "dark"
    blend_bg_fg = not args.no_blend_bg_fg

    # ---- source colour
    image_path = None
    if args.color:
        argb = hex_to_argb(args.color if args.color.startswith("#") else "#" + args.color)
    else:
        image_path = args.image or macos_wallpaper()
        if not image_path:
            sys.exit(
                "Could not sample the current wallpaper.\n"
                "Apple's Aerial (video) wallpapers are streamed, so there is no local image "
                "to read colours from.\n"
                "Point at an image instead:  matcolor ~/Pictures/wallpaper.jpg\n"
                "or set an accent directly:  matcolor --color '#7B4FA8'"
            )
        if not os.path.isfile(image_path):
            sys.exit(f"No such image: {image_path}")
        image = open_image(image_path)
        if image.format == "GIF":
            image.seek(1)
        if image.mode in ("L", "P"):
            image = image.convert("RGB")
        image = image.convert("RGB")
        w, h = image.size
        nw, nh = calculate_optimal_size(w, h, args.size)
        if nw < w or nh < h:
            image = image.resize((nw, nh), Image.Resampling.BICUBIC)
        argb = Score.score(QuantizeCelebi(list(image.getdata()), 128))[0]

    hct = Hct.from_int(argb)

    # ---- scheme choice
    scheme_name = args.scheme
    if scheme_name == "auto":
        if image_path:
            try:
                scheme_name = "scheme-neutral" if image_colorfulness(image_path) < 40 else "scheme-tonal-spot"
            except Exception:
                scheme_name = "scheme-tonal-spot"
        else:
            scheme_name = "scheme-neutral" if hct.chroma < 20 else "scheme-tonal-spot"
    if scheme_name not in SCHEMES:
        sys.exit(f"Unknown scheme {scheme_name!r}. Choose from: {', '.join(SCHEMES)}, auto")

    module, cls = SCHEMES[scheme_name].split(".")
    Scheme = getattr(__import__(f"materialyoucolor.scheme.{module}", fromlist=[cls]), cls)
    scheme = Scheme(hct, dark, 0.0)

    # ---- material roles
    material = {}
    for name in vars(MaterialDynamicColors).keys():
        role = getattr(MaterialDynamicColors, name)
        if hasattr(role, "get_hct"):
            material[name] = rgba_to_hex(role.get_hct(scheme).to_rgba())

    if dark:
        material.update(success="#B5CCBA", onSuccess="#213528",
                        successContainer="#374B3E", onSuccessContainer="#D1E9D6")
    else:
        material.update(success="#4F6354", onSuccess="#FFFFFF",
                        successContainer="#D1E8D5", onSuccessContainer="#0C1F13")

    # ---- terminal palette, harmonised towards the accent
    base = json.loads(TERMSCHEME.read_text())["dark" if dark else "light"]
    key_color = material.get("primaryPaletteKeyColor") or material["primary"]
    primary_argb = hex_to_argb(key_color)

    term = {}
    for name, val in base.items():
        if scheme_name == "scheme-monochrome":
            term[name] = val
            continue
        if blend_bg_fg and name == "term0":
            out = boost_chroma_tone(hex_to_argb(material["surfaceContainerLow"]), 1.2, 0.95)
        elif blend_bg_fg and name == "term15":
            out = boost_chroma_tone(hex_to_argb(material["onSurface"]), 3, 1)
        else:
            out = harmonize(hex_to_argb(val), primary_argb, args.harmonize_threshold, args.harmony)
            out = boost_fg(out, args.term_fg_boost, dark, args.legacy_fg_boost)
        term[name] = argb_to_hex(out)

    # A pinned background wins over the derived surface tint. Applied after the loop so
    # the other fifteen colours are still harmonised against the accent as usual.
    if args.background:
        bg_hex = args.background if args.background.startswith("#") else "#" + args.background
        if len(bg_hex) != 7:
            sys.exit(f"--background expects a 6-digit hex colour, got {args.background!r}")
        term["term0"] = bg_hex.upper()

    # ---- the slot-hijack map: rarely-used ANSI indices carry Material roles
    overrides = {
        255: material["primary"],            254: material["primaryContainer"],
        253: material["secondary"],          252: material["secondaryContainer"],
        251: material["tertiary"],           250: material["tertiaryContainer"],
        249: material["error"],              248: material["errorContainer"],
        245: material["outlineVariant"],     244: material["error"],
        243: material["primary"],            240: material["onPrimary"],
        239: material["onErrorContainer"],   238: material["onError"],
        237: material["onTertiaryContainer"],236: material["onTertiary"],
        235: material["onSecondaryContainer"],234: material["onSecondary"],
        233: material["onPrimaryContainer"], 232: material["onPrimary"],
    }

    fg, bg = term["term7"], term["term0"]

    # ---- Ghostty theme file
    lines = [
        "# Generated by matcolor — Material You, ported from end-4/dots-hyprland.",
        "# Do not edit; it is overwritten on every run.",
        f"# source: {image_path or key_color}   scheme: {scheme_name}   mode: {'dark' if dark else 'light'}",
        "",
        f"background = {bg}",
        f"foreground = {fg}",
        f"cursor-color = {fg}",
        f"selection-background = {material['onSecondaryContainer']}",
        f"selection-foreground = {material['secondaryContainer']}",
        "",
    ]
    for i in range(16):
        lines.append(f"palette = {i}={term['term%d' % i]}")
    lines.append("")
    lines.append("# Material roles parked in unused slots so starship re-themes for free")
    for idx in sorted(overrides, reverse=True):
        lines.append(f"palette = {idx}={overrides[idx]}")
    THEME_FILE.parent.mkdir(parents=True, exist_ok=True)
    THEME_FILE.write_text("\n".join(lines) + "\n")

    # ---- OSC sequences for terminals that are already open
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    osc = []
    for i in range(16):
        osc.append(f"\033]4;{i};{term['term%d' % i]}\033\\")
    for idx, val in overrides.items():
        osc.append(f"\033]4;{idx};{val}\033\\")
    osc.append(f"\033]10;{fg}\033\\")                       # foreground
    # The [alpha] prefix is a kitty extension; plain OSC 11 keeps Ghostty happy.
    bg_spec = bg if args.opacity >= 100 else f"[{args.opacity}]{bg}"
    osc.append(f"\033]11;{bg_spec}\033\\")                  # background
    osc.append(f"\033]12;{fg}\033\\")                       # cursor
    osc.append(f"\033]17;{material['onSecondaryContainer']}\033\\")  # selection bg
    osc.append(f"\033]19;{material['secondaryContainer']}\033\\")    # selection fg
    seq = "".join(osc)
    SEQ_FILE.write_text(seq)

    JSON_FILE.write_text(json.dumps(
        {"mode": "dark" if dark else "light", "scheme": scheme_name,
         "source": image_path or key_color, "accent": argb_to_hex(argb),
         "material": material, "terminal": term}, indent=2))

    applied = 0 if args.no_reload else live_reload(seq.encode())

    if not args.quiet:
        print(f"  accent   {swatch(argb_to_hex(argb))} {argb_to_hex(argb)}   "
              f"H {hct.hue:.0f}  C {hct.chroma:.0f}  T {hct.tone:.0f}")
        print(f"  scheme   {scheme_name}, {'dark' if dark else 'light'}")
        print(f"  source   {image_path or key_color}")
        print("  palette  " + "".join(swatch(term[f'term{i}']) for i in range(16)))
        print(f"  wrote    {THEME_FILE}")
        if applied:
            print(f"  reloaded {applied} open terminal(s)")


if __name__ == "__main__":
    main()
