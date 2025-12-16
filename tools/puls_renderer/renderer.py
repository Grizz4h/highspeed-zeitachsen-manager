import json
import random
import re

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Any, Optional, Tuple, List

from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageChops

from .layout_config import MatchdayLayoutV1
from .adapter import convert_generator_json_to_matchday


# ----------------------------
# Paths
# ----------------------------
@dataclass
class RenderPaths:
    base_dir: Path

    @property
    def templates_dir(self) -> Path:
        return self.base_dir / "assets" / "templates"

    @property
    def logos_dir(self) -> Path:
        return self.base_dir / "assets" / "logos"

    @property
    def fonts_dir(self) -> Path:
        return self.base_dir / "assets" / "fonts"

    @property
    def output_dir(self) -> Path:
        return self.base_dir / "output"


# ----------------------------
# Helpers: IO / Fonts
# ----------------------------
def _load_team_meta(assets_dir: Path) -> dict:
    p = assets_dir / "team_meta.json"
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}



def _safe_load_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _load_font(font_path: Path, size: int) -> ImageFont.FreeTypeFont:
    if not font_path.exists():
        raise FileNotFoundError(f"Font not found: {font_path}")
    return ImageFont.truetype(str(font_path), size)

def _text_width_singleline(draw, s: str, font) -> int:
    # textlength crasht bei multiline -> hier nur singleline messen
    return int(draw.textlength(s, font=font))


def _fit_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    font_path: Path,
    max_width: int,
    start_size: int,
    min_size: int = 18,
) -> ImageFont.FreeTypeFont:
    size = start_size
    while size >= min_size:
        font = _load_font(font_path, size)
                # multiline-safe: max width der einzelnen Zeilen messen
        lines = str(text).split("\n")
        w = max((_text_width_singleline(draw, line, font) for line in lines), default=0)

        if w <= max_width:
            return font
        size -= 2
    return _load_font(font_path, min_size)

import re
def _text_w(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont) -> int:
    # PIL-sicher (auch bei Sonderzeichen). Kein multiline hier!
    bbox = draw.textbbox((0, 0), text, font=font)
    return int(bbox[2] - bbox[0])


def _split_first_last(fake_name: str) -> tuple[str, str]:
    fake_name = (fake_name or "").strip()
    if not fake_name:
        return "", ""
    parts = fake_name.split()
    if len(parts) == 1:
        return parts[0], ""
    return " ".join(parts[:-1]), parts[-1]


def _truncate_line(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, max_w: int) -> str:
    if _text_w(draw, text, font) <= max_w:
        return text
    ell = "…"
    lo, hi = 0, len(text)
    while lo < hi:
        mid = (lo + hi) // 2
        cand = text[:mid].rstrip() + ell
        if _text_w(draw, cand, font) <= max_w:
            lo = mid + 1
        else:
            hi = mid
    return text[: max(0, lo - 1)].rstrip() + ell


def _split_first_last(full: str) -> tuple[str, str]:
    """
    Split in Vorname / Nachname.
    Bei mehr als 2 Wörtern: alles bis auf letztes Wort = Vorname, letztes Wort = Nachname.
    """
    s = (full or "").replace("_", " ").strip()
    if not s:
        return "", ""
    parts = s.split()
    if len(parts) == 1:
        return parts[0], ""
    return " ".join(parts[:-1]), parts[-1]

def _draw_watermark(
    img: Image.Image,
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.FreeTypeFont,
    margin: int = 24,
    opacity: int = 110,
):
    w, h = img.size
    tw = draw.textlength(text, font=font)
    th = font.size

    x = w - tw - margin
    y = h - th - margin

    draw.text(
        (x, y),
        text,
        font=font,
        fill=(255, 255, 255, opacity),
    )



