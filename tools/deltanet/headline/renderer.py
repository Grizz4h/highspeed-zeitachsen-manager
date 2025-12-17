# tools/deltanet/headline/renderer.py
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Dict, Any, Tuple
import json
import re
from datetime import datetime

from PIL import Image, ImageDraw, ImageFont

from .layout_config import DeltaNetHeadlineLayoutV1


@dataclass
class DeltaNetPaths:
    tools_dir: Path  # .../tools

    @property
    def template_path(self) -> Path:
        return self.tools_dir / "deltanet" / "data" / "deltanet_headline_v1.png"

    @property
    def fonts_dir(self) -> Path:
        return self.tools_dir / "puls_renderer" / "assets" / "fonts"

    @property
    def output_dir(self) -> Path:
        return self.tools_dir / "deltanet" / "headline" / "output"


def _ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


def _fit_text(draw: ImageDraw.ImageDraw, text: str, font_path: Path, max_width: int, start_size: int, min_size: int = 12) -> ImageFont.FreeTypeFont:
    size = start_size
    while size >= min_size:
        f = ImageFont.truetype(str(font_path), size=size)
        bbox = draw.textbbox((0, 0), text, font=f)
        w = bbox[2] - bbox[0]
        if w <= max_width:
            return f
        size -= 1
    return ImageFont.truetype(str(font_path), size=min_size)


def _wrap_text(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, max_width: int) -> str:
    # Sehr robustes Wrap (Whitespace + harte Zeilenumbrüche respektieren)
    text = (text or "").strip()
    if not text:
        return ""

    lines = []
    for raw_line in text.splitlines():
        words = raw_line.split()
        if not words:
            lines.append("")
            continue

        cur = words[0]
        for w in words[1:]:
            test = f"{cur} {w}"
            bbox = draw.textbbox((0, 0), test, font=font)
            width = bbox[2] - bbox[0]
            if width <= max_width:
                cur = test
            else:
                lines.append(cur)
                cur = w
        lines.append(cur)

    return "\n".join(lines)


def _status_color(layout: DeltaNetHeadlineLayoutV1, status: str) -> Tuple[int, int, int, int]:
    s = (status or "").upper().strip()
    if s in ("CRITICAL", "BREAK", "ALERT"):
        return layout.color_red
    if s in ("UNVERIFIED", "DEVELOPING", "AMBER"):
        return layout.color_amber
    return layout.color_muted


def _sanitize_filename(s: str) -> str:
    s = (s or "").strip().lower()
    s = re.sub(r"[^a-z0-9\-_]+", "-", s)
    s = re.sub(r"-{2,}", "-", s).strip("-")
    return s or "deltanet"


def save_payload_json(payload: Dict[str, Any], data_dir: Path) -> Path:
    _ensure_dir(data_dir)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    slug = _sanitize_filename(payload.get("headline", "")[:48])
    out = data_dir / f"{ts}_{slug}.json"
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return out


