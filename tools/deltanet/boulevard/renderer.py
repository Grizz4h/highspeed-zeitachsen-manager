from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Any, Optional, Tuple, List
import json
import re
import random
from datetime import datetime

from PIL import Image, ImageDraw, ImageFont

from .layout_config import DeltaNetBoulevardLayoutV1


# ----------------------------
# Background Auswahl (Dropdown Key -> Datei)
# ----------------------------
BG_MAP = {
    # Keys, die du im Payload setzen kannst:
    "urban": "urban_life_stadtgeschehen.png",
    "infrastruktur": "infrastruktur_und_system.png",
    "trash": "influencer_trash_boulevard.png",
    "chaos": "sicherheit_vorfaelle_chaos.png",
    "lifestyle": "Lifestyle_konsum.png",
    "sportnews": "sport_news.png",
        # so wie deine Datei aktuell heißt
}

# Aliases (optional, falls du mal andere Begriffe nutzt)
BG_ALIASES = {
    "urban_life": "urban",
    "stadt": "urban",
    "stadtgeschehen": "urban",

    "infra": "infrastruktur",
    "infrastruktur": "infrastruktur",
    "system": "infrastruktur",

    "influencer": "trash",
    "boulevard": "trash",
    "influencertrashbulletball": "trash",

    "sicherheit": "chaos",
    "vorfaelle": "chaos",
    "incidents": "chaos",

    "konsum": "lifestyle",
    "sport_news": "sportnews",
    "sport": "sportnews",
}


DEFAULT_BG_KEY = "urban"


# ----------------------------
# Paths
# ----------------------------
@dataclass
class BoulevardPaths:
    tools_dir: Path  # .../tools

    @property
    def data_dir(self) -> Path:
        return self.tools_dir / "deltanet" / "data"

    @property
    def template_fallback_path(self) -> Path:
        # fallback, falls bg fehlt oder Datei nicht existiert
        return self.data_dir / "deltanet_boulevard_v1.png"

    @property
    def fonts_dir(self) -> Path:
        return self.tools_dir / "puls_renderer" / "assets" / "fonts"

    @property
    def output_dir(self) -> Path:
        return self.tools_dir / "deltanet" / "boulevard" / "output"

    @property
    def payload_dir(self) -> Path:
        return self.tools_dir / "deltanet" / "boulevard" / "payloads"


def _ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


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


# ----------------------------
# Helpers: Text fitting / wrapping
# ----------------------------
def _fit_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    font_path: Path,
    max_width: int,
    start_size: int,
    min_size: int = 12,
) -> ImageFont.FreeTypeFont:
    size = start_size
    while size >= min_size:
        f = ImageFont.truetype(str(font_path), size=size)
        bbox = draw.textbbox((0, 0), text, font=f)
        w = bbox[2] - bbox[0]
        if w <= max_width:
            return f
        size -= 1
    return ImageFont.truetype(str(font_path), size=min_size)


def _wrap_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.FreeTypeFont,
    max_width: int,
) -> List[str]:
    """
    Wrappt in echte Render-Zeilen. Gibt LISTE von Zeilen zurück (kein \\n String),
    damit wir später pro Zeile Marker zeichnen können.
    """
    text = (text or "").strip()
    if not text:
        return []

    out: List[str] = []
    for raw_line in text.splitlines():
        words = raw_line.split()
        if not words:
            out.append("")
            continue

        cur = words[0]
        for w in words[1:]:
            test = f"{cur} {w}"
            bbox = draw.textbbox((0, 0), test, font=font)
            if (bbox[2] - bbox[0]) <= max_width:
                cur = test
            else:
                out.append(cur)
                cur = w
        out.append(cur)

    return out


RGBA = Tuple[int, int, int, int]


