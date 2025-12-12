#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Literal, Optional

ContentType = Literal["episode", "sim", "promo", "news"]

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_CONFIG = BASE_DIR / "canon_time_config.json"



@dataclass(frozen=True)
class CanonConfig:
    world_today: date
    season_start: dict[int, date]                  # season -> matchday 1 date
    matchday_interval_days: int
    offset_rules: dict[str, tuple[int, int]]       # content_type -> (min,max)


def load_config(path: Path) -> CanonConfig:
    if not path.exists():
        raise FileNotFoundError(f"Config not found: {path}")

    d = json.loads(path.read_text(encoding="utf-8"))

    season_start_raw = d.get("season_start")
    if not isinstance(season_start_raw, dict) or not season_start_raw:
        raise ValueError("Config error: 'season_start' must be a non-empty object.")

    offset_rules_raw = d.get("offset_rules")
    if not isinstance(offset_rules_raw, dict) or not offset_rules_raw:
        raise ValueError("Config error: 'offset_rules' must be a non-empty object.")

    season_start = {int(k): date.fromisoformat(v) for k, v in season_start_raw.items()}

    offset_rules: dict[str, tuple[int, int]] = {}
    for k, v in offset_rules_raw.items():
        if not (isinstance(v, list) and len(v) == 2 and all(isinstance(x, int) for x in v)):
            raise ValueError(f"Config error: offset_rules['{k}'] must be [min,max] ints.")
        offset_rules[k] = (v[0], v[1])

    return CanonConfig(
        world_today=date.fromisoformat(d["world_today"]),
        season_start=season_start,
        matchday_interval_days=int(d.get("matchday_interval_days", 3)),
        offset_rules=offset_rules,
    )


def matchday_date(cfg: CanonConfig, season: int, matchday: int) -> date:
    if season not in cfg.season_start:
        raise ValueError(f"Missing season_start for season {season}. Add it to config.")
    if matchday < 1:
        raise ValueError("matchday must be >= 1")

    start = cfg.season_start[season]
    return start + timedelta(days=(matchday - 1) * cfg.matchday_interval_days)


def allocate_inworld_date(
    cfg: CanonConfig,
    *,
    season: int,
    matchday: int,
    content_type: ContentType,
    offset_days: int,
    allow_future: bool,
) -> date:
    base = matchday_date(cfg, season, matchday)

    if content_type not in cfg.offset_rules:
        raise ValueError(f"Unknown content_type '{content_type}'. Allowed: {list(cfg.offset_rules.keys())}")

    min_off, max_off = cfg.offset_rules[content_type]
    if not (min_off <= offset_days <= max_off):
        raise ValueError(
            f"Offset {offset_days} out of bounds for '{content_type}': allowed {min_off}..{max_off}"
        )

    d = base + timedelta(days=offset_days)

    # Gate against accidental future canon content
    if not allow_future and d > cfg.world_today:
        raise ValueError(
            f"inWorldDate {d.isoformat()} is after world_today {cfg.world_today.isoformat()}. "
            f"Advance world_today in config or pass --allow-future for planned content."
        )

    return d


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, obj: dict) -> None:
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8")


def write_inworld_date(
    *,
    json_path: Path,
    inworld_date: date,
    field: str,
    dry_run: bool,
) -> None:
    obj = load_json(json_path)
    obj[field] = inworld_date.isoformat()
    if dry_run:
        print(f"[dry-run] Would write {field}={obj[field]} into {json_path}")
        return
    save_json(json_path, obj)
    print(f"Wrote {field}={obj[field]} into {json_path}")


def cmd_alloc(args: argparse.Namespace) -> int:
    cfg = load_config(Path(args.config))

    inworld = allocate_inworld_date(
        cfg,
        season=args.season,
        matchday=args.matchday,
        content_type=args.type,
        offset_days=args.offset,
        allow_future=args.allow_future,
    )

    # Always print the computed date (so you can pipe it)
    print(inworld.isoformat())

    # Optional: write into a JSON file
    if args.write:
        write_inworld_date(
            json_path=Path(args.write),
            inworld_date=inworld,
            field=args.field,
            dry_run=args.dry_run,
        )

    return 0


def cmd_table(args: argparse.Namespace) -> int:
    cfg = load_config(Path(args.config))
    season = args.season
    start = args.start
    end = args.end

    if end < start:
        raise ValueError("end must be >= start")

    print(f"Season {season} | Matchdays {start}..{end} | Interval {cfg.matchday_interval_days} days")
    print("-" * 64)
    for md in range(start, end + 1):
        d = matchday_date(cfg, season, md)
        print(f"MD{md:02d}: {d.isoformat()}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="canon_time",
        description="Allocate canonical in-world dates based on season/matchday cadence.",
    )
    p.add_argument("--config", default=str(DEFAULT_CONFIG), help="Path to canon_time_config.json")

    sub = p.add_subparsers(dest="cmd", required=True)

    alloc = sub.add_parser("alloc", help="Compute an in-world date for a content item (optionally write into JSON)")
    alloc.add_argument("--season", type=int, required=True)
    alloc.add_argument("--matchday", type=int, required=True)
    alloc.add_argument("--type", choices=["episode", "sim", "promo", "news"], required=True)
    alloc.add_argument("--offset", type=int, default=0, help="Day offset relative to matchday (can be negative)")
    alloc.add_argument("--allow-future", action="store_true", help="Allow dates after world_today (planned content)")
    alloc.add_argument("--write", type=str, help="Path to a JSON file to update")
    alloc.add_argument("--field", type=str, default="inWorldDate", help="JSON field to write (default: inWorldDate)")
    alloc.add_argument("--dry-run", action="store_true", help="Do not write file, only show what would happen")
    alloc.set_defaults(func=cmd_alloc)

    table = sub.add_parser("table", help="Print matchday -> date table for a season")
    table.add_argument("--season", type=int, required=True)
    table.add_argument("--start", type=int, default=1)
    table.add_argument("--end", type=int, default=10)
    table.set_defaults(func=cmd_table)

    return p


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
