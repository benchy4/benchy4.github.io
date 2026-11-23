"""Import aggregate PnR outcomes from a Hudl exchange XML directory with source_manifest.json.

Run: python3 scripts/import_pnr_efficiency.py PATH_TO_XML_DIRECTORY
"""
import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
import xml.etree.ElementTree as ET

DATA = Path(__file__).resolve().parents[1] / "app/scouting"
ALIASES = {"University of Canberra Capitals": "UC Capitals", "Tasmania Jewels W": "Tasmania Jewels"}


def made_points(labels):
    return sum(int(shot) for shot in labels["Shot"] if shot.startswith("+"))


def coverage(labels):
    tags = set(labels["Handler Defense"]) | set(labels["Screener Defense"])
    if tags == {"Ice", "Drop"}:
        return "ICE / Drop"
    if len(tags) > 1:
        return "Multiple coverages"
    return next(iter(tags), "Untagged").replace("Trap", "Double (trap)")


def outcomes(xml, game):
    live = []
    scores = Counter()
    previous = None
    records = ET.fromstring(xml).findall("./ALL_INSTANCES/instance[code='Full Game']")
    for event in sorted(records, key=lambda e: float(e.findtext("start"))):
        labels = defaultdict(list)
        for label in event.findall("label"):
            labels[label.findtext("group")].append(label.findtext("text"))
        team, = labels["Offensive Team"]
        period, = labels["Period"]
        points = made_points(labels)
        scores[team] += points
        if "Free Throw" in labels["Shot Characteristics"]:
            # Credit the fouled player’s ensuing free throws to the live-ball event.
            if (previous and (team, period) == previous["key"]
                    and set(labels["Shooter"]).intersection(previous["labels"]["Foul Drawn"])
                    and "Technical" not in previous["labels"]["Foul Class"]):
                previous["points"] += points
                previous["last_ft_made"] = "+1" in labels["Shot"]
            continue
        previous = {"key": (team, period), "labels": labels, "points": points, "last_ft_made": False}
        live.append(previous)

    expected = {game["team_a"]: game["score_a"], game["team_b"]: game["score_b"]}
    if dict(scores) != expected:
        raise ValueError(f"Final score mismatch: {scores} vs {expected}")

    chains = []
    ended = True
    for event in live:
        if ended or event["key"] != chains[-1][-1]["key"]:
            chains.append([])
        chains[-1].append(event)
        labels = event["labels"]
        ended = ("Turnover" in labels["Result"] or bool({"+2", "+3"}.intersection(labels["Shot"]))
                 or event["last_ft_made"])

    by_team = {team: {} for team in expected}
    count = 0
    for chain in chains:
        coverages = {coverage(e["labels"]) for e in chain if "Ball Screen" in e["labels"]["Play Type"]}
        if not coverages:
            continue
        category = coverages.pop() if len(coverages) == 1 else "Multiple coverages"
        team = chain[0]["key"][0]
        total = by_team[team].setdefault(category, {"possessions": 0, "points": 0, "turnovers": 0})
        total["possessions"] += 1
        total["points"] += sum(e["points"] for e in chain)
        total["turnovers"] += int(any("Turnover" in e["labels"]["Result"] for e in chain))
        count += 1
    if count != (game["pnr_possessions"] or 0):
        raise ValueError(f"Expected {game['pnr_possessions']} tagged possessions, found {count}")
    return None if game["pnr_possessions"] is None else by_team


def main(folder):
    manifest = json.loads((folder / "source_manifest.json").read_text())
    index = json.loads((DATA / "index.json").read_text())
    by_box = {g["box"]: g for g in index["games"] if g.get("box")}
    codes = {name: code for code, name in index["teams"].items()}
    target = DATA / "pnr-efficiency.json"
    updated = json.loads(target.read_text()) if target.exists() else {}
    for game in manifest["games"]:
        xml = (folder / game["source_xml"]).read_bytes()
        if hashlib.sha256(xml).hexdigest() != game["sha256"]:
            raise ValueError(f"Source checksum mismatch for {game['game']}")
        box = game["match_url"].rstrip("/").split("/")[-1]
        fixture = by_box[box]
        teams = {name: codes[ALIASES.get(name, name)] for name in (game["team_a"], game["team_b"])}
        if set(teams.values()) != {fixture["home"], fixture["away"]} or fixture["date"] != game["date"]:
            raise ValueError(f"Fixture mismatch for {game['game']}")
        stats = outcomes(xml, game)
        updated[fixture["id"]] = None if stats is None else {teams[t]: group for t, group in stats.items()}
    target.write_text(json.dumps(updated, sort_keys=True, indent=2) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("folder", type=Path)
    main(parser.parse_args().folder)
