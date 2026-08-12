import csv
import json
from collections import defaultdict
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT.parent / "outputs/WNBL_Data_Collector/wnbl_dataset"


def minutes_seconds(value):
    try:
        minutes, seconds = str(value).split(":", 1)
        return int(minutes) * 60 + int(seconds)
    except (TypeError, ValueError):
        return 0


def mean(values):
    values = [value for value in values if value is not None]
    return sum(values) / len(values) if values else None


def quantile(values, probability):
    ordered = sorted(values)
    if not ordered:
        return None
    position = (len(ordered) - 1) * probability
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    weight = position - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def round_value(value, places=4):
    return None if value is None else round(value, places)


games = {}
with (DATA / "processed/games.csv").open(newline="", encoding="utf-8-sig") as handle:
    for row in csv.DictReader(handle):
        games[(row["season"], row["game_id"])] = row

periods = defaultdict(int)
quarter = defaultdict(lambda: {"off_poss": 0, "off_points": 0, "def_poss": 0, "def_points": 0})
with (DATA / "analytics/possessions.csv").open(newline="", encoding="utf-8-sig") as handle:
    for row in csv.DictReader(handle):
        game_key = (row["season"], row["game_id"])
        period = int(row["period_number"])
        periods[game_key] = max(periods[game_key], period)
        if period != 4:
            continue
        points = int(float(row["points"] or 0))
        synergy_possessions = float(row.get("synergy_play_possessions") or 0)
        offense_key = (*game_key, row["offense_team"])
        defense_key = (*game_key, row["defense_team"])
        quarter[offense_key]["off_poss"] += synergy_possessions
        quarter[offense_key]["off_points"] += points
        quarter[defense_key]["def_poss"] += synergy_possessions
        quarter[defense_key]["def_points"] += points

player_minutes = defaultdict(list)
with (DATA / "processed/player_game_stats.csv").open(newline="", encoding="utf-8-sig") as handle:
    for row in csv.DictReader(handle):
        seconds = minutes_seconds(row["minutes"])
        player_minutes[(row["season"], row["game_id"], row["team"])].append(
            {"player": row["player"], "seconds": seconds}
        )

team_dates = defaultdict(list)
for (season, game_id), game in games.items():
    for team in (game["team_1"], game["team_2"]):
        team_dates[(season, team)].append((date.fromisoformat(game["game_date"]), game_id))

rest_days = {}
for key, dates in team_dates.items():
    previous = None
    for game_date, game_id in sorted(dates):
        rest_days[(*key, game_id)] = None if previous is None else (game_date - previous).days
        previous = game_date

rows = []
excluded_coverage = 0
for (season, game_id, team), roster in player_minutes.items():
    game = games.get((season, game_id))
    if not game:
        continue
    max_period = max(4, periods.get((season, game_id), 4))
    expected_seconds = (40 + 5 * (max_period - 4)) * 5 * 60
    actual_seconds = sum(player["seconds"] for player in roster)
    coverage = actual_seconds / expected_seconds if expected_seconds else 0
    if not 0.97 <= coverage <= 1.03:
        excluded_coverage += 1
        continue
    ordered = sorted((player["seconds"] for player in roster if player["seconds"] > 0), reverse=True)
    if len(ordered) < 5 or actual_seconds <= 0:
        continue
    is_team_1 = team == game["team_1"]
    score_for = int(game["score_1"] if is_team_1 else game["score_2"])
    score_against = int(game["score_2"] if is_team_1 else game["score_1"])
    q4 = quarter[season, game_id, team]
    q4_off_ppp = q4["off_points"] / q4["off_poss"] if q4["off_poss"] else None
    q4_def_ppp = q4["def_points"] / q4["def_poss"] if q4["def_poss"] else None
    rows.append(
        {
            "season": season,
            "game_id": game_id,
            "game_date": game["game_date"],
            "team": team,
            "opponent": game["team_2"] if is_team_1 else game["team_1"],
            "won": score_for > score_against,
            "margin": score_for - score_against,
            "overtime": max_period > 4,
            "minutes_coverage": coverage,
            "players_used": len(ordered),
            "top5_share": sum(ordered[:5]) / actual_seconds,
            "top7_share": sum(ordered[:7]) / actual_seconds,
            "top9_share": sum(ordered[:9]) / actual_seconds,
            "rotation_hhi": sum((seconds / actual_seconds) ** 2 for seconds in ordered),
            "rest_days": rest_days.get((season, team, game_id)),
            "q4_off_poss": q4["off_poss"],
            "q4_off_ppp": q4_off_ppp,
            "q4_def_ppp": q4_def_ppp,
            "q4_net_ppp": None if q4_off_ppp is None or q4_def_ppp is None else q4_off_ppp - q4_def_ppp,
        }
    )

cutoffs = [quantile([row["top5_share"] for row in rows], value) for value in (0.25, 0.5, 0.75)]


def band_for(value):
    if value <= cutoffs[0]:
        return "Spread"
    if value <= cutoffs[1]:
        return "Balanced"
    if value <= cutoffs[2]:
        return "Tight"
    return "Very tight"


for row in rows:
    row["band"] = band_for(row["top5_share"])


