from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from PIL import Image, ImageDraw, ImageFont

# Reuse aus renderer.py
from .renderer import (
    RenderPaths,
    _safe_load_json,
    _fit_text,
    _load_font,
    _load_logo,
    _draw_watermark,
    draw_text_fx,
)

# ----------------------------
# Layout
# ----------------------------
@dataclass
class LeagueTableLayoutV1:
    # canvas
    width: int = 1080
    height: int = 1350

    # header positions
    header_brand_y: int = 92
    header_title_y: int = 165
    header_sub_y: int = 240
    header_date_y: int = 270

    # blocks (NORD oben, SÜD unten)
    nord_title_y: int = 340
    nord_table_top: int = 388

    # NOTE: Süd runter, damit nichts überlappt
    sued_title_y: int = 760
    sued_table_top: int = 808

    # row sizes
    header_row_h: int = 52
    row_h: int = 44

    # colors (RGBA)
    color_text: Tuple[int, int, int, int] = (220, 240, 255, 255)
    color_accent: Tuple[int, int, int, int] = (130, 220, 255, 255)
    color_grid: Tuple[int, int, int, int] = (130, 220, 255, 80)


def _normalize_delta_date(delta_date: Optional[str]) -> str:
    if not delta_date:
        return ""
    s = str(delta_date).strip()
    s = re.sub(r"^(delta|Δ)\s*", "", s, flags=re.IGNORECASE).strip()
    if not s:
        return ""
    if not s.startswith("Δ"):
        s = "Δ" + s
    return s


def _try_extract_season_spieltag(meta: Dict[str, Any]) -> Tuple[Optional[int], Optional[int]]:
    season = meta.get("season", None)
    if season is None:
        season = meta.get("saison", None)
    if season is None:
        season = meta.get("Season", None)

    spieltag = meta.get("spieltag", None)
    if spieltag is None:
        spieltag = meta.get("matchday", None)

    def _to_int(x) -> Optional[int]:
        try:
            return int(x)
        except Exception:
            return None

    return _to_int(season), _to_int(spieltag)


def _slugify_fallback(team_name: str) -> str:
    s = (team_name or "").strip().lower()
    s = (
        s.replace("ä", "ae")
         .replace("ö", "oe")
         .replace("ü", "ue")
         .replace("ß", "ss")
    )
    s = re.sub(r"[\s_]+", "-", s)
    s = re.sub(r"[^a-z0-9\-]+", "", s).strip("-")
    s = re.sub(r"-{2,}", "-", s)
    return s


def _resolve_team_slug(team_name: str, display_map: Dict[str, str]) -> str:
    # display_map: slug -> DisplayName
    reverse = {v.strip().lower(): k for k, v in display_map.items()}
    key = (team_name or "").strip().lower()
    return reverse.get(key) or _slugify_fallback(team_name)