def draw_marker_lines(
    img: Image.Image,
    draw: ImageDraw.ImageDraw,
    x: int,
    y: int,
    lines: List[str],
    font: ImageFont.FreeTypeFont,
    text_fill: RGBA,
    marker_fill: RGBA,
    line_gap: int,
    pad_x: int = 18,
    pad_y: int = 10,
    jitter_right: int = 28,
    jitter_y: int = 3,
    radius: int = 10,
    seed: int = 7,
) -> int:
    """
    Textmarker-Look pro Zeile:
    - misst die echte Textbbox
    - zeichnet ein leicht "organisches" Marker-Rechteck (rechte Kante jitter)
    - zeichnet Text darüber

    Gibt das y nach dem Block zurück.
    """
    rnd = random.Random(seed)
    cy = y

    for line in lines:
        if not line.strip():
            cy += font.size + line_gap
            continue

        bbox = draw.textbbox((x, cy), line, font=font, anchor="la")
        x0, y0, x1, y1 = bbox

        jr = rnd.randint(-jitter_right // 3, jitter_right)  # eher länger als kürzer
        jy1 = rnd.randint(-jitter_y, jitter_y)
        jy2 = rnd.randint(-jitter_y, jitter_y)

        rect = (
            x0 - pad_x,
            y0 - pad_y + jy1,
            x1 + pad_x + jr,
            y1 + pad_y + jy2,
        )

        overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
        od = ImageDraw.Draw(overlay)
        od.rounded_rectangle(rect, radius=radius, fill=marker_fill)
        img.alpha_composite(overlay)

        draw.text((x, cy), line, font=font, fill=text_fill, anchor="la")
        cy += font.size + line_gap

    return cy


def _fit_headline_font_then_wrap(
    draw: ImageDraw.ImageDraw,
    font_path: Path,
    text: str,
    max_width: int,
    start_size: int,
    min_size: int,
) -> Tuple[ImageFont.FreeTypeFont, List[str]]:
    """
    Wichtig: erst Fontgröße finden, dann mit dieser Fontgröße wrappen.
    Sonst ist dein Wrapping inkonsistent.
    """
    size = start_size
    best_font = ImageFont.truetype(str(font_path), size=min_size)

    while size >= min_size:
        f = ImageFont.truetype(str(font_path), size=size)
        lines = _wrap_text(draw, text, f, max_width)

        ok = True
        for line in lines:
            bbox = draw.textbbox((0, 0), line, font=f)
            if (bbox[2] - bbox[0]) > max_width:
                ok = False
                break

        if ok:
            best_font = f
            return best_font, lines

        size -= 2

    # fallback
    lines = _wrap_text(draw, text, best_font, max_width)
    return best_font, lines


def _resolve_bg_key(raw: Any) -> str:
    k = (raw or "").strip().lower()
    if not k:
        return DEFAULT_BG_KEY
    if k in BG_MAP:
        return k
    if k in BG_ALIASES:
        return BG_ALIASES[k]
    # letzte chance: sanitize (z.B. "Lifestyle & Konsum" -> "lifestyle-konsum" -> maybe alias fehlt)
    k2 = re.sub(r"[^a-z0-9]+", "_", k).strip("_")
    return BG_ALIASES.get(k2, BG_MAP.get(k2, DEFAULT_BG_KEY) if k2 in BG_MAP else DEFAULT_BG_KEY)


def _pick_background_path(paths: BoulevardPaths, payload: Dict[str, Any]) -> Path:
    bg_key = _resolve_bg_key(payload.get("bg") or payload.get("background"))
    bg_file = BG_MAP.get(bg_key, BG_MAP[DEFAULT_BG_KEY])
    p = paths.data_dir / bg_file
    if p.exists():
        return p

    # fallback auf dein altes Template (falls vorhanden)
    if paths.template_fallback_path.exists():
        return paths.template_fallback_path

    raise FileNotFoundError(
        f"Background not found: {p} (bg='{bg_key}') "
        f"and fallback not found: {paths.template_fallback_path}"
    )


# ----------------------------
# Renderer
# ----------------------------
def render_deltanet_boulevard(payload: Dict[str, Any], out_name: Optional[str] = None) -> Path:
    layout = DeltaNetBoulevardLayoutV1()

    tools_dir = Path(__file__).resolve().parents[2]  # .../tools
    paths = BoulevardPaths(tools_dir=tools_dir)

    _ensure_dir(paths.output_dir)
    _ensure_dir(paths.payload_dir)

    # Output name
    if out_name is None:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        slug = _sanitize_filename(payload.get("headline", "")[:48])
        out_name = f"deltanet_boulevard_{ts}_{slug}.png"
    out_path = paths.output_dir / out_name

    # Background aus Dropdown-Key laden
    bg_path = _pick_background_path(paths, payload)

    img = Image.open(bg_path).convert("RGBA")
    draw = ImageDraw.Draw(img)

    font_bold = paths.fonts_dir / "Inter-Bold.ttf"
    font_med = paths.fonts_dir / "Inter-Medium.ttf"
    if not font_bold.exists() or not font_med.exists():
        raise FileNotFoundError(f"Fonts not found in: {paths.fonts_dir}")

    max_w = getattr(layout, "right", img.width - 80) - getattr(layout, "left", 80)

    # Payload
    brand = (payload.get("brand") or "ΔNET - Boulevard").strip()
    kicker = (payload.get("kicker") or "EXKLUSIV").strip()
    headline = (payload.get("headline") or "").strip()
    teaser = (payload.get("teaser") or "").strip()

    delta_date = (payload.get("delta_date") or payload.get("date") or "").strip()
    location = (payload.get("location") or "").strip()
    desk = (payload.get("desk") or "ΔNet · Satirische Parallelmeldungen aus dem HIGHspeed-Universum.").strip()

    heat = (payload.get("heat") or "HOT").strip().upper()
    if heat in ("HOT", "BREAKING"):
        kicker_color = getattr(layout, "color_hot", (255, 90, 120, 255))
        kicker_marker = getattr(layout, "color_hot_marker", (255, 90, 120, 220))
        kicker_text = getattr(layout, "color_hot_text", (20, 20, 20, 255))
    elif heat in ("AMBER", "WARM"):
        kicker_color = getattr(layout, "color_warn", (255, 190, 80, 255))
        kicker_marker = getattr(layout, "color_warn_marker", (255, 190, 80, 220))
        kicker_text = getattr(layout, "color_warn_text", (20, 20, 20, 255))
    else:
        kicker_color = getattr(layout, "color_muted", (180, 185, 190, 255))
        kicker_marker = getattr(layout, "color_muted_marker", (40, 40, 45, 180))
        kicker_text = getattr(layout, "color_text", (230, 232, 235, 255))

    # Defaults, falls Layout-Felder fehlen
    left = getattr(layout, "left", 80)
    y_brand = getattr(layout, "y_brand", 120)
    y_kicker = getattr(layout, "y_kicker", 180)
    y_headline = getattr(layout, "y_headline", 320)
    y_teaser = getattr(layout, "y_teaser", 780)

    headline_gap = getattr(layout, "headline_gap", 18)
    teaser_gap = getattr(layout, "teaser_gap", 10)

    color_muted = getattr(layout, "color_muted", (180, 185, 190, 255))
    color_text = getattr(layout, "color_text", (235, 238, 242, 255))
    color_teaser = getattr(layout, "color_teaser", color_muted)

    # BRAND (small) — safe fallback statt layout.brand_size crash
    brand_size = getattr(layout, "brand_size", 24)
    f_brand = _fit_text(draw, brand.upper(), font_med, max_w, start_size=brand_size, min_size=16)
    draw.text((left, y_brand), brand.upper(), font=f_brand, fill=color_muted, anchor="la")

    # KICKER (Marker + Text)
    kicker_size = getattr(layout, "kicker_size", 72)
    f_kicker = _fit_text(draw, kicker.upper(), font_bold, max_w, start_size=kicker_size, min_size=22)
    kicker_lines = [kicker.upper()]

    draw_marker_lines(
        img, draw,
        x=left,
        y=y_kicker,
        lines=kicker_lines,
        font=f_kicker,
        text_fill=kicker_text,
        marker_fill=kicker_marker,
        line_gap=0,
        pad_x=getattr(layout, "kicker_pad_x", 16),
        pad_y=getattr(layout, "kicker_pad_y", 10),
        jitter_right=getattr(layout, "kicker_jitter_right", 18),
        jitter_y=getattr(layout, "kicker_jitter_y", 2),
        radius=getattr(layout, "kicker_radius", 10),
        seed=1,
    )

    # HEADLINE (Marker + Text)
    headline_text = headline.upper()
    headline_size = getattr(layout, "headline_size", 88)
    headline_min_size = getattr(layout, "headline_min_size", 54)

    f_head, head_lines = _fit_headline_font_then_wrap(
        draw=draw,
        font_path=font_bold,
        text=headline_text,
        max_width=max_w,
        start_size=headline_size,
        min_size=headline_min_size,
    )

    draw_marker_lines(
        img, draw,
        x=left,
        y=y_headline,
        lines=head_lines,
        font=f_head,
        text_fill=color_text,
        marker_fill=getattr(layout, "headline_marker_fill", (15, 20, 30, 180)),
        line_gap=headline_gap,
        pad_x=getattr(layout, "headline_pad_x", 22),
        pad_y=getattr(layout, "headline_pad_y", 14),
        jitter_right=getattr(layout, "headline_jitter_right", 42),
        jitter_y=getattr(layout, "headline_jitter_y", 3),
        radius=getattr(layout, "headline_radius", 12),
        seed=4,
    )

    # TEASER (ohne Marker, aber heller & weiter unten)
    if teaser:
        teaser_size = getattr(layout, "teaser_size", 26)
        f_teaser = _fit_text(draw, teaser, font_med, max_w, start_size=teaser_size, min_size=18)
        teaser_lines = _wrap_text(draw, teaser, f_teaser, max_w)

        y = y_teaser
        for line in teaser_lines:
            draw.text((left, y), line, font=f_teaser, fill=color_teaser, anchor="la")
            y += f_teaser.size + teaser_gap

    # META bottom-left (Datum | Ort)
    meta_size = getattr(layout, "meta_size", 22)
    x_meta_left = getattr(layout, "x_meta_left", left)
    y_meta = getattr(layout, "y_meta", img.height - 140)

    meta_parts = []
    if delta_date:
        meta_parts.append(delta_date)
    if location:
        meta_parts.append(location.upper())
    meta = "  |  ".join(meta_parts)

    if meta:
        f_meta = ImageFont.truetype(str(font_med), size=meta_size)
        draw.text((x_meta_left, y_meta), meta, font=f_meta, fill=color_muted, anchor="la")

    # DESK bottom-right
    watermark_size = getattr(layout, "watermark_size", 20)
    x_watermark = getattr(layout, "x_watermark", img.width - 80)
    y_watermark = getattr(layout, "y_watermark", img.height - 80)

    f_wm = ImageFont.truetype(str(font_med), size=watermark_size)
    draw.text((x_watermark, y_watermark), desk, font=f_wm, fill=color_muted, anchor="rd")

    img.save(out_path)
    return out_path
