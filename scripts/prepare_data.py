import csv, json
from pathlib import Path
from player_identity import canonical_player, merge_player_season_rows

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT.parent / "outputs/WNBL_Data_Collector/wnbl_dataset/analytics"

def short_team(name):
    if name == "University of Canberra Capitals":
        return "UC Capitals"
    if name == "Southside Melbourne Flyers":
        return "Southside Flyers"
    return name.split()[0] if name else name

def rows(path, fields=None):
    with open(BASE/path, encoding="utf-8-sig", newline="") as f:
        source=list(csv.DictReader(f))
    if fields: source=[{k:r.get(k,"") for k in fields} for r in source]
    for r in source:
        for k,v in list(r.items()):
            if v=="" or v is None: r[k]=None
            else:
                try: r[k]=float(v) if any(c in v.lower() for c in ".e") else int(v)
                except (ValueError,AttributeError): pass
        if "team" in r:
            r["team"]=short_team(r["team"])
        for k in ("player_name","assister_name","scorer_name","primary_assister","shooter","defender","leading_scorer","leading_creator"):
            if k in r and isinstance(r[k],str):
                r[k]=canonical_player(r[k])
    return source

profile_data=json.loads((ROOT/"app/player-profiles.json").read_text(encoding="utf-8"))
defense_data=json.loads((ROOT/"app/defense.json").read_text(encoding="utf-8"))
team_profile_data=json.loads((ROOT/"app/team-profiles.json").read_text(encoding="utf-8"))
player_rows=merge_player_season_rows(rows("broader_programme/player_impact_profiles.csv"))
profile_plus_minus={(str(r["season"]),r["team"],p["name"]):r["plus_minus"] for p in profile_data["profiles"] for r in p["season_stats"]}
on_off_fields=("on_minutes","off_minutes","on_plus_minus","off_plus_minus","on_plus_minus_per_40","off_plus_minus_per_40","on_off_plus_minus_per_40","team_relative_plus_minus_per_40","on_off_ci_low","on_off_ci_high","on_off_sample","offensive_rating","defensive_rating","offensive_win_shares","defensive_win_shares","win_shares","win_shares_per_40","team_win_share","adjustment_win_shares","adjusted_win_shares","adjusted_win_shares_per_40","adjusted_team_win_share")
profile_on_off={(str(r["season"]),r["team"],p["name"]):{k:r.get(k) for k in on_off_fields} for p in profile_data["profiles"] for r in p["season_stats"]}
for row in player_rows:
    key=(str(row["season"]),row["team"],row["player_name"])
    if key not in profile_plus_minus:
        raise ValueError(f"Missing official plus/minus for {key}")
    row["plus_minus"]=profile_plus_minus[key]
    row.update(profile_on_off[key])
possession_rows=rows("possessions.csv")
covered_ids={str(r["game_id"]) for r in possession_rows}
dataset_games=[r for r in rows("games_analytics.csv") if str(r["game_id"]) in covered_ids]
synergy_plays=sum(float(r.get("synergy_play_possessions") or 0) for r in rows("possessions.csv"))
foul_opportunities=rows("late_game_foul_policy/late_game_foul_opportunity_detail.csv")
foul_count=sum(r["nonshooting_foul_candidate"] == "True" for r in foul_opportunities)
data={
 "meta":{"seasons":sorted({str(r["season"]) for r in dataset_games}),"games":len(dataset_games),"latest_game_date":max(r["game_date"] for r in dataset_games),"current_season":"2026-27","current_season_complete":False,"possessions":round(synergy_plays,1),"possession_definition":"Possessions used for PPP calculations"},
 "speed":rows("true_possession_speed/true_ppp_by_first_decision_band.csv"),
 "turnovers":rows("advanced_decisions/turnover_consequence_summary.csv"),
 "kills":rows("model_adjusted_decisions/kill_win_probability_added_summary.csv"),
 "clutch":rows("late_game_foul_policy/clutch_team_season_efficiency.csv"),
 "oreb":rows("broader_programme/oreb_extension_play_type_summary.csv"),
 "networks":rows("broader_programme/assist_network_edges.csv"),
 "chemistry":rows("broader_programme/player_chemistry_connections.csv"),
 "networkStructure":rows("broader_programme/team_assist_network_structure.csv"),
 "creators":rows("broader_programme/creator_versatility.csv"),
 "players":player_rows,
 "defensePlayers":defense_data["player_seasons"],
 "defenseAudit":defense_data["audit"],
 "playerProfileSlugs":profile_data["slugs"],
 "development":rows("broader_programme/player_season_development.csv",["season","team","player_name","assisted_make_share","observed_assists","points_created","scorer_partners","play_types_created","change_in_assisted_make_share","change_in_observed_assists","change_in_points_created"]),
 "teams":rows("broader_programme/team_tactical_fingerprints.csv"),
 "teamProfileSlugs":team_profile_data["slugs"],
 "thresholdResults":rows("winning_thresholds/threshold_results.csv"),
 "selectedThresholds":rows("winning_thresholds/selected_thresholds.csv"),
 "thresholdCombinations":rows("winning_thresholds/combination_rules.csv"),
 "foulPolicy":rows("late-game-foul-dashboard/app/foul-data.json") if False else []
}
data["meta"]["late_fouls"]={"opportunities":len(foul_opportunities),"fouls":foul_count,"no_foul":len(foul_opportunities)-foul_count,"rate":foul_count/len(foul_opportunities)}
(ROOT/"app").mkdir(exist_ok=True)
(ROOT/"app/data.json").write_text(json.dumps(data,separators=(",",":"),ensure_ascii=False),encoding="utf-8")
print({k:len(v) if isinstance(v,list) else v for k,v in data.items()})