def _draw_player_block_centered(
    img: Image.Image,
    draw: ImageDraw.ImageDraw,
    center: tuple[int, int],
    number: str,
    fake_name: str,
    font: ImageFont.FreeTypeFont,
    fill: tuple[int, int, int, int],
    max_width: int = 360,
    gap_px: int = 1,         # Abstand zwischen Nummer und Name (horizontal)
    line_gap_px: int = 36,    # Abstand zwischen Vor- und Nachname (vertikal)
    stroke: bool = True,
    stroke_width: int = 3,
    stroke_fill: tuple[int, int, int, int] = (0, 0, 0, 170),
) -> None:
    """
    Layout (linksbündig, aber Block zentriert):
      #31  VORNAME
           NACHNAME
    Nachname startet exakt unter dem Vornamen (Indent = Breite von "#31 ").
    """
    cx, cy = center

    num = (number or "").strip()
    first, last = _split_first_last(fake_name)

    first = (first or "").upper().strip()
    last  = (last or "").upper().strip()

    prefix = f"#{num} " if num else ""
    prefix = prefix.upper()

    # --- Truncate (WICHTIG: nur EINZEILIG messen, kein \n) ---
    # Erwartet: _truncate_line(draw, text, font, max_width) existiert.
    # Erwartet: _text_w(draw, text, font) existiert.
    if prefix:
        # prefix zählt NICHT in max_width für den Namen, sonst wird alles zu kurz
        name_max = max(10, max_width - _text_w(draw, prefix, font))
    else:
        name_max = max_width

    first = _truncate_line(draw, first, font, name_max) if first else ""
    last  = _truncate_line(draw, last,  font, name_max) if last else ""

    if not first and not last:
        return

    # Breiten berechnen
    w_prefix = _text_w(draw, prefix, font) if prefix else 0
    w_first  = _text_w(draw, first, font) if first else 0
    w_last   = _text_w(draw, last, font) if last else 0

    # Blockbreite = max( prefix+first , prefix+last )
    block_w = max(w_prefix + w_first, w_prefix + w_last)
    x0 = int(cx - block_w / 2)
    y0 = int(cy)

    def _fx(x: int, y: int, t: str):
        if not t:
            return
        draw_text_fx(
            img,
            (x, y),
            t,
            font,
            fill=fill,
            anchor="la",
            glow=False,
            shadow=True,
            shadow_offset=(0, 2),
            shadow_alpha=140,
            stroke=stroke,
            stroke_width=stroke_width,
            stroke_fill=stroke_fill,
        )

    # Zeile 1: Prefix + Vorname (Prefix separat, damit Indent sauber ist)
    if prefix:
        _fx(x0, y0, prefix)
    if first:
        _fx(x0 + w_prefix + (gap_px if prefix else 0), y0, first)

    # Zeile 2: Nachname eingerückt um Prefix (+ gap)
    if last:
        _fx(x0 + w_prefix + (gap_px if prefix else 0), y0 + line_gap_px, last)


def _slugify_team_name(name: str) -> str:
    s = (name or "").strip().lower()
    # german chars
    s = (
        s.replace("ä", "ae")
         .replace("ö", "oe")
         .replace("ü", "ue")
         .replace("ß", "ss")
    )
    # whitespace / underscores -> dash
    s = re.sub(r"[\s_]+", "-", s)
    # remove everything not alnum or dash
    s = re.sub(r"[^a-z0-9\-]+", "", s)
    # clean repeated dashes
    s = re.sub(r"-{2,}", "-", s).strip("-")
    return s


def _load_team_display_map(fonts_dir: Path) -> Dict[str, str]:
    """
    Optional file:
    tools/puls_renderer/assets/team_display_names.json  (or fonts_dir.parent/.. depending on your structure)
    In your matchday renderer you used: fonts_dir.parent / "team_display_names.json"
    We'll keep same rule.
    """
    p = fonts_dir.parent / "team_display_names.json"
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    return {}


def _team_name_to_logo_slug(team_name: str, display_map: Dict[str, str]) -> str:
    """
    display_map is slug -> display.
    We need reverse: display -> slug.
    """
    reverse = {v.strip().lower(): k for k, v in display_map.items()}
    key = (team_name or "").strip().lower()
    if key in reverse:
        return reverse[key]
    return _slugify_team_name(team_name)

def format_player(player) -> str:
    """
    Output:
      "#40 HENRIKE\nHAUKELIK"
    (Nummer + Fake-ID, 2 Zeilen)
    """
    def _split_two_lines(name: str) -> tuple[str, str]:
        name = (name or "").replace("_", " ").strip()
        if not name:
            return ("", "")
        parts = [p for p in name.split(" ") if p]
        if len(parts) == 1:
            return (parts[0].upper(), "")
        first = " ".join(parts[:-1]).upper()
        last = parts[-1].upper()
        return (first, last)

    # dict
    if isinstance(player, dict):
        num = player.get("number") or player.get("NUMBER") or ""
        pid = player.get("id") or player.get("ID") or ""
        if not pid:
            pid = player.get("name") or player.get("NAME") or ""

        if isinstance(num, int):
            num = str(num)
        num = str(num).strip()

        first, last = _split_two_lines(str(pid))
        top = f"#{num} {first}".strip() if num else first
        if last:
            return f"{top}\n{last}"
        return top

    # string
    if isinstance(player, str):
        first, last = _split_two_lines(player)
        return f"{first}\n{last}".strip() if last else first

    return ""



