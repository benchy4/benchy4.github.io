"""Import the public WNBL Edge data.json snapshot into Benchy's static scouting views.

Usage: python3 scripts/import_scouting.py /path/to/data.json
"""
import json
import sys
from collections import defaultdict
from pathlib import Path

from player_identity import canonical_player

ROOT = Path(__file__).resolve().parents[1]
TEAM_NAMES = {"University of Canberra Capitals": "UCC"}
# Official-feed and InStat spellings used on Benchy's player profiles.
PLAYER_NAMES = {
    "Chantel Horvat": "Chantel-Anais Horvat", "Isabel Palmer": "Isabel Leigh Palmer",
    "Mackenzie Clinch Hoycard": "Mackenzie Clinch", "Maddy Freer": "Madison Freer",
    "Madeline Westbeld": "Maddy Westbeld", "Manuela Puoch": "Manuala Puoch",
    "Marie Gülich": "Marie Guelich", "Millicent McCarthy": "Millie McCarthy",
    "Nyaduoth Lok": "Nya Lok", "Shyla Heal": "Shyla Jade Heal", "Tera Reed": "Akiene Tera Reed",
    "Unique Thompson": "Unique Alexandria Thompson", "Wang Siyu": "Siyu Wang",
    "Yang Shuyu": "Shuyu Yang", "Yemiyah Morris": "Yemiyah Aiyanna Morris",
}
COVERAGES = ["Over", "Under", "Switch", "Double", "Hedge", "Ice"]
STATS = ["fgm", "fga", "tpm", "tpa", "ftm", "fta", "oreb", "dreb", "ast", "stl", "tov", "foul"]


def scope(snapshot, games):
    matches = [games[g["officialMatchId"]] for g in snapshot["games"]]
    if len(set(g["id"] for g in matches)) != len(matches):
        raise ValueError("Duplicate match in provider snapshot")
    if any(snapshot["team"] not in (g["home"], g["away"]) or snapshot["season"] != g["season"] for g in matches):
        raise ValueError("Provider scope does not match the official schedule")
    return {"games": [g["id"] for g in matches], "captured": snapshot["retrievedAt"][:10]}


def on_off(snapshot, name):
    units = snapshot["rows"]
    audit = snapshot["audit"]
    if not audit["scoreVerified"] or any(sum(u[k] for u in units) != audit[k] for k in
                                         ("seconds", "possessions", "opponent_possessions", "points", "allowed")):
        raise ValueError("Lineup totals failed reconciliation")
    totals = {}
    for unit in units:
        people = {name(p) for p in unit["players"]}
        if len(people) != 5:
            raise ValueError("Lineup needs five distinct players")
        for player in people:
            totals.setdefault(player, {})
    for player, splits in totals.items():
        for key, present in (("on", True), ("off", False)):
            rows = [u for u in units if (player in {name(p) for p in u["players"]}) == present]
            split = {k: sum(u[k] for u in rows) for k in ("seconds", "possessions", "opponent_possessions", "points", "allowed")}
            for side, src in (("team", "stats"), ("opponent", "opponent_stats")):
                split[side] = {k: sum(u[src][k] for u in rows) if all(u.get(src, {}).get(k) is not None for u in rows) else None for k in STATS}
            splits[key] = split
    return {"players": totals, "unallocatedSeconds": audit["unallocatedSeconds"]}


def convert(data):
    profiles = json.loads((ROOT / "app/player-profiles.json").read_text())["profiles"]
    names = {p["name"].casefold(): p["name"] for p in profiles}
    def name(raw):
        value = canonical_player(PLAYER_NAMES.get(raw, raw)) if raw else "Unknown"
        return names.get(value.casefold(), value)

    codes = {v["name"]: k for k, v in data["teams"].items()} | TEAM_NAMES
    boxes = defaultdict(list)
    for b in json.loads((ROOT / "app/box-scores.json").read_text())["games"]:
        sides = frozenset(codes.get(b[k]) for k in ("team_1", "team_2"))
        boxes[b["game_date"], sides].append(b)
    seasons = defaultdict(list)
    index = {"teams": {k: v["name"] for k, v in data["teams"].items()}, "games": [],
             "coverage": {}, "impact": {}, "source": "https://wnbl-edge-fire.sjsee.chatgpt.site/"}
    games = {g["id"]: g for g in data["games"]}
    for g in games.values():
        date = g["date"][:10]
        matches = boxes[date, frozenset((g["home"], g["away"]))]
        matches = [b for b in matches if b["season"] == g["season"] and all(
            b["score_" + i] == g["teams"][codes[b["team_" + i]]]["pts"] for i in ("1", "2"))]
        verified = all(t["shotsVerified"] for t in g["teams"].values())
        info = {k: g[k] for k in ("id", "season", "home", "away", "phase")}
        info.update(date=date, verified=verified, periods=int((g["minutes"] - 40) / 5) + 4,
                    box=str(matches[0]["game_id"]) if len(matches) == 1 else None)
        index["games"].append(info)
        if not verified:
            continue
        players = sorted({name(s["player"]) for s in g["shots"]})
        shots = []
        for code, totals in g["teams"].items():
            attempts = [s for s in g["shots"] if s["team"] == code]
            if len(attempts) != totals["fga"] or sum(s["made"] for s in attempts) != totals["fgm"]:
                raise ValueError(f"Shot count mismatch in {g['id']}")
        for s in g["shots"]:
            if not (0 <= s["x"] <= 100 and 0 <= s["y"] <= 100 and 1 <= s["period"] <= info["periods"]):
                raise ValueError(f"Unusable shot in {g['id']}")
            shots.append([int(s["team"] == g["away"]), players.index(name(s["player"])), s["period"],
                          s["clock"], s["x"], s["y"], s["made"], s["value"], s["zone"]])
        seasons[g["season"]].append({"id": g["id"], "players": players, "shots": shots})
    for snapshot in data["inStatTagged"]:
        record = scope(snapshot, games)
        for side in ("offence", "defence"):
            tagged = snapshot["pnr"][side]
            counts = {k: tagged["coverages"].get(k, {}).get("clips") for k in COVERAGES}
            if all(v is not None for v in counts.values()) and sum(counts.values()) != tagged["totalClips"]:
                raise ValueError("Coverage totals failed reconciliation")
            record[side] = {"total": tagged["totalClips"], "counts": counts}
        index["coverage"].setdefault(snapshot["season"], {})[snapshot["team"]] = record
    for snapshot in data["inStatLineups"]:
        record = scope(snapshot, games) | on_off(snapshot, name)
        index["impact"].setdefault(snapshot["season"], {})[snapshot["team"]] = record
    return {"index": index, **seasons}


if __name__ == "__main__":
    result = convert(json.loads(Path(sys.argv[1]).read_text()))
    output = ROOT / "app/scouting"
    output.mkdir(exist_ok=True)
    for key, value in result.items():
        (output / f"{key}.json").write_text(json.dumps(value, separators=(",", ":"), ensure_ascii=False) + "\n")
