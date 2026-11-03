import csv,json,re,unicodedata
from collections import defaultdict
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT.parent/"outputs/WNBL_Data_Collector/wnbl_dataset"
PROCESSED=DATA/"processed"
team_profiles=json.loads((ROOT/"app/team-profiles.json").read_text(encoding="utf-8"))
logos={p["dataset_name"]:p["logo"] for p in team_profiles["profiles"]}
pilot_path=ROOT/"app/pilot-instat-2357804.json"
pilots={}
if pilot_path.exists():
    pilot=json.loads(pilot_path.read_text(encoding="utf-8"))
    pilots[pilot["game_id"]]=pilot
current_lineups=ROOT/"app/current-season-lineups.json"
if current_lineups.exists():
    pilots.update({g["game_id"]:g for g in json.loads(current_lineups.read_text())})
plus_minus_path=ROOT/"app/player-plus-minus-collection.json"
plus_minus_games={}
if plus_minus_path.exists():
    collection=json.loads(plus_minus_path.read_text(encoding="utf-8"))
    plus_minus_games={row["game_id"]:row for row in collection["games"]}

def normalise_name(value):
    value=unicodedata.normalize("NFKD",value or "")
    return re.sub(r"[^a-z0-9]","",value.encode("ascii","ignore").decode().lower())

def number(value):
    try:return int(float(value))
    except:return 0

with (PROCESSED/"games.csv").open(newline="",encoding="utf-8-sig") as f:
    games=list(csv.DictReader(f))

players=defaultdict(list)
with (PROCESSED/"player_game_stats.csv").open(newline="",encoding="utf-8-sig") as f:
    for row in csv.DictReader(f):
        cleaned={k:(number(v) if k in {"points","fg_made","fg_attempted","three_made","three_attempted","ft_made","ft_attempted","rebounds","offensive_rebounds","defensive_rebounds","assists","steals","turnovers","blocks","fouls"} else v) for k,v in row.items()}
        cleaned["two_made"]=cleaned["fg_made"]-cleaned["three_made"]
        cleaned["two_attempted"]=cleaned["fg_attempted"]-cleaned["three_attempted"]
        players[row["game_id"]].append(cleaned)

records=[]
notes_path=ROOT/"app/current-season-source-notes.json"
source_notes=json.loads(notes_path.read_text()) if notes_path.exists() else {}
for game in games:
    game={**game,"score_1":number(game["score_1"]),"score_2":number(game["score_2"])}
    game["source_note"]=source_notes.get(game["game_id"],"")
    game["logo_1"]=logos.get(game["team_1"],"")
    game["logo_2"]=logos.get(game["team_2"],"")
    pilot=pilots.get(game["game_id"])
    collection_game=plus_minus_games.get(game["game_id"])
    plus_minus={}
    if collection_game and collection_game["status"]=="complete":
        for team in collection_game["teams"]:
            for row in team["rows"]:
                plus_minus[(team["expected_team"],normalise_name(row["player"]))]=row["plus_minus"]
    elif pilot:
        plus_minus={(row["team"],normalise_name(row["player"])):row["plus_minus"] for row in pilot.get("player_plus_minus",[])}
    game["players"]=[{**row,"plus_minus":plus_minus.get((row["team"],normalise_name(row["player"])))} for row in players[game["game_id"]]]
    game["plus_minus_status"]=collection_game["status"] if collection_game else "not_collected"
    game["plus_minus_validation"]=collection_game["validation"] if collection_game else "not_run"
    if pilot:
        game["lineups"]=pilot["five_player_lineups"]
        game["lineup_source"]="Official Hudl/InStat Players and Lineups tabs"
        game["lineup_validation"]={
            "player_plus_minus_reconciles":all(
                sum(row["plus_minus"] for row in pilot["player_plus_minus"] if row["team"]==team)==margin*5
                for team,margin in ((game["team_1"],game["score_1"]-game["score_2"]),(game["team_2"],game["score_2"]-game["score_1"]))
            ),
            "lineup_plus_minus_reconciles":all(
                sum(row["plus_minus"] for row in pilot["five_player_lineups"] if row["team"]==team)==margin
                for team,margin in ((game["team_1"],game["score_1"]-game["score_2"]),(game["team_2"],game["score_2"]-game["score_1"]))
            )
        }
    records.append(game)

out={"games":records,"seasons":sorted({g["season"] for g in records}),"count":len(records)}
(ROOT/"app/box-scores.json").write_text(json.dumps(out,separators=(",",":"),ensure_ascii=False),encoding="utf-8")
print({"games":len(records),"player_rows":sum(len(g["players"]) for g in records)})
