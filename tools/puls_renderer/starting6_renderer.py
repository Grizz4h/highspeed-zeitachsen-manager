from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Tuple, List

from PIL import Image, ImageDraw, ImageFont, ImageFilter

from .layout_config import MatchdayLayoutV1  # wir reuse'n Farben etc.
from .renderer import RenderPaths, _safe_load_json, _load_font, _fit_text, _load_logo
from .lineup_adapter import extract_starting6_for_matchup


# ----------------------------
# Layout (Option B: Slots)
# ----------------------------
@dataclass
class Starting6LayoutV1:
    # Canvas / Key anchors
    center_x: int = 540

    # Header
    y_title: int = 120
    y_subtitle: int = 175

    # Team blocks
    x_home_block: int = 160
    x_away_block: int = 920
    y_team_top: int = 250
    logo_size: int = 120
    team_name_max_width: int = 420

    # Lineup area
    y_section_label: int = 430

    # Forwards arc (3 Spieler)
    y_forwards_base: int = 540
    forwards_arc_height: int = 50   # wie stark der Bogen ist
    forwards_spread: int = 210      # Abstand links/rechts vom Center

    # Defense (2 Spieler)
    y_defense: int = 710
    defense_spread: int = 180

    # Goalie (1)
    y_goalie: int = 860

    # Small labels
    label_gap: int = 28


def _curve_y(x: float, center_x: float, base_y: float, height: float, spread: float) -> float:
    """
    Simple parabola (arc): highest in the center, lower on edges.
    x in [center_x-spread .. center_x+spread]
    """
    t = (x - center_x) / spread  # -1 .. +1
    return base_y - (1 - (t * t)) * height


def _positions_forwards_arc(layout: Starting6LayoutV1) -> List[Tuple[int, int]]:
    """
    Returns positions for LW, C, RW.
    """
    cx = layout.center_x
    base = layout.y_forwards_base
    h = layout.forwards_arc_height
    s = layout.forwards_spread

    xs = [cx - s, cx, cx + s]
    pts: List[Tuple[int, int]] = []
    for x in xs:
        y = _curve_y(x, cx, base, h, s)
        pts.append((int(x), int(y)))
    return pts


def _positions_defense(layout: Starting6LayoutV1) -> List[Tuple[int, int]]:
    cx = layout.center_x
    s = layout.defense_spread
    return [(cx - s, layout.y_defense), (cx + s, layout.y_defense)]


