import csv
import json
import math
from collections import defaultdict
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT.parent / "outputs/WNBL_Data_Collector/wnbl_dataset/analytics/winning_thresholds"
SEASONS = sorted({r["season"] for r in csv.DictReader((BASE / "team_game_metrics.csv").open(encoding="utf-8-sig"))})
TARGET_WIN_RATE = 0.70
CALIBRATION_FLOOR = 0.65
MAX_CALIBRATION_GAP = 0.08
RNG = np.random.default_rng(409)
DOMAIN_MINIMUMS = {
    "net_rating": 0,
    "fga_plus_fta_margin": 0,
    "turnover_margin": 0,
    "rebound_margin": 0,
}

CONFIGS = {
    "points": ("Points scored", "at_least", 5), "points_allowed": ("Points allowed", "at_most", 5),
    "offensive_rating": ("Offensive rating", "at_least", 5), "defensive_rating": ("Defensive rating", "at_most", 5), "net_rating": ("Net rating", "at_least", 5),
    "fg_pct": ("FG%", "at_least", .025), "two_pct": ("2P%", "at_least", .025), "three_pct": ("3P%", "at_least", .025), "ft_pct": ("FT%", "at_least", .025),
    "efg_pct": ("eFG%", "at_least", .025), "free_throw_rate": ("Free throw rate (FTA/FGA)", "at_least", .05),
    "three_made": ("3PM", "at_least", 1), "three_attempted": ("3PA", "at_least", 2), "fga_plus_fta": ("FGA + FTA", "at_least", 5),
    "fga_plus_fta_margin": ("FGA + FTA differential", "at_least", 5), "possessions": ("Possessions", "at_least", 5),
    "assists": ("Assists", "at_least", 2), "turnovers": ("Turnovers", "at_most", 2), "turnover_rate": ("Turnover rate", "at_most", .02),
    "assist_turnover_ratio": ("Assist/turnover ratio", "at_least", .25), "turnover_margin": ("Turnover margin", "at_least", 2),
    "offensive_rebound_pct": ("Offensive rebound %", "at_least", .025), "defensive_rebound_pct": ("Defensive rebound %", "at_least", .025),
    "rebound_margin": ("Rebound margin", "at_least", 2), "steals": ("Steals", "at_least", 1),
    "live_ball_turnovers_forced": ("Live-ball turnovers forced", "at_least", 1), "kills": ("Kills", "at_least", 1),
}


def number(value):
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def read_rows():
    rows = []
    with (BASE / "team_game_metrics.csv").open(encoding="utf-8", newline="") as source:
        for raw in csv.DictReader(source):
            row = dict(raw)
            row["won"] = int(float(row["won"]))
            for metric in CONFIGS:
                row[metric] = number(row.get(metric))
            rows.append(row)
    return rows


