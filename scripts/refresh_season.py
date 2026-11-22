"""Rebuild all WNBL analytical layers from the validated local game archive."""
import csv
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
COLLECTOR = ROOT.parent / "outputs/WNBL_Data_Collector"
DATA = COLLECTOR / "wnbl_dataset"
CAPTURE = ROOT.parent / "outputs/season-update-2026-27"

def run(script, *args):
    print(f"Rebuilding {Path(script).name}", flush=True)
    subprocess.run([sys.executable, str(script), *map(str, args)], check=True, cwd=ROOT)

def read_rows(path):
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))

def typed(row):
    result = {}
    for key, value in row.items():
        if value in ("", "nan", "NaN", None): result[key] = None
        elif value in ("True", "False"): result[key] = value == "True"
        elif key in ("season", "game_id"): result[key] = value
        else:
            try: result[key] = float(value)
            except (TypeError, ValueError): result[key] = value
    return result

def refresh_dashboard():
    path = ROOT / "static/late-game-foul-dashboard.html"
    template = path.read_text()
    old = json.loads(re.search(r'<script id="foul-data" type="application/json">(.*?)</script>', template, re.S)[1])
    records = []
    fields = list(old["records"][0])
    for raw in read_rows(DATA / "analytics/late_game_foul_policy/late_game_foul_opportunity_detail.csv"):
        row = typed(raw)
        time = row["stage_seconds_remaining"]
        if time is None or not 0 <= time <= 90 or abs(row["defense_margin"]) > 8:
            continue
        edge = min(5, max(0, (int(time) - 1) // 15))
        row["time_remaining"] = int(time)
        row["time_bucket"] = ["0–15", "16–30", "31–45", "46–60", "61–75", "76–90"][edge]
        records.append({k: row[k] for k in fields})
    hack = json.loads((ROOT / "app/hackulator-data.json").read_text())
    data = {"meta": {**old["meta"], "opportunities": len(records),
                     "seasons": sorted({r["season"] for r in records}),
                     "ft_oreb_comparison": hack["meta"]["ft_oreb_comparison"]},
            "records": records,
            "policy": [typed(r) for r in read_rows(DATA / "analytics/late_game_foul_policy/foul_decision_policy_by_state.csv")]}
    payload = json.dumps(data, ensure_ascii=False, allow_nan=False, separators=(",", ":")).replace("</script", "<\\/script")
    template = re.sub(r'(<script id="foul-data" type="application/json">).*?(</script>)', lambda m: m[1]+payload+m[2], template, flags=re.S)
    path.write_text(template)

def main():
    run(ROOT / "scripts/import_current_season.py")
    run(COLLECTOR / "collector.py", "--root", DATA, "ingest", "--season", "2026-27", "--input", CAPTURE / "collector-input.json")
    expected_ids = {str(g["gameId"]) for g in json.loads((CAPTURE / "collector-input.json").read_text())}
    archived_ids = {r["game_id"] for r in read_rows(DATA / "manifests/all_games.csv") if r["season"] == "2026-27"}
    assert expected_ids == archived_ids, ("Incomplete archive ingestion", expected_ids - archived_ids)
    validation = subprocess.run([sys.executable, str(COLLECTOR / "collector.py"), "--root", str(DATA), "validate"], capture_output=True, text=True)
    print(validation.stdout, flush=True)
    # The original archive contains two documented unavailable games.
    assert validation.returncode == 0 or (validation.returncode == 1 and "duplicates=0 review=2 missing_files=0" in validation.stdout and "236477" in validation.stdout and "831081" in validation.stdout), validation.stdout + validation.stderr
    run(COLLECTOR / "collector.py", "--root", DATA, "build")
    for name in ["analytics.py", "deep_dive_possessions.py", "advanced_decision_analytics.py",
                 "model_adjusted_decisions.py", "true_possession_speed.py", "late_game_foul_policy.py", "broader_programme.py"]:
        run(COLLECTOR / name, "--root", DATA)
    thresholds = DATA / "analytics/winning_thresholds"
    thresholds.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / "data/winning_thresholds/build_winning_thresholds.py", thresholds / "build_winning_thresholds.py")
    run(thresholds / "build_winning_thresholds.py")
    shutil.copytree(DATA / "analytics/winning_thresholds", ROOT / "data/winning_thresholds", dirs_exist_ok=True)
    shutil.copy2(DATA / "analytics/advanced_decisions/kill_team_game.csv", ROOT / "data/kill_team_game.csv")
    for name in ["export_player_plus_minus.py", "prepare_defense.py", "prepare_foul_risk.py",
                 "prepare_player_profiles.py --on-off-only", "prepare_win_shares.py", "prepare_player_profiles.py", "prepare_team_profiles.py",
                 "prepare_box_scores.py", "prepare_thresholds.py", "prepare_data.py",
                 "prepare_deep_dives.py", "analyze_rotation_compression.py", "prepare_hackulator.py"]:
        run(ROOT / "scripts" / name.split()[0], *name.split()[1:])
    refresh_dashboard()
    current = [g for g in json.loads((ROOT / "app/box-scores.json").read_text())["games"] if g["season"] == "2026-27"]
    metadata = json.loads((ROOT / "app/season-update.json").read_text())
    metadata.update(as_of=max(g["game_date"] for g in current), updated_at=datetime.now(timezone.utc).isoformat(), games=len(current), game_ids=sorted(g["game_id"] for g in current))
    metadata["continuity_note"] = "Requires eight completed games and prior-season minutes per team; only eligible teams appear."
    metadata["source_notes"] = json.loads((ROOT / "app/current-season-source-notes.json").read_text())
    metadata["checks"] = {"official_schedule_matches":len(current), "player_plus_minus_matches":len(current), "lineup_score_and_margin_matches":len(current), "automated_tests_passed":None}
    (ROOT / "app/season-update.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2)+"\n")
    print("All analytical layers rebuilt. Run npm test before publication.", flush=True)

if __name__ == "__main__":
    main()