def _draw_glow_text(
    img: Image.Image,
    pos: Tuple[int, int],
    text: str,
    font: ImageFont.FreeTypeFont,
    fill: Tuple[int, int, int, int],
    anchor: str = "mm",
    glow_radius: int = 10,
    glow_alpha: int = 90,
) -> None:
    """
    Stabiler, unaufdringlicher Glow (kein FX-Loch-Kram).
    """
    glow = Image.new("RGBA", img.size, (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gd.text(pos, text, font=font, fill=(fill[0], fill[1], fill[2], glow_alpha), anchor=anchor)
    glow = glow.filter(ImageFilter.GaussianBlur(radius=glow_radius))
    img.alpha_composite(glow)

    d = ImageDraw.Draw(img)
    d.text(pos, text, font=font, fill=fill, anchor=anchor)


def render_starting6(
    template_path: Path,
    matchday_data: Dict[str, Any],
    lineups_data: Dict[str, Any],
    home_team: str,
    away_team: str,
    out_path: Path,
    paths: RenderPaths,
    layout: Optional[Starting6LayoutV1] = None,
    delta_date: Optional[str] = None,
    season_label: Optional[str] = None,
) -> Path:
    layout = layout or Starting6LayoutV1()
    base_layout = MatchdayLayoutV1()  # Farben reuse'n

    img = Image.open(template_path).convert("RGBA")
    draw = ImageDraw.Draw(img)

    # Fonts (reuse from assets/fonts)
    font_bold_path = paths.fonts_dir / "Inter-Bold.ttf"
    font_med_path = paths.fonts_dir / "Inter-Medium.ttf"

    font_title = _fit_text(draw, "TOP GAME", font_bold_path, max_width=900, start_size=64, min_size=36)
    font_sub = _fit_text(draw, "Δ0000-00-00", font_med_path, max_width=900, start_size=24, min_size=14)

    font_team = _fit_text(draw, home_team.upper(), font_bold_path, max_width=layout.team_name_max_width, start_size=34, min_size=18)
    font_label = _load_font(font_med_path, 18)
    font_player = _fit_text(draw, "PLAYER NAME", font_med_path, max_width=360, start_size=28, min_size=18)

    # Header text
    title_text = "TOP GAME"
    if season_label:
        subtitle = season_label.strip()
    else:
        # fallback: read from matchday json if present
        saison = matchday_data.get("season") or matchday_data.get("saison") or ""
        spieltag = matchday_data.get("spieltag") or ""
        bits = []
        if saison:
            bits.append(f"SAISON {saison}")
        if spieltag:
            bits.append(f"SPIELTAG {spieltag}")
        subtitle = " • ".join(bits) if bits else ""

    # Date
    if not delta_date:
        delta_date = ""
    dd = str(delta_date).strip()
    if dd.startswith("Δ"):
        dd = dd[1:].strip()
    date_str = f"Δ{dd}" if dd else ""

    # Draw header
    _draw_glow_text(img, (layout.center_x, layout.y_title), title_text, font_title, base_layout.color_text, anchor="mm", glow_radius=12, glow_alpha=80)

    if subtitle:
        draw.text((layout.center_x, layout.y_subtitle), subtitle, font=font_sub, fill=base_layout.color_accent, anchor="mm")
    if date_str:
        draw.text((layout.center_x, layout.y_subtitle + 30), date_str, font=font_sub, fill=base_layout.color_accent, anchor="mm")

    # Logos
    logo_home = _load_logo(paths.logos_dir, home_team, layout.logo_size, base_layout.color_accent)
    logo_away = _load_logo(paths.logos_dir, away_team, layout.logo_size, base_layout.color_accent)

    img.alpha_composite(logo_home, (layout.x_home_block - layout.logo_size // 2, layout.y_team_top - layout.logo_size // 2))
    img.alpha_composite(logo_away, (layout.x_away_block - layout.logo_size // 2, layout.y_team_top - layout.logo_size // 2))

    # Team names
    draw.text((layout.x_home_block, layout.y_team_top + 95), home_team.upper(), font=font_team, fill=base_layout.color_text, anchor="mm")
    draw.text((layout.x_away_block, layout.y_team_top + 95), away_team.upper(), font=font_team, fill=base_layout.color_text, anchor="mm")

    # Extract starting6
    s6 = extract_starting6_for_matchup(lineups_data, home_team, away_team)

    # Section label
    draw.text((layout.center_x, layout.y_section_label), "STARTING 6", font=_load_font(font_bold_path, 26), fill=base_layout.color_accent, anchor="mm")

    # Helper to draw one team lineup on left/right side
    def draw_team_lineup(team_key: str, side: str) -> None:
        """
        side: "home" or "away"
        """
        data = s6[team_key]
        forwards = data.get("forwards", [])
        defense = data.get("defense", [])
        goalie = data.get("goalie", "")

        # push to left/right half
        x_offset = -250 if side == "home" else 250

        # FORWARDS (arc)
        f_pts = _positions_forwards_arc(layout)
        f_pts = [(x + x_offset, y) for (x, y) in f_pts]
        labels = ["LW", "C", "RW"]

        for i in range(3):
            name = forwards[i] if i < len(forwards) else ""
            x, y = f_pts[i]
            # role label
            draw.text((x, y - layout.label_gap), labels[i], font=font_label, fill=base_layout.color_accent, anchor="mm")
            # player name
            draw.text((x, y), name, font=font_player, fill=base_layout.color_text, anchor="mm")

        # DEFENSE
        d_pts = _positions_defense(layout)
        d_pts = [(x + x_offset, y) for (x, y) in d_pts]
        dlabels = ["LD", "RD"]

        for i in range(2):
            name = defense[i] if i < len(defense) else ""
            x, y = d_pts[i]
            draw.text((x, y - layout.label_gap), dlabels[i], font=font_label, fill=base_layout.color_accent, anchor="mm")
            draw.text((x, y), name, font=font_player, fill=base_layout.color_text, anchor="mm")

        # GOALIE
        gx = layout.center_x + x_offset
        gy = layout.y_goalie
        draw.text((gx, gy - layout.label_gap), "G", font=font_label, fill=base_layout.color_accent, anchor="mm")
        draw.text((gx, gy), goalie, font=font_player, fill=base_layout.color_text, anchor="mm")

    draw_team_lineup("home", "home")
    draw_team_lineup("away", "away")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path)
    return out_path


def render_starting6_from_files(
    matchday_json_path: Path,
    lineups_json_path: Path,
    home_team: str,
    away_team: str,
    template_name: str = "starting6v1.png",
    out_name: Optional[str] = None,
    delta_date: Optional[str] = None,
    season_label: Optional[str] = None,
) -> Path:
    base_dir = Path(__file__).resolve().parent
    paths = RenderPaths(base_dir=base_dir)

    matchday_data = _safe_load_json(matchday_json_path)
    lineups_data = _safe_load_json(lineups_json_path)

    template_path = paths.templates_dir / template_name
    if not template_path.exists():
        raise FileNotFoundError(f"Template not found: {template_path}")

    if out_name is None:
        out_name = f"starting6_{home_team}_vs_{away_team}.png".replace(" ", "_")

    out_path = paths.output_dir / out_name

    return render_starting6(
        template_path=template_path,
        matchday_data=matchday_data,
        lineups_data=lineups_data,
        home_team=home_team,
        away_team=away_team,
        out_path=out_path,
        paths=paths,
        delta_date=delta_date,
        season_label=season_label,
    )
