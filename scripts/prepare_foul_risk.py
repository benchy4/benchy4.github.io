import csv
import json
import random
from collections import defaultdict
from pathlib import Path
from player_identity import canonical_player

ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT.parent / "outputs/WNBL_Data_Collector/wnbl_dataset"
ENRICHED = DATASET / "analytics/play_by_play_enriched.csv"
PLAYER_GAMES = DATASET / "processed/player_game_stats.csv"
OUT = ROOT / "app/foul-risk.json"

WINDOWS = (30, 60, 120, 180, 240)
SIMULATIONS = 300
PRIOR_MINUTES = 400
QUICK_PRIOR_OPPORTUNITIES = 20


def number(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def minute_seconds(value):
    try:
        minutes, seconds = value.split(":")
        return int(minutes) * 60 + int(seconds)
    except (AttributeError, TypeError, ValueError):
        return 0


minutes = defaultdict(int)
games = defaultdict(set)
with PLAYER_GAMES.open(newline="", encoding="utf-8-sig") as handle:
    for row in csv.DictReader(handle):
        key = (row["season"], canonical_player(row["player"]))
        minutes[key] += minute_seconds(row["minutes"])
        games[key].add(row["game_id"])

foul_groups = defaultdict(list)
team_game_pools = defaultdict(list)
game_max_period = defaultdict(lambda: 4)
with ENRICHED.open(newline="", encoding="utf-8-sig") as handle:
    for row in csv.DictReader(handle):
        game_key = (row["season"], row["game_id"])
        game_max_period[game_key] = max(game_max_period[game_key], int(number(row["period_number"]) or 4))
        if row["action"] != "Personal Foul" or not row["player_name"] or not row["team"]:
            continue
        timestamp = int(number(row["game_seconds_elapsed"]))
        player_key = (row["season"], row["game_id"], row["team"], canonical_player(row["player_name"]))
        team_key = (row["season"], row["game_id"], row["team"])
        foul_groups[player_key].append(timestamp)
        team_game_pools[team_key].append(timestamp)

game_durations = {
    key: 2400 + max(0, periods - 4) * 300
    for key, periods in game_max_period.items()
}
for values in foul_groups.values():
    values.sort()
for values in team_game_pools.values():
    values.sort()

season_fouls = defaultdict(int)
season_minutes = defaultdict(int)
for (season, player), seconds in minutes.items():
    season_minutes[season] += seconds
for (season, game_id, team, player), timestamps in foul_groups.items():
    season_fouls[season] += len(timestamps)

league_fouls_per_40 = {
    season: fouls / (season_minutes[season] / 2400)
    for season, fouls in season_fouls.items()
    if season_minutes[season]
}

actual = defaultdict(lambda: defaultdict(lambda: {
    "first_to_second_n": 0,
    "first_to_second_opportunities": 0,
    "second_to_third_n": 0,
    "second_to_third_opportunities": 0,
    "first_to_third_n": 0,
    "first_to_third_opportunities": 0,
}))

for (season, game_id, team, player), timestamps in foul_groups.items():
    duration = game_durations[(season, game_id)]
    for window in WINDOWS:
        target = actual[(season, player)][window]
        if timestamps and duration - timestamps[0] >= window:
            target["first_to_second_opportunities"] += 1
            target["first_to_third_opportunities"] += 1
            target["first_to_second_n"] += int(
                len(timestamps) >= 2 and timestamps[1] - timestamps[0] <= window
            )
            target["first_to_third_n"] += int(
                len(timestamps) >= 3 and timestamps[2] - timestamps[0] <= window
            )
        if len(timestamps) >= 2 and duration - timestamps[1] >= window:
            target["second_to_third_opportunities"] += 1
            target["second_to_third_n"] += int(
                len(timestamps) >= 3 and timestamps[2] - timestamps[1] <= window
            )

rng = random.Random(20260724)
expected_counts = defaultdict(lambda: defaultdict(lambda: defaultdict(float)))

for _ in range(SIMULATIONS):
    for (season, game_id, team, player), observed in foul_groups.items():
        sampled = sorted(rng.sample(team_game_pools[(season, game_id, team)], len(observed)))
        duration = game_durations[(season, game_id)]
        for window in WINDOWS:
            target = expected_counts[(season, player)][window]
            if sampled and duration - sampled[0] >= window:
                target["first_to_second_opportunities"] += 1
                target["first_to_third_opportunities"] += 1
                target["first_to_second_n"] += int(
                    len(sampled) >= 2 and sampled[1] - sampled[0] <= window
                )
                target["first_to_third_n"] += int(
                    len(sampled) >= 3 and sampled[2] - sampled[0] <= window
                )
            if len(sampled) >= 2 and duration - sampled[1] >= window:
                target["second_to_third_opportunities"] += 1
                target["second_to_third_n"] += int(
                    len(sampled) >= 3 and sampled[2] - sampled[1] <= window
                )

league_quick = defaultdict(lambda: defaultdict(int))
for player_windows in actual.values():
    for window, values in player_windows.items():
        for key, value in values.items():
            league_quick[window][key] += value


def rate(numerator, denominator):
    return numerator / denominator if denominator else None


records = []
all_player_seasons = sorted(set(minutes) | {(key[0], key[3]) for key in foul_groups})
for season, player in all_player_seasons:
    seconds = minutes[(season, player)]
    actual_fouls = sum(
        len(timestamps)
        for (s, game_id, team, p), timestamps in foul_groups.items()
        if s == season and p == player
    )
    league_rate = league_fouls_per_40.get(season, 0)
    expected_fouls = league_rate * seconds / 2400
    actual_per_40 = actual_fouls / (seconds / 2400) if seconds else None
    stabilized_per_40 = (
        (actual_fouls + league_rate * PRIOR_MINUTES / 40)
        / ((seconds / 60 + PRIOR_MINUTES) / 40)
        if seconds
        else None
    )
    windows = []
    for window in WINDOWS:
        observed = actual[(season, player)][window]
        simulated = expected_counts[(season, player)][window]
        item = {"seconds": window}
        for sequence in ("first_to_second", "second_to_third", "first_to_third"):
            n_key = f"{sequence}_n"
            opp_key = f"{sequence}_opportunities"
            actual_rate = rate(observed[n_key], observed[opp_key])
            expected_rate = rate(simulated[n_key], simulated[opp_key])
            league_rate_quick = rate(
                league_quick[window][n_key],
                league_quick[window][opp_key],
            )
            stabilized_rate = None
            if actual_rate is not None and league_rate_quick is not None:
                stabilized_rate = (
                    observed[n_key] + league_rate_quick * QUICK_PRIOR_OPPORTUNITIES
                ) / (observed[opp_key] + QUICK_PRIOR_OPPORTUNITIES)
            item[sequence] = {
                "actual_n": observed[n_key],
                "opportunities": observed[opp_key],
                "actual_rate": actual_rate,
                "expected_rate": expected_rate,
                "actual_to_expected": (
                    actual_rate / expected_rate
                    if actual_rate is not None and expected_rate
                    else None
                ),
                "stabilized_rate": stabilized_rate,
            }
        windows.append(item)
    records.append({
        "season": season,
        "player_name": player,
        "games": len(games[(season, player)]),
        "minutes": seconds / 60,
        "actual_fouls": actual_fouls,
        "expected_fouls": expected_fouls,
        "actual_minus_expected": actual_fouls - expected_fouls,
        "actual_fouls_per_40": actual_per_40,
        "expected_fouls_per_40": league_rate,
        "actual_to_expected": actual_fouls / expected_fouls if expected_fouls else None,
        "stabilized_fouls_per_40": stabilized_per_40,
        "windows": windows,
    })

payload = {
    "meta": {
        "simulations": SIMULATIONS,
        "windows_seconds": WINDOWS,
        "overall_expected_definition": "Season league-average personal fouls per 40 minutes multiplied by the player's recorded minutes.",
        "quick_expected_definition": "Monte Carlo expectation preserving each player-game foul count and sampling from that team-game's observed foul timestamps.",
        "censoring": "An opportunity is included only when the full time window remained in the game.",
        "stabilization": {
            "overall_prior_minutes": PRIOR_MINUTES,
            "quick_prior_opportunities": QUICK_PRIOR_OPPORTUNITIES,
        },
    },
    "league_fouls_per_40": league_fouls_per_40,
    "records": records,
}
OUT.write_text(json.dumps(payload, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
print(f"Wrote {len(records)} player-season foul-risk records to {OUT}")
