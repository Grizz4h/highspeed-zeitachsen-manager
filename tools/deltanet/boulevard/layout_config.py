from dataclasses import dataclass
from typing import Tuple


@dataclass(frozen=True)
class DeltaNetBoulevardLayoutV1:
    width: int = 1080
    height: int = 1350

    # Safe area for text (inside your frame)
    left: int = 110
    right: int = 970

    # Font start sizes (fit reduces)
    kicker_size: int = 100
    headline_size: int = 110
    teaser_size: int = 34
    meta_size: int = 24
    watermark_size: int = 22
    brand_size: int = 26

    # Positions
    y_brand: int = 110          # "DELTANET" or small brand line
    y_kicker: int = 190         # small "EXKLUSIV" etc.
    y_headline: int = 320       # giant headline block
    y_teaser: int = 720         # short teaser block
    y_meta: int = 1250          # date/location line
    x_meta_left: int = 350
    x_watermark: int = 910
    y_watermark: int = 1320

    # Line gaps
    headline_gap: int = 16
    teaser_gap: int = 10

    # Colors
    color_text: Tuple[int, int, int, int] = (240, 242, 245, 255)
    color_muted: Tuple[int, int, int, int] = (170, 175, 180, 255)
    color_hot: Tuple[int, int, int, int] = (255, 90, 120, 255)   # boulevard pop
    color_warn: Tuple[int, int, int, int] = (255, 170, 70, 255)
