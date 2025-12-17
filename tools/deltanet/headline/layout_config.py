# tools/deltanet/headline/layout_config.py
from dataclasses import dataclass
from typing import Tuple


@dataclass(frozen=True)
class DeltaNetHeadlineLayoutV1:
    # Canvas
    width: int = 1080
    height: int = 1350

    # Content frame bounds (Text soll im Frame bleiben)
    content_left: int = 110
    content_right: int = 970

    # Font start sizes (fit_text skaliert runter)
    meta_size: int = 22
    headline_size: int = 92
    subline_size: int = 36
    watermark_size: int = 18

    # --- Top meta block (optional, wenn du oben noch Datum/Ort etc. willst) ---
    y_meta_top: int = 170
    meta_line_gap: int = 18

    # --- Main blocks ---
    y_headline_top: int = 480          # nach oben geschoben (mehr Luft unten)
    headline_line_gap: int = 18

    y_subline_top: int = 680           # näher an Headline, aber noch Luft
    subline_line_gap: int = 10

    # --- Bottom meta row (Datum | Ort | Status nebeneinander) ---
    y_meta_row: int = 1010
    x_date: int = 120
    x_location: int = 380
    x_status: int = 780

    # Optional: Priority unter Status (kleiner / sekundär)
    y_priority: int = 900
    x_priority: int = 830

    # --- Watermark / source bottom-right ---
    x_watermark: int = 1050
    y_watermark: int = 1320

    # Colors (RGBA)
    color_text: Tuple[int, int, int, int] = (230, 232, 235, 255)
    color_muted: Tuple[int, int, int, int] = (160, 165, 170, 255)
    color_amber: Tuple[int, int, int, int] = (230, 160, 60, 255)
    color_red: Tuple[int, int, int, int] = (220, 70, 70, 255)
