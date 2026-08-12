import csv
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT.parent / "outputs/WNBL_Data_Collector/wnbl_dataset"
pilot = json.loads((ROOT / "app/pilot-instat-2357804.json").read_text(encoding="utf-8"))
game = next(
    row
    for row in csv.DictReader(
        (DATASET / "processed/games.csv").open(newline="", encoding="utf-8-sig")
    )
    if row["game_id"] == pilot["game_id"]
)

player_fields = [
    "season",
    "game_id",
    "game_date",
    "team",
    "hudl_player_id",
    "player",
    "minutes",
    "plus_minus",
    "source_url",
]
with (DATASET / "processed/player_plus_minus.csv").open("w", newline="", encoding="utf-8") as handle:
    writer = csv.DictWriter(handle, fieldnames=player_fields)
    writer.writeheader()
    for row in pilot["player_plus_minus"]:
        writer.writerow(
            {
                "season": game["season"],
                "game_id": game["game_id"],
                "game_date": game["game_date"],
                **row,
                "source_url": pilot["source_url"] + "/players",
            }
        )

lineup_fields = [
    "season",
    "game_id",
    "game_date",
    "team",
    "lineup_id",
    "players",
    "minutes",
    "possessions",
    "points",
    "points_allowed",
    "plus_minus",
    "offensive_rating",
    "defensive_rating",
    "net_rating",
    "source_url",
]
with (DATASET / "processed/five_player_lineups.csv").open("w", newline="", encoding="utf-8") as handle:
    writer = csv.DictWriter(handle, fieldnames=lineup_fields)
    writer.writeheader()
    for row in pilot["five_player_lineups"]:
        possessions = row["possessions"]
        points_allowed = row["points"] - row["plus_minus"]
        offensive_rating = 100 * row["points"] / possessions if possessions else None
        defensive_rating = 100 * points_allowed / possessions if possessions else None
        lineup_key = "|".join(sorted(row["players"]))
        writer.writerow(
            {
                "season": game["season"],
                "game_id": game["game_id"],
                "game_date": game["game_date"],
                "team": row["team"],
                "lineup_id": hashlib.sha1((row["team"] + "|" + lineup_key).encode()).hexdigest()[:12],
                "players": " | ".join(row["players"]),
                "minutes": row["minutes"],
                "possessions": possessions,
                "points": row["points"],
                "points_allowed": points_allowed,
                "plus_minus": row["plus_minus"],
                "offensive_rating": "" if offensive_rating is None else round(offensive_rating, 2),
                "defensive_rating": "" if defensive_rating is None else round(defensive_rating, 2),
                "net_rating": "" if offensive_rating is None else round(offensive_rating - defensive_rating, 2),
                "source_url": pilot["source_url"] + "/lineups",
            }
        )

print({"player_rows": len(pilot["player_plus_minus"]), "lineup_rows": len(pilot["five_player_lineups"])})
