import csv
import json
from collections import defaultdict
from pathlib import Path

from player_identity import canonical_player


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT.parent / "outputs/WNBL_Data_Collector/wnbl_dataset"
PROCESSED = DATA / "processed"
ANALYTICS = DATA / "analytics"

BOX_FIELDS = (
    "points", "fg_made", "fg_attempted", "three_made", "three_attempted",
    "ft_made", "ft_attempted", "rebounds", "offensive_rebounds",
    "defensive_rebounds", "assists", "steals", "turnovers", "blocks", "fouls",
)


def number(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def minutes(value):
    try:
        minute, second = value.split(":")
        return int(minute) + int(second) / 60
    except (AttributeError, ValueError):
        return 0.0


def divide(numerator, denominator, fallback=0.0):
    return numerator / denominator if denominator else fallback


def short_team(name):
    if name == "University of Canberra Capitals":
        return "UC Capitals"
    if name == "Southside Melbourne Flyers":
        return "Southside Flyers"
    return name.split()[0] if name else name


def team_possessions(team, opponent):
    """Synergy-style team play possessions: FGA + 0.44*FTA + TOV."""
    del opponent
    return team["fg_attempted"] + 0.44 * team["ft_attempted"] + team["turnovers"]


def scoring_possessions(fgm, ftm, fta):
    ft_part = (1 - (1 - divide(ftm, fta)) ** 2) * 0.4 * fta if fta else 0.0
    return fgm + ft_part


games = {}
with (PROCESSED / "games.csv").open(newline="", encoding="utf-8-sig") as source:
    for row in csv.DictReader(source):
        games[row["game_id"]] = row

team_games = defaultdict(set)
team_box = defaultdict(lambda: {field: 0.0 for field in BOX_FIELDS})
player_box = defaultdict(lambda: {field: 0.0 for field in BOX_FIELDS})
player_games = defaultdict(set)
player_minutes = defaultdict(float)

with (PROCESSED / "player_game_stats.csv").open(newline="", encoding="utf-8-sig") as source:
    for row in csv.DictReader(source):
        season = row["season"]
        team = row["team"]
        player = canonical_player(row["player"])
        team_key = (season, team)
        player_key = (season, team, player)
        team_games[team_key].add(row["game_id"])
        player_games[player_key].add(row["game_id"])
        player_minutes[player_key] += minutes(row["minutes"])
        for field in BOX_FIELDS:
            value = number(row[field])
            team_box[team_key][field] += value
            player_box[player_key][field] += value

team_scores = defaultdict(lambda: {"points": 0.0, "points_allowed": 0.0, "wins": 0})
for (season, team), game_ids in team_games.items():
    for game_id in game_ids:
        game = games[game_id]
        first = team == game["team_1"]
        scored = number(game["score_1"] if first else game["score_2"])
        allowed = number(game["score_2"] if first else game["score_1"])
        team_scores[(season, team)]["points"] += scored
        team_scores[(season, team)]["points_allowed"] += allowed
        team_scores[(season, team)]["wins"] += int(scored > allowed)

team_opponent = {}
for season, team in team_box:
    for game_id in team_games[(season, team)]:
        game = games[game_id]
        opponent_name = game["team_2"] if team == game["team_1"] else game["team_1"]
        # Team-season opponent totals are assembled from the already reconciled team-game boxes.
        # Cache those boxes on first use below to avoid using schedule averages as a substitute.
        team_opponent[(season, team, game_id)] = opponent_name

team_game_box = defaultdict(lambda: {field: 0.0 for field in BOX_FIELDS})
with (PROCESSED / "player_game_stats.csv").open(newline="", encoding="utf-8-sig") as source:
    for row in csv.DictReader(source):
        key = (row["game_id"], row["team"])
        for field in BOX_FIELDS:
            team_game_box[key][field] += number(row[field])

opponent_box = defaultdict(lambda: {field: 0.0 for field in BOX_FIELDS})
for season, team in team_box:
    for game_id in team_games[(season, team)]:
        opponent_name = team_opponent[(season, team, game_id)]
        for field in BOX_FIELDS:
            opponent_box[(season, team)][field] += team_game_box[(game_id, opponent_name)][field]

on_off = {}
with (PROCESSED / "player_same_game_on_off.csv").open(newline="", encoding="utf-8-sig") as source:
    for row in csv.DictReader(source):
        on_off[(row["season"], row["team"], canonical_player(row["player"]))] = {
            key: number(row[key]) for key in ("team_relative_plus_minus_per_40", "on_off_plus_minus_per_40")
        }

defense_data = json.loads((ROOT / "app/defense.json").read_text(encoding="utf-8"))
defense = {
    (str(row["season"]), row["team"], canonical_player(row["player_name"])): row
    for row in defense_data["player_seasons"]
}

team_context = {}
season_context = defaultdict(lambda: {"points": 0.0, "possessions": 0.0, "games": 0, "pace_games": 0.0})
for key, box in team_box.items():
    season, team = key
    opponent = opponent_box[key]
    possessions = team_possessions(box, opponent)
    team_minutes = sum(player_minutes[player_key] for player_key in player_minutes if player_key[:2] == key)
    games_played = len(team_games[key])
    pace_games = team_minutes / 200 if team_minutes else games_played
    pace = divide(possessions, pace_games)
    team_context[key] = {
        "possessions": possessions,
        "team_minutes": team_minutes,
        "games": games_played,
        "pace": pace,
        **team_scores[key],
    }
    season_context[season]["points"] += team_scores[key]["points"]
    season_context[season]["possessions"] += possessions
    season_context[season]["games"] += games_played
    season_context[season]["pace_games"] += pace_games

for season, context in season_context.items():
    context["points_per_game"] = divide(context["points"], context["games"])
    context["points_per_possession"] = divide(context["points"], context["possessions"])
    context["pace"] = divide(context["possessions"], context["pace_games"])

records = []
for player_key, player in player_box.items():
    season, team, player_name = player_key
    team_key = (season, team)
    club = team_box[team_key]
    opponent = opponent_box[team_key]
    context = team_context[team_key]
    league = season_context[season]
    mp = player_minutes[player_key]
    team_mp = context["team_minutes"]
    minute_share = divide(mp, team_mp / 5)

    qast_first = minute_share * 1.14 * divide(club["assists"] - player["assists"], club["fg_made"])
    qast_numerator = divide(club["assists"], team_mp) * mp * 5 - player["assists"]
    qast_denominator = divide(club["fg_made"], team_mp) * mp * 5 - player["fg_made"]
    qast = qast_first + divide(qast_numerator, qast_denominator) * (1 - minute_share)
    qast = min(1.0, max(0.0, qast))

    player_ft_part = (
        (1 - (1 - divide(player["ft_made"], player["ft_attempted"])) ** 2)
        * 0.4 * player["ft_attempted"]
        if player["ft_attempted"] else 0.0
    )
    team_scoring_poss = scoring_possessions(club["fg_made"], club["ft_made"], club["ft_attempted"])
    team_orb_rate = divide(
        club["offensive_rebounds"],
        club["offensive_rebounds"] + opponent["defensive_rebounds"],
    )
    team_play_rate = divide(
        team_scoring_poss,
        club["fg_attempted"] + 0.4 * club["ft_attempted"] + club["turnovers"],
    )
    team_orb_weight = divide(
        (1 - team_orb_rate) * team_play_rate,
        (1 - team_orb_rate) * team_play_rate + team_orb_rate * (1 - team_play_rate),
    )
    fg_part = player["fg_made"] * (
        1 - 0.5 * divide(player["points"] - player["ft_made"], 2 * player["fg_attempted"]) * qast
    )
    ast_part = 0.5 * divide(
        (club["points"] - club["ft_made"]) - (player["points"] - player["ft_made"]),
        2 * (club["fg_attempted"] - player["fg_attempted"]),
    ) * player["assists"]
    orb_part = player["offensive_rebounds"] * team_orb_weight * team_play_rate
    scoring_poss = (fg_part + ast_part + player_ft_part) * (
        1 - divide(club["offensive_rebounds"], team_scoring_poss) * team_orb_weight * team_play_rate
    ) + orb_part
    missed_fg_poss = (player["fg_attempted"] - player["fg_made"]) * (1 - 1.07 * team_orb_rate)
    missed_ft_poss = (
        (1 - divide(player["ft_made"], player["ft_attempted"])) ** 2
        * 0.4 * player["ft_attempted"]
        if player["ft_attempted"] else 0.0
    )
    # Keep player ratings on the same Synergy-style play denominator used everywhere else.
    offensive_possessions = player["fg_attempted"] + 0.44 * player["ft_attempted"] + player["turnovers"]

    produced_fg = 2 * (player["fg_made"] + 0.5 * player["three_made"]) * (
        1 - 0.5 * divide(player["points"] - player["ft_made"], 2 * player["fg_attempted"]) * qast
    )
    produced_ast = (
        2
        * divide(
            club["fg_made"] - player["fg_made"] + 0.5 * (club["three_made"] - player["three_made"]),
            club["fg_made"] - player["fg_made"],
        )
        * 0.5
        * divide(
            (club["points"] - club["ft_made"]) - (player["points"] - player["ft_made"]),
            2 * (club["fg_attempted"] - player["fg_attempted"]),
        )
        * player["assists"]
    )
    produced_orb = (
        player["offensive_rebounds"] * team_orb_weight * team_play_rate
        * divide(club["points"], team_scoring_poss)
    )
    points_produced = (produced_fg + produced_ast + player["ft_made"]) * (
        1 - divide(club["offensive_rebounds"], team_scoring_poss) * team_orb_weight * team_play_rate
    ) + produced_orb
    offensive_rating = 100 * divide(points_produced, offensive_possessions)

    defensive_orb_rate = divide(
        opponent["offensive_rebounds"],
        opponent["offensive_rebounds"] + club["defensive_rebounds"],
    )
    defensive_fg_rate = divide(opponent["fg_made"], opponent["fg_attempted"])
    field_miss_weight = divide(
        defensive_fg_rate * (1 - defensive_orb_rate),
        defensive_fg_rate * (1 - defensive_orb_rate) + (1 - defensive_fg_rate) * defensive_orb_rate,
    )
    stops_one = (
        player["steals"]
        + player["blocks"] * field_miss_weight * (1 - 1.07 * defensive_orb_rate)
        + player["defensive_rebounds"] * (1 - field_miss_weight)
    )
    stops_two = (
        (
            divide(opponent["fg_attempted"] - opponent["fg_made"] - club["blocks"], team_mp)
            * field_miss_weight * (1 - 1.07 * defensive_orb_rate)
            + divide(opponent["turnovers"] - club["steals"], team_mp)
        ) * mp
        + divide(player["fouls"], club["fouls"])
        * 0.4 * opponent["ft_attempted"]
        * (1 - divide(opponent["ft_made"], opponent["ft_attempted"])) ** 2
    )
    stops = stops_one + stops_two
    stop_percentage = min(1.0, max(0.0, divide(stops * team_mp, context["possessions"] * mp)))
    team_defensive_rating = 100 * divide(context["points_allowed"], context["possessions"])
    defensive_points_per_scoring_possession = divide(
        context["points_allowed"],
        scoring_possessions(opponent["fg_made"], opponent["ft_made"], opponent["ft_attempted"]),
    )
    defensive_rating = team_defensive_rating + 0.2 * (
        100 * defensive_points_per_scoring_possession * (1 - stop_percentage) - team_defensive_rating
    )

    marginal_points_per_win = (
        0.32 * league["points_per_game"] * divide(context["pace"], league["pace"], 1.0)
    )
    marginal_offense = points_produced - 0.92 * league["points_per_possession"] * offensive_possessions
    marginal_defense = divide(mp, team_mp) * context["possessions"] * (
        1.08 * league["points_per_possession"] - defensive_rating / 100
    )
    offensive_win_shares = divide(marginal_offense, marginal_points_per_win)
    defensive_win_shares = divide(marginal_defense, marginal_points_per_win)
    win_shares = offensive_win_shares + defensive_win_shares

    short = short_team(team)
    same_game = on_off.get((season, short, player_name), {})
    defense_row = defense.get((season, short, player_name), {})
    pm_rate = number(same_game.get("team_relative_plus_minus_per_40"))
    pm_signal_points = pm_rate * (mp / 40) * divide(mp, mp + 400)
    defense_signal_points = (
        number(defense_row.get("stabilized_points_saved_per_100"))
        * number(defense_row.get("opportunities")) / 100
    )
    raw_adjustment_points = 0.25 * pm_signal_points + 0.25 * defense_signal_points

    records.append({
        "season": season,
        "team": short,
        "player": player_name,
        "games": len(player_games[player_key]),
        "minutes": mp,
        "offensive_rating": offensive_rating,
        "defensive_rating": defensive_rating,
        "offensive_possessions": offensive_possessions,
        "points_produced": points_produced,
        "marginal_points_per_win": marginal_points_per_win,
        "offensive_win_shares": offensive_win_shares,
        "defensive_win_shares": defensive_win_shares,
        "win_shares": win_shares,
        "win_shares_per_40": divide(win_shares, mp / 40),
        "raw_adjustment_points": raw_adjustment_points,
        "plus_minus_adjustment_points": 0.25 * pm_signal_points,
        "matchup_defense_adjustment_points": 0.25 * defense_signal_points,
    })

by_team = defaultdict(list)
for row in records:
    by_team[(row["season"], row["team"])].append(row)

reconciliation = []
for (season, team), rows in by_team.items():
    traditional_total = sum(row["win_shares"] for row in rows)
    raw_total = sum(row["raw_adjustment_points"] for row in rows)
    minute_total = sum(row["minutes"] for row in rows)
    for row in rows:
        centered_points = row["raw_adjustment_points"] - raw_total * divide(row["minutes"], minute_total)
        row["adjustment_win_shares"] = divide(centered_points, row["marginal_points_per_win"])
        row["adjusted_win_shares"] = row["win_shares"] + row["adjustment_win_shares"]
        row["adjusted_win_shares_per_40"] = divide(row["adjusted_win_shares"], row["minutes"] / 40)
        row["team_win_share"] = divide(row["win_shares"], traditional_total)
        row["adjusted_team_win_share"] = divide(row["adjusted_win_shares"], traditional_total)
    adjusted_total = sum(row["adjusted_win_shares"] for row in rows)
    full_team = next(key[1] for key in team_context if key[0] == season and short_team(key[1]) == team)
    wins = team_context[(season, full_team)]["wins"]
    reconciliation.append({
        "season": season,
        "team": team,
        "wins": wins,
        "player_win_shares": traditional_total,
        "adjusted_player_win_shares": adjusted_total,
        "difference_from_wins": traditional_total - wins,
        "adjusted_minus_traditional": adjusted_total - traditional_total,
    })

fieldnames = [
    "season", "team", "player", "games", "minutes", "offensive_rating", "defensive_rating",
    "offensive_possessions", "points_produced", "marginal_points_per_win",
    "offensive_win_shares", "defensive_win_shares", "win_shares", "win_shares_per_40",
    "team_win_share", "plus_minus_adjustment_points", "matchup_defense_adjustment_points",
    "adjustment_win_shares", "adjusted_win_shares", "adjusted_win_shares_per_40",
    "adjusted_team_win_share",
]
with (PROCESSED / "player_win_shares.csv").open("w", newline="", encoding="utf-8") as output:
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    for row in sorted(records, key=lambda item: (item["season"], item["team"], item["player"])):
        writer.writerow({key: row.get(key) for key in fieldnames})

result = {
    "meta": {
        "method": "Basketball-Reference Win Shares structure calibrated to each WNBL season",
        "adjusted_method": "Traditional Win Shares plus centered, reliability-weighted same-game plus/minus and matchup-defence signals",
        "player_seasons": len(records),
        "team_seasons": len(reconciliation),
        "adjusted_team_total_rule": "Adjusted player Win Shares sum to the same team total as traditional Win Shares.",
    },
    "records": [{key: row.get(key) for key in fieldnames} for row in records],
    "reconciliation": reconciliation,
}
(ROOT / "app/win-shares.json").write_text(
    json.dumps(result, separators=(",", ":"), ensure_ascii=False), encoding="utf-8"
)

mean_absolute_difference = divide(
    sum(abs(row["difference_from_wins"]) for row in reconciliation), len(reconciliation)
)
max_adjusted_drift = max(abs(row["adjusted_minus_traditional"]) for row in reconciliation)
print({
    "player_seasons": len(records),
    "team_seasons": len(reconciliation),
    "traditional_team_win_mae": round(mean_absolute_difference, 3),
    "max_adjusted_team_drift": max_adjusted_drift,
})