def render_deltanet_headline(
    payload: Dict[str, Any],
    out_name: Optional[str] = None,
    template_path: Optional[Path] = None,
) -> Path:
    """
    DeltaNet Headline Renderer (Authoring-Usecase)
    Payload expected (minimal):
      - delta_date (str)
      - location (str)
      - status (str)
      - priority (str)
      - headline (str)      (can contain \\n)
      - subline (str)       optional
      - source (str)        optional
    """
    layout = DeltaNetHeadlineLayoutV1()

    tools_dir = Path(__file__).resolve().parents[2]  # .../tools
    paths = DeltaNetPaths(tools_dir=tools_dir)

    tpath = template_path or paths.template_path
    if not tpath.exists():
        raise FileNotFoundError(f"Template not found: {tpath}")

    _ensure_dir(paths.output_dir)

    # Output name
    if out_name is None:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        slug = _sanitize_filename(payload.get("headline", "")[:48])
        out_name = f"deltanet_headline_{ts}_{slug}.png"

    out_path = paths.output_dir / out_name

    img = Image.open(tpath).convert("RGBA")
    draw = ImageDraw.Draw(img)

    font_bold = paths.fonts_dir / "Inter-Bold.ttf"
    font_med = paths.fonts_dir / "Inter-Medium.ttf"

    if not font_bold.exists() or not font_med.exists():
        raise FileNotFoundError(f"Fonts not found. Expected in: {paths.fonts_dir}")

    # --- Read payload ---
    delta_date = str(payload.get("delta_date", "")).strip()
    location = str(payload.get("location", "")).strip()
    status = str(payload.get("status", "")).strip().upper()
    priority = str(payload.get("priority", "")).strip().upper()

    headline = str(payload.get("headline", "")).strip()
    subline = str(payload.get("subline", "")).strip()
    source = str(payload.get("source", "ΔNet Aggregation Node")).strip()

    # --- Meta block ---
    meta_max_w = layout.content_right - layout.content_left
    meta_font = ImageFont.truetype(str(font_med), size=layout.meta_size)

    # Meta lines: wir halten das bewusst kompakt
    meta_lines = [
        delta_date,
        location,
        f"STATUS: {status}" if status else "",
        f"PRIORITY: {priority}" if priority else "",
    ]
    meta_lines = [l for l in meta_lines if l]


    # --- Headline (wrap + fit) ---
    head_max_w = meta_max_w
    # erst mit Startfont messen, dann ggf. wrap
    head_font = ImageFont.truetype(str(font_bold), size=layout.headline_size)
    headline_wrapped = headline

    # Wenn kein \n drin ist, erlauben wir auto-wrap
    if "\n" not in headline_wrapped:
        headline_wrapped = _wrap_text(draw, headline_wrapped, head_font, head_max_w)

    # Fit: wir rechnen auf Basis der längsten Zeile
    longest = max((len(l) for l in headline_wrapped.splitlines()), default=0)
    # Fit anhand tatsächlicher Pixelbreite je Zeile
    # -> wir nehmen max der Zeilenbreiten
    def _max_line_px(fnt: ImageFont.FreeTypeFont) -> int:
        mx = 0
        for l in headline_wrapped.splitlines():
            bbox = draw.textbbox((0, 0), l, font=fnt)
            mx = max(mx, bbox[2] - bbox[0])
        return mx

    size = layout.headline_size
    while size >= 44:
        f = ImageFont.truetype(str(font_bold), size=size)
        if _max_line_px(f) <= head_max_w:
            head_font = f
            break
        size -= 1

    y = layout.y_headline_top
    for line in headline_wrapped.splitlines():
        draw.text((layout.content_left, y), line.upper(), font=head_font, fill=layout.color_text, anchor="la")
        y += (head_font.size + layout.headline_line_gap)

    # --- Subline (optional) ---
    if subline:
        sub_max_w = meta_max_w
        sub_font = _fit_text(draw, subline, font_med, max_width=sub_max_w, start_size=layout.subline_size, min_size=20)
        sub_wrapped = _wrap_text(draw, subline, sub_font, sub_max_w)

        y = layout.y_subline_top
        for line in sub_wrapped.splitlines():
            draw.text((layout.content_left, y), line, font=sub_font, fill=layout.color_muted, anchor="la")
            y += (sub_font.size + layout.subline_line_gap)

    # --- Footer/source ---
    foot = source
        # --- Bottom Meta Row: date | location | status ---
    delta_date = (
    payload.get("date")
    or payload.get("delta_date")
    or payload.get("datum")
    or ""
).strip()

    location   = payload.get("location", "").strip()

    status = payload.get("status", "").strip()
    if status:
        status_text = f"STATUS: {status.upper()}"
    else:
        status_text = ""

    font_med_path = paths.fonts_dir / "Inter-Medium.ttf"
    meta_font = ImageFont.truetype(str(font_med_path), size=layout.meta_size)

    y = layout.y_meta_row

    # date (muted)
    if delta_date:
        draw.text(
            (layout.x_date, y),
            delta_date,
            font=meta_font,
            fill=layout.color_muted,
            anchor="lm",
        )

    # location (muted)
    if location:
        draw.text(
            (layout.x_location, y),
            location.upper(),
            font=meta_font,
            fill=layout.color_muted,
            anchor="lm",
        )

    # status (amber/red/text)
    status_fill = layout.color_text
    if status.upper() in {"UNVERIFIED", "AMBER", "WARNING"}:
        status_fill = layout.color_amber
    elif status.upper() in {"CRITICAL", "BREAK", "ALERT"}:
        status_fill = layout.color_red

    if status_text:
        draw.text(
            (layout.x_status, y),
            status_text,
            font=meta_font,
            fill=status_fill,
            anchor="lm",
        )

    # optional priority under status (small, same x)
    priority = payload.get("priority", "").strip()
    if priority:
        pr_font = ImageFont.truetype(str(font_med_path), size=max(16, layout.meta_size - 8))
        draw.text(
            (layout.x_priority, layout.y_priority),
            f"PRIORITY: {priority.upper()}",
            font=pr_font,
            fill=layout.color_amber,
            anchor="lm",
        )

        # --- Watermark / Source (bottom-right) ---
    watermark = payload.get("source", "ΔNet Core Feed")

    wm_font = ImageFont.truetype(
        str(font_med),
        size=layout.watermark_size
    )

    draw.text(
        (layout.x_watermark, layout.y_watermark),
        watermark,
        font=wm_font,
        fill=layout.color_muted,
        anchor="rd"  # right-down
    )


    img.save(out_path)
    return out_path

# ---- compatibility alias ----
# falls die Funktion anders heißt:
render_deltanet_headline = render_deltanet_headline  # nur wenn sie schon genauso heißt

# Beispiel, wenn sie render_headline heißt:
# render_deltanet_headline = render_headline
