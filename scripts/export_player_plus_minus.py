import csv
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT.parent / "outputs/WNBL_Data_Collector/wnbl_dataset"
PROCESSED = DATASET / "processed"
SOURCE = ROOT / "app/player-plus-minus-collection.json"


def write_csv(path, fieldnames, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


collection = json.loads(SOURCE.read_text(encoding="utf-8"))
player_rows = []
game_rows = []

for game in collection["games"]:
    game_rows.append(
        {
            "season": game["season"],
            "game_id": game["game_id"],
            "game_date": game["game_date"],
            "team_1": game["team_1"],
            "team_2": game["team_2"],
            "score_1": game["score_1"],
            "score_2": game["score_2"],
            "collection_status": game["status"],
            "validation_status": game["validation"],
            "player_rows": sum(len(team.get("rows", [])) for team in game.get("teams", [])),
            "reason": game.get("reason", ""),
            "source_url": game.get("url") or game["source_url"],
            "collected_at": game.get("collected_at", ""),
        }
    )
    if game["status"] != "complete":
        continue
    for team in game["teams"]:
        for player in team["rows"]:
            player_rows.append(
                {
                    "season": game["season"],
                    "game_id": game["game_id"],
                    "game_date": game["game_date"],
                    "team": team["expected_team"],
                    "opponent": game["team_2"] if team["expected_team"] == game["team_1"] else game["team_1"],
                    "hudl_player_id": player["hudl_player_id"],
                    "jersey_number": player["jersey_number"],
                    "player": player["player"],
                    "minutes": player["minutes"],
                    "plus_minus": player["plus_minus"],
                    "team_score": team["score"],
                    "opponent_score": team["opponent_score"],
                    "team_margin": team["score"] - team["opponent_score"],
                    "validation_status": game["validation"],
                    "source_url": game.get("url") or game["source_url"],
                    "collected_at": game.get("collected_at", ""),
                }
            )

player_fields = [
    "season",
    "game_id",
    "game_date",
    "team",
    "opponent",
    "hudl_player_id",
    "jersey_number",
    "player",
    "minutes",
    "plus_minus",
    "team_score",
    "opponent_score",
    "team_margin",
    "validation_status",
    "source_url",
    "collected_at",
]
game_fields = [
    "season",
    "game_id",
    "game_date",
    "team_1",
    "team_2",
    "score_1",
    "score_2",
    "collection_status",
    "validation_status",
    "player_rows",
    "reason",
    "source_url",
    "collected_at",
]

write_csv(PROCESSED / "player_plus_minus.csv", player_fields, player_rows)
write_csv(PROCESSED / "player_plus_minus_game_status.csv", game_fields, game_rows)

valid_games = sum(row["collection_status"] == "complete" for row in game_rows)
unavailable_games = len(game_rows) - valid_games
assert len({row["game_id"] for row in game_rows}) == len(game_rows)
assert all(row["validation_status"] == "pass" for row in game_rows if row["collection_status"] == "complete")
print(
    {
        "games": len(game_rows),
        "valid_games": valid_games,
        "unavailable_games": unavailable_games,
        "player_rows": len(player_rows),
    }
)
