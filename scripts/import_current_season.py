"""Validate browser-captured InStat tables, then prepare the existing collector input."""
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
CAPTURE = ROOT.parent / "outputs/season-update-2026-27"
SEASON = "2026-27"
SOURCE_NOTES = {"2497248": "InStat source discrepancy: Sydney's player box score totals 93 points, including 18 for Shuyu Yang, while the final score, play-by-play and lineups record 95 (20 for Yang in the event log). Player figures are preserved as published; team results use the verified 95–68 final score."}
FIELDS = ["MinutesMIN", "PointsPT", "Field goals madeFG+", "Field goals attemptedFG",
          "Field goals, %FG%", "3-pt field goals made3PT+", "3-pt field goals attempted3PT",
          "3-pt field goals, %3PT%", "Free throws madeFT+", "Free throws attemptedFT",
          "Free throws, %FT%", "ReboundsREB", "Offensive reboundsOREB",
          "Defensive reboundsDREB", "AssistsAST", "StealsSTL", "TurnoversTOV", "BlocksBLK", "FoulsF"]

def number(value):
    return 0 if value in ("-", "", None) else int(value)

def seconds(value):
    m, s = value.split(":")
    return int(m) * 60 + int(s)

def convert(g):
    scores = list(map(int, re.search(r"(\d+):(\d+)", g["heading"]).groups()))
    date = datetime.strptime(g["date"], "%m.%d.%Y").date().isoformat()
    result = {k: g[k] for k in ["gameId", "sourceUrl", "date", "heading", "teams", "periodScores", "teamStats", "pbp", "playerLinks"]}
    result["playerTables"] = []
    pm = dict(season=SEASON, game_id=g["gameId"], game_date=date,
              team_1=g["teams"][0], team_2=g["teams"][1], score_1=scores[0], score_2=scores[1],
              source_url=g["sourceUrl"], url=g["sourceUrl"]+"/players", status="complete",
              validation="pass", teams=[], collected_at=datetime.now(timezone.utc).isoformat())
    lineup = dict(game_id=g["gameId"], source_url=g["sourceUrl"], collected_from=["Players", "Lineups"], player_plus_minus=[], five_player_lineups=[])
    assert len(g["rawPlayerTables"]) == len(g["rawLineups"]) == 2
    duration = 2400 + max(0, len(g["periodScores"]) - 4) * 300
    names = {}
    for i, table in enumerate(g["rawPlayerTables"]):
        headers, rows = table[0], table[1:]
        assert headers[0] == g["teams"][i], (g["gameId"], "team order")
        assert len(rows) >= 5
        out = [["Jersey number#", "Player", *FIELDS]]
        pm_rows = []
        for j, row in enumerate(rows):
            jersey, name = g["playerNames"][i][j]
            player_id = g["playerLinks"][i][j].split("/")[-1]
            names[player_id] = name
            out.append([jersey, name, *[row[headers.index(field)] for field in FIELDS]])
            record = dict(hudl_player_id=player_id, jersey_number=jersey, player=name,
                          minutes=row[headers.index("MinutesMIN")], plus_minus=number(row[headers.index("Plus/Minus+/-")]))
            pm_rows.append(record)
            lineup["player_plus_minus"].append(dict(record, team=g["teams"][i]))
        result["playerTables"].append(out)
        player_points = sum(number(r[3]) for r in out[1:])
        if g["gameId"] == "2497248" and i == 0:
            assert (player_points, scores[i]) == (93, 95), "Recheck the known source discrepancy"
        else:
            assert player_points == scores[i], (g["gameId"], "player points")
        # InStat's video-coded intervals can omit a few seconds at period edges.
        # Keep the original times; reject material gaps rather than rescale them.
        assert abs(sum(seconds(r[2]) for r in out[1:]) - duration * 5) <= duration * .05, (g["gameId"], "player minutes")
        margin = scores[i] - scores[1-i]
        assert sum(r["plus_minus"] for r in pm_rows) == margin * 5, (g["gameId"], "player plus/minus")
        pm["teams"].append(dict(team=g["teams"][i], expected_team=g["teams"][i], score=scores[i], opponent_score=scores[1-i], rows=pm_rows,
                                plus_minus_sum=margin*5, expected_plus_minus_sum=margin*5, missing_plus_minus=0))
    for i, table in enumerate(g["rawLineups"]):
        headers, rows = table["rows"][0], table["rows"][1:]
        assert rows, (g["gameId"], "missing lineups")
        assert headers[0] == g["teams"][i]
        for row, links in zip(rows, table["playerLinks"]):
            assert len(links) == 5
            record = dict(team=g["teams"][i], players=[names[x["href"].split("/")[-1]] for x in links],
                          minutes=row[headers.index("MinutesMIN")], points=number(row[headers.index("PointsPT")]),
                          possessions=number(row[headers.index("PossessionsPOSS")]), plus_minus=number(row[headers.index("Plus/Minus+/-")]))
            lineup["five_player_lineups"].append(record)
        team_lineups = [r for r in lineup["five_player_lineups"] if r["team"] == g["teams"][i]]
        assert abs(sum(seconds(r["minutes"]) for r in team_lineups) - duration) <= duration * .01, (g["gameId"], "lineup minutes")
        assert sum(r["points"] for r in team_lineups) == scores[i], (g["gameId"], "lineup points")
        assert sum(r["plus_minus"] for r in team_lineups) == scores[i]-scores[1-i], (g["gameId"], "lineup plus/minus")
    assert len(g["pbp"]) > 100 and all(r[2] for r in g["pbp"][1:]), (g["gameId"], "event labels")
    final = next(r[3] for r in reversed(g["pbp"][1:]) if r[3])
    assert final == f"{scores[0]}:{scores[1]}", (g["gameId"], "final event score", final)
    periods = [list(map(int, p.split(":"))) for p in g["periodScores"]]
    assert [sum(p[i] for p in periods) for i in range(2)] == scores
    # Keep the source spelling in the capture; use the official club name in analytics.
    result["teams"] = [t.removesuffix(" W") if t.startswith("Tasmania Jewels") else t for t in result["teams"]]
    for k in ("team_1", "team_2"):
        pm[k] = pm[k].removesuffix(" W") if pm[k].startswith("Tasmania Jewels") else pm[k]
    for team in pm["teams"]:
        for k in ("team", "expected_team"):
            team[k] = team[k].removesuffix(" W") if team[k].startswith("Tasmania Jewels") else team[k]
    for row in lineup["player_plus_minus"] + lineup["five_player_lineups"]:
        row["team"] = row["team"].removesuffix(" W") if row["team"].startswith("Tasmania Jewels") else row["team"]
    return result, pm, lineup