def player_label(player: dict | str | None) -> str:
    """
    Gibt genau das zurück, was ins Bild darf:
    '#31 Geraldo Kuhnnik'
    - nutzt NUMBER + ID (Fake-Name)
    - ID wird aus _ -> " " umgewandelt
    - keine Position, kein echtes NAME
    """
    if not player:
        return ""

    # Falls irgendwo doch mal ein String kommt
    if isinstance(player, str):
        raw = player
        number = ""
    elif isinstance(player, dict):
        number = player.get("NUMBER") or player.get("number") or ""
        raw = player.get("ID") or player.get("id") or ""
    else:
        return str(player)

    # ID schön machen
    name = str(raw).replace("_", " ").strip()
    # Title Case (macht aus 'GERALDO KUHNNIK' -> 'Geraldo Kuhnnik')
    name = " ".join(w.capitalize() for w in name.split())

    if number and name:
        return f"#{number} {name}"
    if name:
        return name
    if number:
        return f"#{number}"
    return ""



# ----------------------------
# Text FX
# ----------------------------
def draw_text_fx(
    img: Image.Image,
    pos: Tuple[int, int],
    text: str,
    font: ImageFont.FreeTypeFont,
    fill: Tuple[int, int, int, int],
    anchor: str = "mm",
    glow: bool = True,
    glow_radius: int = 6,
    glow_alpha: int = 120,
    shadow: bool = True,
    shadow_offset: Tuple[int, int] = (0, 2),
    shadow_alpha: int = 120,
    stroke: bool = True,
    stroke_width: int = 2,
    stroke_fill: Tuple[int, int, int, int] = (0, 0, 0, 140),
) -> None:
    """
    Subtiler Broadcast-FX: Shadow + Stroke + optional Glow.
    """
    x, y = pos

    base = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(base)

    # Shadow
    if shadow:
        sx, sy = shadow_offset
        d.text((x + sx, y + sy), text, font=font, fill=(0, 0, 0, shadow_alpha), anchor=anchor)

    # Stroke
    if stroke and stroke_width > 0:
        d.text(
            (x, y),
            text,
            font=font,
            fill=fill,
            anchor=anchor,
            stroke_width=stroke_width,
            stroke_fill=stroke_fill,
        )

    # Main
    d.text((x, y), text, font=font, fill=fill, anchor=anchor)

    # Glow
    if glow:
        glow_layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
        gd = ImageDraw.Draw(glow_layer)
        gd.text((x, y), text, font=font, fill=(fill[0], fill[1], fill[2], glow_alpha), anchor=anchor)
        glow_layer = glow_layer.filter(ImageFilter.GaussianBlur(radius=glow_radius))
        img.alpha_composite(glow_layer)

    img.alpha_composite(base)


def draw_text_ice_noise_bbox(
    img: Image.Image,
    pos: Tuple[int, int],
    text: str,
    font: ImageFont.FreeTypeFont,
    fill: Tuple[int, int, int, int],
    anchor: str = "mm",
    intensity: float = 0.15,      # 0.25 subtil, 0.35 sichtbar, 0.5 stark
    speck_size: int = 2,          # 1..4 (Pixelradius)
    seed: Optional[int] = 1,
    threshold: int = 80,
) -> None:
    """
    Sichtbarer 'Eisrauheit'-Look:
    - Noise wird NUR im Text-Bounding-Box erzeugt.
    - Ergebnis ist verlässlich sichtbar, ohne Neon/Glow.
    """
    if seed is not None:
        random.seed(seed)

    # bbox für Text berechnen
    tmp = Image.new("RGBA", img.size, (0, 0, 0, 0))
    td = ImageDraw.Draw(tmp)
    l, t, r, b = td.textbbox(pos, text, font=font, anchor=anchor)

    l = max(0, l)
    t = max(0, t)
    r = min(img.size[0], r)
    b = min(img.size[1], b)
    bw = max(1, r - l)
    bh = max(1, b - t)

    # Textmaske in Box
    text_mask = Image.new("L", (bw, bh), 0)
    md = ImageDraw.Draw(text_mask)
    md.text((pos[0] - l, pos[1] - t), text, font=font, fill=255, anchor=anchor)

    # Noise in Box
    noise = Image.new("L", (bw, bh), 0)
    nd = ImageDraw.Draw(noise)

    n = int(bw * bh * intensity / 120)
    n = max(120, n)  # Minimum, damit es sicher sichtbar ist

    for _ in range(n):
        x = random.randint(0, bw - 1)
        y = random.randint(0, bh - 1)
        nd.ellipse((x - speck_size, y - speck_size, x + speck_size, y + speck_size), fill=255)

    scratched = ImageChops.subtract(text_mask, noise)
    scratched = scratched.point(lambda p: 255 if p > threshold else 0)

    layer = Image.new("RGBA", (bw, bh), fill)
    img.paste(layer, (l, t), mask=scratched)