def write_csv(name, rows):
    if not rows:
        return
    with (BASE / name).open("w", encoding="utf-8", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def candidates(rows, metric, step):
    values = sorted(row[metric] for row in rows if row[metric] is not None)
    low = values[int(.10 * (len(values) - 1))]
    high = values[int(.90 * (len(values) - 1))]
    start = math.ceil(max(low, DOMAIN_MINIMUMS.get(metric, low)) / step) * step
    end = math.floor(high / step) * step
    out, value = [], start
    while value <= end + step / 100:
        out.append(round(value, 6))
        value += step
    return out


def transformed(row, metric, direction):
    value = row[metric]
    return value if direction == "at_least" else -value


def fit_isotonic(rows, metric, direction):
    pairs = sorted((transformed(row, metric, direction), row["won"]) for row in rows if row[metric] is not None)
    grouped = []
    for x, y in pairs:
        if grouped and grouped[-1]["x"] == x:
            grouped[-1]["sum"] += y
            grouped[-1]["weight"] += 1
        else:
            grouped.append({"x": x, "sum": y, "weight": 1})
    blocks = []
    for point in grouped:
        blocks.append({"lo": point["x"], "hi": point["x"], "sum": point["sum"], "weight": point["weight"]})
        while len(blocks) > 1 and blocks[-2]["sum"] / blocks[-2]["weight"] > blocks[-1]["sum"] / blocks[-1]["weight"]:
            right = blocks.pop()
            left = blocks.pop()
            blocks.append({"lo": left["lo"], "hi": right["hi"], "sum": left["sum"] + right["sum"], "weight": left["weight"] + right["weight"]})
    centers = np.array([(block["lo"] + block["hi"]) / 2 for block in blocks], dtype=float)
    rates = np.array([block["sum"] / block["weight"] for block in blocks], dtype=float)
    return centers, rates


def predict(model, value, direction):
    centers, rates = model
    x = value if direction == "at_least" else -value
    return float(np.interp(x, centers, rates, left=rates[0], right=rates[-1]))


def meets(value, threshold, direction):
    return value >= threshold if direction == "at_least" else value <= threshold


def cluster_interval(rows, iterations=800):
    by_game = defaultdict(lambda: [0, 0])
    for row in rows:
        by_game[row["game_id"]][0] += row["won"]
        by_game[row["game_id"]][1] += 1
    values = np.array(list(by_game.values()), dtype=float)
    if not len(values):
        return None, None
    draws = RNG.integers(0, len(values), size=(iterations, len(values)))
    sampled = values[draws]
    rates = sampled[:, :, 0].sum(axis=1) / sampled[:, :, 1].sum(axis=1)
    return float(np.quantile(rates, .025)), float(np.quantile(rates, .975))


def p_value(wins, total):
    if not total:
        return 1.0
    z = abs((wins / total - .5) / math.sqrt(.25 / total))
    return math.erfc(z / math.sqrt(2))


def add_q_values(rows):
    ordered = sorted(enumerate(rows), key=lambda item: item[1]["p_value"])
    count, running, q_values = len(rows), 1.0, [1.0] * len(rows)
    for rank, (index, row) in reversed(list(enumerate(ordered, 1))):
        running = min(running, row["p_value"] * count / rank)
        q_values[index] = running
    for row, q_value in zip(rows, q_values):
        row["q_value"] = q_value


team_games = read_rows()
evaluation_seasons = SEASONS[2:]
results, selected, oof_by_metric = [], [], {}

for metric, (label, direction, step) in CONFIGS.items():
    metric_rows = [row for row in team_games if row[metric] is not None]
    oof = []
    for test_index in range(2, len(SEASONS)):
        train_seasons = set(SEASONS[:test_index])
        test_season = SEASONS[test_index]
        train = [row for row in metric_rows if row["season"] in train_seasons]
        test = [row for row in metric_rows if row["season"] == test_season]
        model = fit_isotonic(train, metric, direction)
        for row in test:
            oof.append({**row, "model_wp": predict(model, row[metric], direction), "fold": test_season})
    oof_by_metric[metric] = oof
    final_model = fit_isotonic(metric_rows, metric, direction)
    candidate_rows = []
    for threshold in candidates(metric_rows, metric, step):
        full = [row for row in metric_rows if meets(row[metric], threshold, direction)]
        validation = [row for row in oof if meets(row[metric], threshold, direction)]
        wins = sum(row["won"] for row in full)
        validation_wins = sum(row["won"] for row in validation)
        represented = []
        season_rates = []
        for season in evaluation_seasons:
            season_rows = [row for row in validation if row["season"] == season]
            if len(season_rows) >= 10:
                represented.append(season)
                season_rates.append(sum(row["won"] for row in season_rows) / len(season_rows))
        ci_low, ci_high = cluster_interval(validation)
        model_at_cutoff = float(np.mean([predict(final_model, row[metric], direction) for row in full])) if full else None
        row = {
            "metric": metric, "metric_label": label, "direction": direction, "threshold": threshold,
            "team_games": len(full), "wins": wins, "win_rate": wins / len(full) if full else None,
            "validation_n": len(validation), "validation_win_rate": validation_wins / len(validation) if validation else None,
            "validation_ci_low": ci_low, "validation_ci_high": ci_high,
            "model_win_probability": model_at_cutoff,
            "rolling_model_win_rate": float(np.mean([item["model_wp"] for item in validation])) if validation else None,
            "rolling_brier": float(np.mean([(item["model_wp"] - item["won"]) ** 2 for item in oof])) if oof else None,
            "rolling_folds": len(evaluation_seasons), "validation_seasons": " | ".join(evaluation_seasons),
            "seasons_with_10_plus": len(represented), "season_min_win_rate": min(season_rates) if season_rates else None,
            "season_max_win_rate": max(season_rates) if season_rates else None,
            "win_rate_lift": validation_wins / len(validation) - .5 if validation else None,
            "p_value": p_value(validation_wins, len(validation)),
        }
        candidate_rows.append(row)
        results.append(row)
    eligible = [row for row in candidate_rows if row["validation_n"] >= 40 and row["seasons_with_10_plus"] >= 3]
    strict_order = sorted(eligible, key=lambda row: row["threshold"], reverse=direction == "at_most")
    best = next((row for row in strict_order if row["rolling_model_win_rate"] >= TARGET_WIN_RATE and row["model_win_probability"] >= TARGET_WIN_RATE and row["validation_win_rate"] >= CALIBRATION_FLOOR and abs(row["rolling_model_win_rate"] - row["validation_win_rate"]) <= MAX_CALIBRATION_GAP), None)
    target_reached = best is not None
    if best is None and eligible:
        best = max(eligible, key=lambda row: (row["rolling_model_win_rate"], row["validation_n"]))
    if best:
        picked = dict(best)
        picked["selection_target"] = TARGET_WIN_RATE
        picked["selection_target_reached"] = target_reached
        picked["validation_pass"] = bool(target_reached and picked["validation_win_rate"] > .5 and picked["validation_ci_low"] is not None and picked["validation_ci_low"] > .5)
        selected.append(picked)

add_q_values(results)
selected_map = {row["metric"]: row for row in selected if row["selection_target_reached"]}
selected = [{**row, "q_value": next(item["q_value"] for item in results if item["metric"] == row["metric"] and item["threshold"] == row["threshold"])} for row in selected]

actionable = ["fg_pct", "two_pct", "three_pct", "efg_pct", "free_throw_rate", "three_attempted", "fga_plus_fta", "fga_plus_fta_margin", "possessions", "turnovers", "turnover_rate", "assist_turnover_ratio", "turnover_margin", "offensive_rebound_pct", "defensive_rebound_pct", "rebound_margin", "steals", "live_ball_turnovers_forced", "kills"]
pairs = []
evaluation_rows = [row for row in team_games if row["season"] in evaluation_seasons]
for index, first_metric in enumerate(actionable):
    first = selected_map.get(first_metric)
    if not first:
        continue
    for second_metric in actionable[index + 1:]:
        second = selected_map.get(second_metric)
        if not second:
            continue
        matching = [row for row in evaluation_rows if row[first_metric] is not None and row[second_metric] is not None and meets(row[first_metric], first["threshold"], first["direction"]) and meets(row[second_metric], second["threshold"], second["direction"])]
        if len(matching) < 30:
            continue
        wins = sum(row["won"] for row in matching)
        low, high = cluster_interval(matching)
        pairs.append({
            "metric_1": first_metric, "label_1": first["metric_label"], "direction_1": first["direction"], "threshold_1": first["threshold"],
            "metric_2": second_metric, "label_2": second["metric_label"], "direction_2": second["direction"], "threshold_2": second["threshold"],
            "validation_n": len(matching), "validation_win_rate": wins / len(matching), "validation_ci_low": low, "validation_ci_high": high,
            "validation_seasons": " | ".join(evaluation_seasons), "rolling_folds": len(evaluation_seasons),
        })
pairs = sorted(pairs, key=lambda row: (row["validation_win_rate"], row["validation_n"]), reverse=True)[:30]

write_csv("threshold_results.csv", results)
write_csv("selected_thresholds.csv", selected)
write_csv("combination_rules.csv", pairs)
(BASE / "VALIDATION_REPORT.md").write_text(
    "# Validation report\n\n"
    f"- {len(team_games) // 2} games and {len(team_games)} paired team-game rows.\n"
    "- Five chronological rolling folds: each season from 2021–22 onward is predicted only from earlier seasons.\n"
    "- A monotonic continuous probability curve is fitted separately for every statistic.\n"
    "- The displayed all-season curve is refitted only after rolling validation is complete.\n"
    "- Coaching cut-offs are the least extreme natural increment where both the rolling estimate and the final all-season estimate reach a 70% win rate, the observed rolling rate is at least 65%, and the model-to-observed gap is no more than eight percentage points. Each also requires at least 40 team-games and three represented validation seasons.\n"
    "- Confidence intervals resample whole games, keeping the two opposing team rows together.\n"
    "- Results remain descriptive associations; outcome-adjacent measures such as points and efficiency are not causal targets.\n",
    encoding="utf-8",
)
(BASE / "FINDINGS.md").write_text(
    "# Rolling win-threshold findings\n\n" + "\n".join(
        f"- {row['metric_label']} {'≥' if row['direction'] == 'at_least' else '≤'} {row['threshold']}: {row['validation_win_rate']:.1%} actual rolling win rate across {row['validation_n']} team-games; model expectation {row['rolling_model_win_rate']:.1%}."
        for row in sorted(selected, key=lambda item: item["validation_win_rate"], reverse=True)
    ) + "\n",
    encoding="utf-8",
)
print(json.dumps({"team_games": len(team_games), "folds": len(evaluation_seasons), "thresholds": len(results), "selected": len(selected), "pairs": len(pairs)}))