def summarize(sample, label):
    return {
        "label": label,
        "team_games": len(sample),
        "win_percentage": round_value(mean([int(row["won"]) for row in sample])),
        "average_margin": round_value(mean([row["margin"] for row in sample])),
        "average_top5_share": round_value(mean([row["top5_share"] for row in sample])),
        "average_top7_share": round_value(mean([row["top7_share"] for row in sample])),
        "average_players_used": round_value(mean([row["players_used"] for row in sample])),
        "q4_off_ppp": round_value(mean([row["q4_off_ppp"] for row in sample])),
        "q4_def_ppp": round_value(mean([row["q4_def_ppp"] for row in sample])),
        "q4_net_ppp": round_value(mean([row["q4_net_ppp"] for row in sample])),
    }


band_order = ["Spread", "Balanced", "Tight", "Very tight"]
bands = [summarize([row for row in rows if row["band"] == band], band) for band in band_order]
close_bands = [
    summarize([row for row in rows if row["band"] == band and abs(row["margin"]) <= 10], band)
    for band in band_order
]

team_season_groups = defaultdict(list)
for row in rows:
    team_season_groups[(row["season"], row["team"])].append(row)

team_seasons = []
for (season, team), sample in sorted(team_season_groups.items()):
    summary = summarize(sample, team)
    summary.update({"season": season, "team": team})
    team_seasons.append(summary)

season_groups = defaultdict(list)
for row in rows:
    season_groups[row["season"]].append(row)
seasons = []
for season, sample in sorted(season_groups.items()):
    summary = summarize(sample, season)
    summary["season"] = season
    seasons.append(summary)


def two_variable_within_team_season(outcome):
    centered = []
    for sample in team_season_groups.values():
        usable = [row for row in sample if row[outcome] is not None]
        if len(usable) < 2:
            continue
        x_mean = mean([row["top5_share"] for row in usable])
        rest_mean = mean([min(row["rest_days"], 7) for row in usable if row["rest_days"] is not None])
        y_mean = mean([row[outcome] for row in usable])
        for row in usable:
            if row["rest_days"] is None or rest_mean is None:
                continue
            centered.append(
                (
                    row["top5_share"] - x_mean,
                    min(row["rest_days"], 7) - rest_mean,
                    row[outcome] - y_mean,
                )
            )
    xx = sum(x * x for x, _, _ in centered)
    rr = sum(r * r for _, r, _ in centered)
    xr = sum(x * r for x, r, _ in centered)
    xy = sum(x * y for x, _, y in centered)
    ry = sum(r * y for _, r, y in centered)
    determinant = xx * rr - xr * xr
    coefficient = None if abs(determinant) < 1e-12 else (xy * rr - ry * xr) / determinant
    return {
        "observations": len(centered),
        "per_5pp_top5_share": round_value(coefficient * 0.05 if coefficient is not None else None),
    }


rest_groups = []
for label, test in (
    ("0–1 days", lambda value: value is not None and value <= 1),
    ("2 days", lambda value: value == 2),
    ("3+ days", lambda value: value is not None and value >= 3),
):
    for compression in ("Spread / balanced", "Tight / very tight"):
        wanted = {"Spread", "Balanced"} if compression.startswith("Spread") else {"Tight", "Very tight"}
        sample = [row for row in rows if test(row["rest_days"]) and row["band"] in wanted]
        summary = summarize(sample, compression)
        summary.update({"rest_band": label, "compression": compression})
        rest_groups.append(summary)

output = {
    "meta": {
        "team_games": len(rows),
        "games": len({row["game_id"] for row in rows}),
        "seasons": sorted({row["season"] for row in rows}),
        "excluded_for_minutes_coverage": excluded_coverage,
        "median_top5_share": round_value(quantile([row["top5_share"] for row in rows], 0.5)),
        "median_players_used": round_value(quantile([row["players_used"] for row in rows], 0.5)),
        "band_cutoffs": {
            "spread_max": round_value(cutoffs[0]),
            "balanced_max": round_value(cutoffs[1]),
            "tight_max": round_value(cutoffs[2]),
        },
        "definition": "Top-five minute share is the share of a team's recorded player-minutes used by its five highest-minute players in that game.",
    },
    "bands": bands,
    "close_game_bands": close_bands,
    "rest_groups": rest_groups,
    "seasons": seasons,
    "team_seasons": team_seasons,
    "team_games": [
        {
            key: round_value(value) if isinstance(value, float) else value
            for key, value in row.items()
            if key
            in {
                "season",
                "game_id",
                "game_date",
                "team",
                "opponent",
                "won",
                "margin",
                "overtime",
                "players_used",
                "top5_share",
                "top7_share",
                "top9_share",
                "rotation_hhi",
                "rest_days",
                "q4_off_ppp",
                "q4_def_ppp",
                "q4_net_ppp",
                "band",
            }
        }
        for row in rows
    ],
    "associations": {
        "margin": two_variable_within_team_season("margin"),
        "q4_net_ppp": two_variable_within_team_season("q4_net_ppp"),
    },
}

(ROOT / "app/rotation-compression.json").write_text(
    json.dumps(output, separators=(",", ":"), ensure_ascii=False), encoding="utf-8"
)
print(json.dumps(output["meta"], indent=2))
print(json.dumps(output["associations"], indent=2))
