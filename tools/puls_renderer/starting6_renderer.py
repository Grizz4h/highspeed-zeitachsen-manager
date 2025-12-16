from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional, Tuple, List

from PIL import Image, ImageDraw, ImageFont

from .layout_config import Starting6LayoutV1
from .adapter import slugify_team
from .lineup_adapter import extract_starting6_for_matchup

# Wir importieren die stabilen Shared-Helpers aus renderer.py,
# damit wir NICHT alles auf einmal umbauen müssen.
from .renderer import (
    RenderPaths,
    _safe_load_json,
    _fit_text,
    draw_text_fx,
    draw_text_ice_noise_bbox,
    _load_logo,
    _draw_watermark,
    _draw_player_block_centered,
)


def _player_number(p: Any) -> str:
    if isinstance(p, dict):
        n = p.get("number") or p.get("NUMBER") or ""
        return str(n).strip()
    return ""


def _player_display_name(p: Any) -> str:
    """
    WICHTIG: Manche Lineups haben ID, andere nur NAME.
    Wir nehmen: ID -> id -> NAME -> name
    und machen _ zu Leerzeichen.
    """
    if isinstance(p, dict):
        raw = (
            p.get("ID")
            or p.get("id")
            or p.get("NAME")
            or p.get("name")
            or ""
        )
    else:
        raw = str(p or "")

    return str(raw).replace("_", " ").strip()


def _draw_divider(img: Image.Image, y: int, color: Tuple[int, int, int, int]) -> None:
    d = ImageDraw.Draw(img)
    d.line((110, y, 970, y), fill=color, width=2)
    d.line((110, y - 10, 110, y + 10), fill=color, width=2)
    d.line((970, y - 10, 970, y + 10), fill=color, width=2)