# ----------------------------
# Logos
# ----------------------------
def _load_logo(
    logos_dir: Path,
    team_id: str,
    size: int,
    accent: Tuple[int, int, int, int],
) -> Image.Image:
    p = logos_dir / f"{team_id}.png"
    if p.exists():
        im = Image.open(p).convert("RGBA")
        return im.resize((size, size), Image.LANCZOS)

    # fallback placeholder
    im = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.ellipse((3, 3, size - 3, size - 3), outline=accent, width=3)
    return im


# ----------------------------
# Renderer
# ----------------------------
def render_matchday_overview(
    template_path: Path,
    data: Dict[str, Any],
    logos_dir: Path,
    fonts_dir: Path,
    out_path: Path,
    layout: Optional[MatchdayLayoutV1] = None,
    enable_draw_vs: bool = False,
    delta_date: Optional[str] = None,
    enable_fx_on_teams: bool = False,
    header_fx: str = "ice_noise",  # "ice_noise" | "fx"
) -> Path:
    layout = layout or MatchdayLayoutV1()

    img = Image.open(template_path).convert("RGBA")
    draw = ImageDraw.Draw(img)

    # Fonts
    font_bold_path = fonts_dir / "Inter-Bold.ttf"
    font_med_path = fonts_dir / "Inter-Medium.ttf"

    # Base sizes
    team_size = 23
    spieltag_size = 72
    date_size = 20
    vs_size = 34

    # Header
    spieltag = data.get("spieltag")
    if spieltag is None:
        raise ValueError("JSON missing required field: spieltag")

    header_text = f"SPIELTAG {spieltag}"
    font_spieltag = _fit_text(draw, header_text, font_bold_path, max_width=900, start_size=spieltag_size, min_size=34)

    if header_fx == "ice_noise":
        draw_text_ice_noise_bbox(
            img,
            (layout.header_center_x, layout.header_spieltag_y),
            header_text,
            font_spieltag,
            fill=layout.color_text,
            anchor="mm",
            intensity=0.15,
            speck_size=1,
            seed=2,
            threshold=80,
        )
    else:
        draw_text_fx(
            img,
            (layout.header_center_x, layout.header_spieltag_y),
            header_text,
            font_spieltag,
            fill=layout.color_text,
            anchor="mm",
            glow=True,
            glow_radius=10,
            glow_alpha=130,
            shadow=True,
            shadow_offset=(0, 3),
            shadow_alpha=140,
            stroke=True,
            stroke_width=2,
            stroke_fill=(0, 0, 0, 160),
        )

    # Footer date: Δ + user input
    if not delta_date:
        raise ValueError("Δ-Datum fehlt. Bitte im Renderer-UI eintragen (z.B. 2125-10-18).")

    delta_date = str(delta_date).strip()
    if delta_date.lower().startswith("delta"):
        delta_date = delta_date[5:].strip()
    if delta_date.startswith("Δ"):
        delta_date = delta_date[1:].strip()

    date_str = f"Δ{delta_date}"
    font_date = _fit_text(draw, date_str, font_med_path, max_width=700, start_size=date_size, min_size=12)

    # Datum: klein, clean
    draw.text(
        (layout.footer_date_center_x, layout.footer_date_y),
        date_str,
        font=font_date,
        fill=layout.color_accent,
        anchor="mm",
    )


    # Define watermark font before use
    wm_font = ImageFont.truetype(str(fonts_dir / "Inter-Medium.ttf"), size=20)
    _draw_watermark(
        img,
        draw,
        text="powered by HIGHspeeΔ PUX! Engine",
        font=wm_font,
        margin=22,
        opacity=90,
    )



    # Matches
    nord: List[Dict[str, str]] = data.get("nord", [])
    sued: List[Dict[str, str]] = data.get("sued", [])

    if len(nord) != 5 or len(sued) != 5:
        raise ValueError(f"Expected 5 nord + 5 sued matches. Got nord={len(nord)} sued={len(sued)}")

    # Optional display-name mapping
    display_map_path = fonts_dir.parent / "team_display_names.json"
    display_map: Dict[str, str] = {}
    if display_map_path.exists():
        display_map = json.loads(display_map_path.read_text(encoding="utf-8"))

    def draw_match_row(y: int, home_id: str, away_id: str) -> None:
        logo_home = _load_logo(logos_dir, home_id, layout.logo_size, layout.color_accent)
        logo_away = _load_logo(logos_dir, away_id, layout.logo_size, layout.color_accent)

        home_label = display_map.get(home_id, home_id.replace("-", " "))
        away_label = display_map.get(away_id, away_id.replace("-", " "))
        home_txt = home_label.upper()
        away_txt = away_label.upper()

        team_font = _load_font(font_bold_path, team_size)


        # logos
        img.alpha_composite(logo_home, (layout.x_logo_home, int(y - layout.logo_size / 2)))
        img.alpha_composite(logo_away, (layout.x_logo_away, int(y - layout.logo_size / 2)))

        # team text
        if enable_fx_on_teams:
            # Clean TV look: shadow + thin stroke, NO glow
            draw_text_fx(
                img,
                (layout.x_text_home, y),
                home_txt,
                team_font,
                fill=layout.color_text,
                anchor="lm",
                glow=False,
                shadow=True,
                shadow_offset=(0, 2),
                shadow_alpha=140,
                stroke=True,
                stroke_width=2,
                stroke_fill=(0, 0, 0, 190),
            )
            draw_text_fx(
                img,
                (layout.x_text_away, y),
                away_txt,
                team_font,
                fill=layout.color_text,
                anchor="rm",
                glow=False,
                shadow=True,
                shadow_offset=(0, 2),
                shadow_alpha=140,
                stroke=True,
                stroke_width=2,
                stroke_fill=(0, 0, 0, 190),
            )
        else:
            draw.text((layout.x_text_home, y), home_txt, font=team_font, fill=layout.color_text, anchor="lm")
            draw.text((layout.x_text_away, y), away_txt, font=team_font, fill=layout.color_text, anchor="rm")

        # VS optional
        if enable_draw_vs:
            font_vs = _fit_text(draw, "VS", font_med_path, max_width=120, start_size=vs_size, min_size=22)
            draw_text_fx(
                img,
                (layout.center_x, y),
                "VS",
                font_vs,
                fill=layout.color_accent,
                anchor="mm",
                glow=True,
                glow_radius=8,
                glow_alpha=140,
                shadow=True,
                shadow_offset=(0, 2),
                shadow_alpha=120,
                stroke=False,
            )

    for i, m in enumerate(nord):
        draw_match_row(layout.y_nord[i], m["home"], m["away"])

    for i, m in enumerate(sued):
        draw_match_row(layout.y_sued[i], m["home"], m["away"])


    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path)
    return out_path