def _draw_table_block(
    img: Image.Image,
    draw: ImageDraw.ImageDraw,
    layout: LeagueTableLayoutV1,
    title: str,
    title_y: int,
    table_top: int,
    rows: List[Dict[str, Any]],
    logos_dir: Path,
    fonts_dir: Path,
    display_map: Dict[str, str],
) -> None:
    font_bold_path = fonts_dir / "Inter-Bold.ttf"
    font_med_path = fonts_dir / "Inter-Medium.ttf"

    # Titel (du willst den ggf. später selbst reinmalen – kannst du auch einfach auskommentieren)
    font_block_title = _load_font(font_bold_path, 34)
    draw_text_fx(
        img,
        (layout.width // 2, title_y),
        title.upper(),
        font_block_title,
        fill=layout.color_text,
        anchor="mm",
        glow=False,
        shadow=True,
        shadow_offset=(0, 2),
        shadow_alpha=140,
        stroke=True,
        stroke_width=2,
        stroke_fill=(0, 0, 0, 170),
    )

    # ----------------------------
    # Column layout (zentriert!)
    # ----------------------------
    # Ziel: Team-Spalte schmaler, rechts alles sichtbar.
    col_rank = 56
    col_logo = 52
    col_team = 380   # <= hier bewusst schmaler als vorher, aber lang genug für Schwenningen Sturmflügel
    col_pts  = 80
    col_gf   = 70
    col_ga   = 70
    col_gd   = 70

    table_width = col_rank + col_logo + col_team + col_pts + col_gf + col_ga + col_gd
    x0 = (layout.width - table_width) // 2  # DAS ist die echte Zentrierung

    x_rank = x0
    x_logo = x_rank + col_rank
    x_team = x_logo + col_logo
    x_pts  = x_team + col_team
    x_gf   = x_pts + col_pts
    x_ga   = x_gf + col_gf
    x_gd   = x_ga + col_ga

    # header labels (ohne Backplate!)
    font_hdr = _load_font(font_bold_path, 22)
    y_hdr = table_top + layout.header_row_h // 2

    draw.text((x_rank + 10, y_hdr), "#", font=font_hdr, fill=layout.color_text, anchor="lm")
    draw.text((x_team + 10, y_hdr), "TEAM", font=font_hdr, fill=layout.color_text, anchor="lm")
    draw.text((x_pts + col_pts // 2, y_hdr), "PTS", font=font_hdr, fill=layout.color_text, anchor="mm")
    draw.text((x_gf + col_gf // 2, y_hdr), "GF", font=font_hdr, fill=layout.color_text, anchor="mm")
    draw.text((x_ga + col_ga // 2, y_hdr), "GA", font=font_hdr, fill=layout.color_text, anchor="mm")
    draw.text((x_gd + col_gd // 2, y_hdr), "GD", font=font_hdr, fill=layout.color_text, anchor="mm")

    # verticale separator (optional, subtil)
    panel_h = layout.header_row_h + len(rows) * layout.row_h
    for x in [x_pts, x_gf, x_ga, x_gd]:
        draw.line((x, table_top + 10, x, table_top + panel_h - 10), fill=layout.color_grid, width=2)

    # rows (keine Hintergründe!)
    font_team = _load_font(font_bold_path, 24)
    font_num  = _load_font(font_med_path, 24)

    for i, r in enumerate(rows):
        y = table_top + layout.header_row_h + i * layout.row_h
        y_mid = y + layout.row_h // 2

        rank = i + 1
        team_name = str(r.get("Team", ""))
        pts = r.get("Points", 0)
        gf = r.get("GF", 0)
        ga = r.get("GA", 0)
        gd = r.get("GD", 0)

        team_slug = _resolve_team_slug(team_name, display_map)

        # logo
        logo = _load_logo(logos_dir, team_slug, size=34, accent=layout.color_accent)
        img.alpha_composite(logo, (x_logo + 6, y + (layout.row_h - 34) // 2))

        # rank
        draw.text((x_rank + 12, y_mid), f"{rank}.", font=font_num, fill=layout.color_text, anchor="lm")

        # team text
        draw_text_fx(
            img,
            (x_team + 10, y_mid),
            team_name,
            font_team,
            fill=layout.color_text,
            anchor="lm",
            glow=False,
            shadow=True,
            shadow_offset=(0, 2),
            shadow_alpha=120,
            stroke=True,
            stroke_width=2,
            stroke_fill=(0, 0, 0, 160),
        )

        def num_center(val: Any, xx: int, ww: int):
            draw.text((xx + ww // 2, y_mid), str(val), font=font_num, fill=layout.color_text, anchor="mm")

        num_center(pts, x_pts, col_pts)
        num_center(gf,  x_gf,  col_gf)
        num_center(ga,  x_ga,  col_ga)

        # GD with sign
        try:
            gd_i = int(gd)
            gd_str = f"{gd_i:+d}"
        except Exception:
            gd_str = str(gd)
        num_center(gd_str, x_gd, col_gd)


def render_league_table_from_matchday_json(
    matchday_json_path: Path,
    template_name: str = "league_table_v1.png",  # <- dein Asset
    out_name: Optional[str] = None,
    delta_date: Optional[str] = None,
) -> Path:
    """
    Rendert NORD + SÜD in EINEM Bild (1080x1350).
    Erwartet in matchday json:
      - tabelle_nord: [{Team, Points, GF, GA, GD}, ...] (10 Teams)
      - tabelle_sued: [{...}] (10 Teams)
      - optional: season/saison + spieltag
    """
    base_dir = Path(__file__).resolve().parent
    paths = RenderPaths(base_dir=base_dir)
    layout = LeagueTableLayoutV1()

    data = _safe_load_json(Path(matchday_json_path))

    # season / spieltag
    season, spieltag = _try_extract_season_spieltag(data)
    season_label = f"SAISON {season}" if season is not None else "SAISON ?"
    spieltag_label = f"SPIELTAG {spieltag}" if spieltag is not None else "SPIELTAG ?"
    sub = f"{season_label} • {spieltag_label}"

    # delta date: entweder param oder aus JSON (wenn vorhanden)
    if not delta_date:
        for k in ["delta_date", "deltaDate", "delta", "datum", "date"]:
            if k in data and data.get(k):
                delta_date = str(data.get(k))
                break

    date_str = _normalize_delta_date(delta_date)
    if not date_str:
        raise ValueError("Δ-Datum fehlt. Bitte im UI eintragen (z.B. 2125-10-18).")

    nord_rows = data.get("tabelle_nord", []) or []
    sued_rows = data.get("tabelle_sued", []) or []

    if len(nord_rows) != 10 or len(sued_rows) != 10:
        raise ValueError(f"Erwarte 10 Teams pro Division. Got nord={len(nord_rows)} sued={len(sued_rows)}")

    template_path = paths.templates_dir / template_name
    if not template_path.exists():
        raise FileNotFoundError(f"Template not found: {template_path}")

    if out_name is None:
        st_val = spieltag if spieltag is not None else "X"
        out_name = f"tabelle_spieltag_{int(st_val):02d}.png" if str(st_val).isdigit() else f"tabelle_spieltag_{st_val}.png"

    out_path = paths.output_dir / out_name
    out_path.parent.mkdir(parents=True, exist_ok=True)

    img = Image.open(template_path).convert("RGBA")
    draw = ImageDraw.Draw(img)

    # Fonts
    font_bold_path = paths.fonts_dir / "Inter-Bold.ttf"
    font_med_path = paths.fonts_dir / "Inter-Medium.ttf"

    # Header brand
    font_brand = _load_font(font_bold_path, 34)
    draw_text_fx(
        img,
        (layout.width // 2, layout.header_brand_y),
        "PULS",
        font_brand,
        fill=layout.color_accent,
        anchor="mm",
        glow=True,
        glow_radius=10,
        glow_alpha=120,
        shadow=True,
        shadow_offset=(0, 3),
        shadow_alpha=140,
        stroke=True,
        stroke_width=2,
        stroke_fill=(0, 0, 0, 170),
    )

    # Header title
    font_title = _fit_text(draw, "LIGA-TABELLE", font_bold_path, max_width=920, start_size=74, min_size=48)
    draw_text_fx(
        img,
        (layout.width // 2, layout.header_title_y),
        "LIGA-TABELLE",
        font_title,
        fill=layout.color_text,
        anchor="mm",
        glow=False,
        shadow=True,
        shadow_offset=(0, 4),
        shadow_alpha=150,
        stroke=True,
        stroke_width=2,
        stroke_fill=(0, 0, 0, 170),
    )

    # Sub
    font_sub = _fit_text(draw, sub, font_med_path, max_width=920, start_size=26, min_size=18)
    draw.text((layout.width // 2, layout.header_sub_y), sub, font=font_sub, fill=layout.color_accent, anchor="mm")

    # Δ date sichtbar
    font_date = _load_font(font_med_path, 20)
    draw.text((layout.width // 2, layout.header_date_y), date_str, font=font_date, fill=layout.color_accent, anchor="mm")

    # display map (optional)
    display_map_path = paths.fonts_dir.parent / "team_display_names.json"
    display_map: Dict[str, str] = {}
    if display_map_path.exists():
        display_map = json.loads(display_map_path.read_text(encoding="utf-8"))

    # Blocks
    _draw_table_block(
        img=img,
        draw=draw,
        layout=layout,
        title="TABELLE NORD",
        title_y=layout.nord_title_y,
        table_top=layout.nord_table_top,
        rows=nord_rows,
        logos_dir=paths.logos_dir,
        fonts_dir=paths.fonts_dir,
        display_map=display_map,
    )

    _draw_table_block(
        img=img,
        draw=draw,
        layout=layout,
        title="TABELLE SÜD",
        title_y=layout.sued_title_y,
        table_top=layout.sued_table_top,
        rows=sued_rows,
        logos_dir=paths.logos_dir,
        fonts_dir=paths.fonts_dir,
        display_map=display_map,
    )

    # watermark
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


# Backwards-compatible alias
def render_table_from_matchday_json(*args, **kwargs) -> Path:
    return render_league_table_from_matchday_json(*args, **kwargs)