def render_starting6_from_files(
    matchday_json_path: Path,
    lineups_json_path: Path,
    home_team: str,
    away_team: str,
    template_name: str = "starting6v1.png",
    out_name: Optional[str] = None,
    season_label: str = "SAISON 1",
) -> Path:
    """
    Starting6 Renderer (Top Game – Starting 6)
    - nutzt matchday_json für spieltag label
    - nutzt lineups_json für Spieler
    """

    base_dir = Path(__file__).resolve().parent
    paths = RenderPaths(base_dir=base_dir)
    layout = Starting6LayoutV1()

    matchday = _safe_load_json(Path(matchday_json_path))
    lineups = _safe_load_json(Path(lineups_json_path))

    starting6 = extract_starting6_for_matchup(lineups, home_team, away_team)

    spieltag = matchday.get("spieltag")
    if spieltag is None:
        # falls generator-json oder irgendwas anderes
        spieltag = matchday.get("SPIELTAG") or matchday.get("matchday") or "X"

    template_path = paths.templates_dir / template_name
    if not template_path.exists():
        raise FileNotFoundError(f"Template not found: {template_path}")

    if out_name is None:
        out_name = f"starting6_{home_team.replace(' ', '-')}_vs_{away_team.replace(' ', '-')}.png"

    out_path = paths.output_dir / out_name
    out_path.parent.mkdir(parents=True, exist_ok=True)

    img = Image.open(template_path).convert("RGBA")
    draw = ImageDraw.Draw(img)

    font_bold = paths.fonts_dir / "Inter-Bold.ttf"
    font_med = paths.fonts_dir / "Inter-Medium.ttf"

    # Header
    header = ""
    sub = f"{season_label} • SPIELTAG {spieltag}"

    font_h = _fit_text(draw, header, font_bold, max_width=980, start_size=layout.title_size, min_size=34)
    draw_text_ice_noise_bbox(
        img,
        (540, layout.header_title_y),
        header,
        font_h,
        fill=layout.color_text,
        anchor="mm",
        intensity=0.12,
        speck_size=1,
        seed=2,
        threshold=90,
    )

    font_sub = _fit_text(draw, sub.upper(), font_med, max_width=980, start_size=layout.sub_size, min_size=14)
    draw.text((540, layout.header_sub_y), sub.upper(), font=font_sub, fill=layout.color_accent, anchor="mm")

    # Divider (oben)
    _draw_divider(img, layout.divider_y, layout.color_divider)

    # Logos
    home_id = slugify_team(home_team)
    away_id = slugify_team(away_team)

    logo_home = _load_logo(paths.logos_dir, home_id, layout.logo_size, layout.color_accent)
    logo_away = _load_logo(paths.logos_dir, away_id, layout.logo_size, layout.color_accent)

    img.alpha_composite(logo_home, (540 - layout.logo_size // 2, layout.home_logo_y - layout.logo_size // 2))
    img.alpha_composite(logo_away, (540 - layout.logo_size // 2, layout.away_logo_y - layout.logo_size // 2))

    font_obj = ImageFont.truetype(str(font_bold), size=layout.name_size)

    # -------- HOME BLOCK --------
    home = starting6["home"]

    # Goalie
    g = home.get("goalie", {})
    _draw_player_block_centered(
        img, draw,
        center=(540, layout.home_goalie_y),
        number=_player_number(g),
        fake_name=_player_display_name(g),
        font=font_obj,
        fill=layout.color_text,
        max_width=700,
    )

    # Defense
    d = home.get("defense", [])
    pL = d[0] if len(d) > 0 else {}
    pR = d[1] if len(d) > 1 else {}

    _draw_player_block_centered(
        img, draw,
        center=(380, layout.home_def_y),
        number=_player_number(pL),
        fake_name=_player_display_name(pL),
        font=font_obj,
        fill=layout.color_text,
    )
    _draw_player_block_centered(
        img, draw,
        center=(700, layout.home_def_y),
        number=_player_number(pR),
        fake_name=_player_display_name(pR),
        font=font_obj,
        fill=layout.color_text,
    )

    # Forwards (leicht nach unten gewölbt)
    f = home.get("forwards", [])
    pLW = f[0] if len(f) > 0 else {}
    pC  = f[1] if len(f) > 1 else {}
    pRW = f[2] if len(f) > 2 else {}

    _draw_player_block_centered(
        img, draw,
        center=(260, layout.home_fwd_y - 6),
        number=_player_number(pLW),
        fake_name=_player_display_name(pLW),
        font=font_obj,
        fill=layout.color_text,
    )
    _draw_player_block_centered(
        img, draw,
        center=(540, layout.home_fwd_y + 22),
        number=_player_number(pC),
        fake_name=_player_display_name(pC),
        font=font_obj,
        fill=layout.color_text,
    )
    _draw_player_block_centered(
        img, draw,
        center=(820, layout.home_fwd_y - 6),
        number=_player_number(pRW),
        fake_name=_player_display_name(pRW),
        font=font_obj,
        fill=layout.color_text,
    )

    # Divider (Mitte)
    _draw_divider(img, layout.divider_y, layout.color_divider)

    # -------- AWAY BLOCK --------
    away = starting6["away"]

    # Forwards (gegenläufig nach oben)
    f2 = away.get("forwards", [])
    pLW = f2[0] if len(f2) > 0 else {}
    pC  = f2[1] if len(f2) > 1 else {}
    pRW = f2[2] if len(f2) > 2 else {}

    _draw_player_block_centered(
        img, draw,
        center=(260, layout.away_fwd_y + 6),
        number=_player_number(pLW),
        fake_name=_player_display_name(pLW),
        font=font_obj,
        fill=layout.color_text,
    )
    _draw_player_block_centered(
        img, draw,
        center=(540, layout.away_fwd_y - 22),
        number=_player_number(pC),
        fake_name=_player_display_name(pC),
        font=font_obj,
        fill=layout.color_text,
    )
    _draw_player_block_centered(
        img, draw,
        center=(820, layout.away_fwd_y + 6),
        number=_player_number(pRW),
        fake_name=_player_display_name(pRW),
        font=font_obj,
        fill=layout.color_text,
    )

    # Defense
    d2 = away.get("defense", [])
    pL = d2[0] if len(d2) > 0 else {}
    pR = d2[1] if len(d2) > 1 else {}

    _draw_player_block_centered(
        img, draw,
        center=(380, layout.away_def_y),
        number=_player_number(pL),
        fake_name=_player_display_name(pL),
        font=font_obj,
        fill=layout.color_text,
    )
    _draw_player_block_centered(
        img, draw,
        center=(700, layout.away_def_y),
        number=_player_number(pR),
        fake_name=_player_display_name(pR),
        font=font_obj,
        fill=layout.color_text,
    )

    # Goalie
    g = away.get("goalie", {})
    _draw_player_block_centered(
        img, draw,
        center=(540, layout.away_goalie_y),
        number=_player_number(g),
        fake_name=_player_display_name(g),
        font=font_obj,
        fill=layout.color_text,
        max_width=700,
    )

    # Watermark
    wm_font = ImageFont.truetype(str(paths.fonts_dir / "Inter-Medium.ttf"), size=20)
    _draw_watermark(
        img,
        draw,
        text="powered by HIGHspeeΔ PUX! Engine",
        font=wm_font,
        margin=22,
        opacity=90,
    )

    img.save(out_path)
    return out_path