def render_from_json_file(
    json_path: Path,
    template_name: str = "matchday_overview_v1.png",
    out_name: Optional[str] = None,
    enable_draw_vs: bool = False,
    delta_date: Optional[str] = None,
    enable_fx_on_teams: bool = False,
    header_fx: str = "ice_noise",
) -> Path:
    base_dir = Path(__file__).resolve().parent
    paths = RenderPaths(base_dir=base_dir)
    layout = MatchdayLayoutV1()

    raw = _safe_load_json(json_path)

    # generator-json: has "results"
    if "results" in raw and "nord" not in raw and "sued" not in raw:
        data = convert_generator_json_to_matchday(raw)
    else:
        data = raw

    template_path = paths.templates_dir / template_name
    if not template_path.exists():
        raise FileNotFoundError(f"Template not found: {template_path}")

    spieltag = data.get("spieltag", "XX")
    if out_name is None:
        out_name = f"spieltag_{int(spieltag):02d}.png" if str(spieltag).isdigit() else f"spieltag_{spieltag}.png"

    out_path = paths.output_dir / out_name

    return render_matchday_overview(
        template_path=template_path,
        data=data,
        logos_dir=paths.logos_dir,
        fonts_dir=paths.fonts_dir,
        out_path=out_path,
        layout=layout,
        enable_draw_vs=enable_draw_vs,
        delta_date=delta_date,
        enable_fx_on_teams=enable_fx_on_teams,
        header_fx=header_fx,
    )


