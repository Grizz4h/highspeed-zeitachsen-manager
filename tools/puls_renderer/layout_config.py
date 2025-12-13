from dataclasses import dataclass
from typing import List, Tuple


@dataclass(frozen=True)
class MatchdayLayoutV1:
    # Canvas
    width: int = 1080
    height: int = 1350

    # --- Header: "SPIELTAG XX" (zentriert unter PULS) ---
    header_center_x: int = 540
    header_spieltag_y: int = 210

    # --- Match rows: Y-Positionen ---
    # Leicht hochgezogen im Süd-Block (unten war's bei dir am knappsten)
    y_nord: List[int] = (430, 510, 590, 670, 750)
    y_sued: List[int] = (875, 955, 1035, 1110, 1185)

    # --- Symmetrie / Slots ---
    center_x: int = 540

    # VS-Korridor enger -> mehr Platz für Teamnamen
    vs_gap_half_width: int = 70  # vorher 90

    # Logos
    logo_size: int = 54

    # Home-Logo weiter nach außen (mehr nutzbare Breite)
    x_logo_home: int = 80

    # Away-Logo weiter nach außen (mehr nutzbare Breite)
    x_logo_away: int = 946  # 1080 - 80 - 54

    # Teamnamen
    # Home-Text startet näher am Logo (und insgesamt weiter links)
    x_text_home: int = 150  # Logo (80) + 54 + ~16

    # Away-Text endet näher am Logo (rechtsbündig) -> weniger verschenkter Platz
    x_text_away: int = 930  # nah ans Logo ran, aber nicht kollidieren

    @property
    def max_width_home(self) -> int:
        return (self.center_x - self.vs_gap_half_width) - self.x_text_home

    @property
    def max_width_away(self) -> int:
        return self.x_text_away - (self.center_x + self.vs_gap_half_width)

    # --- Footer: Datum ---
    footer_date_center_x: int = 540
    footer_date_y: int = 1285

    # Colors (RGBA)
    color_text: Tuple[int, int, int, int] = (174, 220, 255, 255)  # #AEDCFF
    color_accent: Tuple[int, int, int, int] = (120, 190, 220, 255) # eisblau
