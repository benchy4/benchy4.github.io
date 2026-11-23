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


def outcomes(xml, game, expected):
    live = []
    scores = Counter()
    periods, tagged_periods = set(), set()
    previous = None
    records = ET.fromstring(xml).findall("./ALL_INSTANCES/instance[code='Full Game']")
    for event in sorted(records, key=lambda e: float(e.findtext("start"))):
        labels = defaultdict(list)
        for label in event.findall("label"):
            labels[label.findtext("group")].append(label.findtext("text"))
        team, = labels["Offensive Team"]
        period, = labels["Period"]
        periods.add(int(period))
        if labels["Play Type"]:
            tagged_periods.add(int(period))
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

    if set(scores) != set(expected):
        raise ValueError(f"Teams in XML do not match the fixture: {list(scores)}")
    if dict(scores) != expected:
        return None, {"scoreMismatch": True, "exportScore": [scores[t] for t in expected],
                      "boxScore": list(expected.values())}

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
        if len(coverages) > 1:
            coverages.discard("Untagged")
        category = coverages.pop() if len(coverages) == 1 else "Multiple coverages"
        team = chain[0]["key"][0]
        total = by_team[team].setdefault(category, {"possessions": 0, "points": 0, "turnovers": 0})
        total["possessions"] += 1
        total["points"] += sum(e["points"] for e in chain)
        total["turnovers"] += int(any("Turnover" in e["labels"]["Result"] for e in chain))
        count += 1
    if "pnr_possessions" in game and count != (game["pnr_possessions"] or 0):
        raise ValueError(f"Expected {game['pnr_possessions']} tagged possessions, found {count}")
    note = {"taggedPeriods": sorted(tagged_periods)} if tagged_periods < periods and tagged_periods else {}
    return (by_team if count else None), note


def main(folder):
    manifest = json.loads((folder / "source_manifest.json").read_text())
    index = json.loads((DATA / "index.json").read_text())
    boxes = json.loads((DATA.parent / "box-scores.json").read_text())["games"]
    by_box = {str(g["game_id"]): g for g in boxes}
    official_ids = {g["box"]: g["id"] for g in index["games"] if g.get("box")}
    codes = {name: code for code, name in index["teams"].items()}
    target = DATA / "pnr-efficiency.json"
    notes_path = DATA.parent / "pnr-review.json"
    updated = json.loads(target.read_text()) if target.exists() else {}
    notes = json.loads(notes_path.read_text()) if notes_path.exists() else {}
    for game in manifest["games"]:
        xml = (folder / game["source_xml"]).read_bytes()
        if hashlib.sha256(xml).hexdigest() != game["sha256"]:
            raise ValueError(f"Source checksum mismatch for {game['game']}")
        box = game["match_url"].rstrip("/").split("/")[-1]
        fixture = by_box[box]
        names = {ALIASES.get(n, n): n for n in (game["team_a"], game["team_b"])}
        box_names = [ALIASES.get(fixture[k], fixture[k]) for k in ("team_1", "team_2")]
        if set(names) != set(box_names) or fixture["game_date"] != game["date"]:
            raise ValueError(f"Fixture mismatch for {game['game']}")
        expected = {names[name]: fixture["score_" + str(i)] for i, name in enumerate(box_names, 1)}
        stats, note = outcomes(xml, game, expected)
        key = official_ids.get(box, box)
        if key != box:
            updated.pop(box, None)
        updated[key] = None if stats is None else {codes[ALIASES.get(n, n)]: v for n, v in stats.items()}
        if note:
            notes[box] = note
        else:
            notes.pop(box, None)
    notes_path.write_text(json.dumps(notes, sort_keys=True, indent=2) + "\n")
    target.write_text(json.dumps(updated, sort_keys=True, indent=2) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("folder", type=Path)
    main(parser.parse_args().folder)