def main():
    games, plus_minus, lineups, errors = [], [], [], []
    for path in sorted(CAPTURE.glob("[0-9]*.json")):
        try:
            g, p, l = convert(json.loads(path.read_text()))
            games.append(g); plus_minus.append(p); lineups.append(l)
        except (AssertionError, ValueError, KeyError) as exc:
            errors.append({"game": path.stem, "error": str(exc)})
    print(json.dumps({"validated_games": len(games), "errors": errors}, indent=2))
    if errors:
        sys.exit(1)
    official = [m for m in json.loads((CAPTURE / "official-schedule.json").read_text())["matches"] if m["season_type"] == "regular" and m["phase"] == "complete"]
    def club(name):
        return "Canberra" if "Canberra" in name or "Capitals" in name else name.split()[0]
    expected = {(datetime.fromtimestamp(m["starts_at_ms"] / 1000, ZoneInfo("Australia/Brisbane")).date().isoformat(), club(m["home"]["name"]), club(m["away"]["name"]), m["home_score"], m["away_score"]) for m in official}
    actual = {(g["game_date"], club(g["team_1"]), club(g["team_2"]), g["score_1"], g["score_2"]) for g in plus_minus}
    assert expected == actual, ("Official schedule mismatch", expected - actual, actual - expected)
    print("All 17 dates, opponents and final scores match the official WNBL schedule.")
    if "--check" in sys.argv:
        return
    assert len(games) == 17, "All 17 games must pass validation before import"
    (CAPTURE / "collector-input.json").write_text(json.dumps(games, ensure_ascii=False))
    pm_path = ROOT / "app/player-plus-minus-collection.json"
    existing = json.loads(pm_path.read_text())
    ids = {p["game_id"] for p in plus_minus}
    existing["games"] = [g for g in existing["games"] if g["game_id"] not in ids] + plus_minus
    existing["total_games"] = len(existing["games"])
    existing["updated_at"] = datetime.now(timezone.utc).isoformat()
    pm_path.write_text(json.dumps(existing, ensure_ascii=False, separators=(",", ":")))
    (ROOT / "app/current-season-lineups.json").write_text(json.dumps(lineups, ensure_ascii=False, separators=(",", ":")))
    (ROOT / "app/current-season-source-notes.json").write_text(json.dumps(SOURCE_NOTES, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
