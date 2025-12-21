from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import difflib


def _normalize(s: str) -> str:
    if s is None:
        return ""
    s = s.strip()
    s = re.sub(r"\s+", " ", s)
    s = s.casefold()
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    return s


@dataclass
class NameMatch:
    real: Optional[str]
    fake: Optional[str]
    confidence: float
    suggestions: List[Tuple[str, str, float]]  # (real, fake, score)


class NameMapper:
    def __init__(self, mapping: List[dict]):
        self.real_to_fake: Dict[str, str] = {}
        self._norm_real_index: Dict[str, str] = {}  # norm real -> original real

        for row in mapping:
            real = (row.get("real") or "").strip()
            fake = (row.get("fake") or "").strip()
            if not real or not fake:
                continue
            self.real_to_fake[real] = fake
            self._norm_real_index[_normalize(real)] = real

        self._real_names_sorted = sorted(self.real_to_fake.keys(), key=len, reverse=True)
        escaped = [re.escape(n) for n in self._real_names_sorted]
        self._replace_pattern = re.compile(r"(?<!\w)(" + "|".join(escaped) + r")(?!\w)")

    @classmethod
    def from_repo_file(cls) -> "NameMapper":
        # tools/deltanet/name_mapper.py -> tools/deltanet/data/mapping_player_names.json
        base = Path(__file__).resolve().parent
        path = base / "data" / "mapping_player_names.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            raise ValueError("mapping_player_names.json must be a list of {real,fake} objects")
        return cls(data)

    def lookup_fake(self, real_name: str, suggest_n: int = 5) -> NameMatch:
        q = _normalize(real_name)
        if not q:
            return NameMatch(real=None, fake=None, confidence=0.0, suggestions=[])

        # exact normalized match
        original_real = self._norm_real_index.get(q)
        if original_real:
            return NameMatch(real=original_real, fake=self.real_to_fake.get(original_real), confidence=1.0, suggestions=[])

        # suggest
        keys = list(self._norm_real_index.keys())
        close = difflib.get_close_matches(q, keys, n=suggest_n, cutoff=0.6)

        suggestions: List[Tuple[str, str, float]] = []
        for k in close:
            r = self._norm_real_index[k]
            f = self.real_to_fake.get(r)
            score = difflib.SequenceMatcher(None, q, k).ratio()
            suggestions.append((r, f, score))

        if suggestions:
            best = suggestions[0]
            return NameMatch(real=best[0], fake=best[1], confidence=best[2], suggestions=suggestions)

        return NameMatch(real=None, fake=None, confidence=0.0, suggestions=[])

    def replace_in_text(self, text: str) -> str:
        if not text:
            return text

        def _repl(m: re.Match) -> str:
            real = m.group(1)
            return self.real_to_fake.get(real, real)

        return self._replace_pattern.sub(_repl, text)

    def size(self) -> int:
        return len(self.real_to_fake)
