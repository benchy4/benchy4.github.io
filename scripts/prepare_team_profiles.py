import csv,json,re
from collections import defaultdict
from pathlib import Path
from player_identity import canonical_player,merge_player_season_rows

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT.parent/"outputs/WNBL_Data_Collector/wnbl_dataset"
PROCESSED=DATA/"processed";ANALYTICS=DATA/"analytics"
DEFENSE=json.loads((ROOT/"app/defense.json").read_text(encoding="utf-8"))
COACH_SOURCE="https://www.wnbl.com.au/news/wnbl27-roster-tracker-every-off-season-move"
TEAMS=[
 {'dataset_name': 'Tasmania Jewels', 'name': 'Tasmania Jewels', 'slug': 'tasmania-jewels', 'coach': 'Claudia Brassard', 'logo': 'https://images.dc.connect.sportradar.com/b1jrd/5d917012344d4983a10ef442f7742397?size=200&format=webp', 'source': 'https://www.wnbl.com.au/news/tasmania-jewels-announce-inaugural-coach---claudia-brassard'},
 {"dataset_name":"Adelaide Lightning","name":"Adelaide Lightning","slug":"adelaide-lightning","coach":"Aja Parham-Ammar","logo":"https://cdn.prod.website-files.com/67edd996ab58aa16079f9454/6899df15a8c4a3edb445f481_6899d7332545db17b7f10241_256.webp","source":"https://adelaidelightning.wnbl.com.au/"},
 {"dataset_name":"Bendigo Spirit","name":"Bendigo Spirit","slug":"bendigo-spirit","coach":"Kennedy Kereama","logo":"https://cdn.prod.website-files.com/67edd996ab58aa16079f9454/689d6977ce07a7f730673b68_1a7c0fec-a826-4214-8182-018f056cf632-p-500.png","source":"https://bendigospirit.wnbl.com.au/"},
 {"dataset_name":"University of Canberra Capitals","name":"University of Canberra Capitals","slug":"canberra-capitals","coach":"Paul Goriss","logo":"https://cdn.prod.website-files.com/67edd996ab58aa16079f9454/67ede9a6f27cf615c17f25a5_UC-Capitals-2019%20(1).webp","source":"https://uccapitals.wnbl.com.au/"},
 {"dataset_name":"Geelong Venom","name":"Geelong Venom","slug":"geelong-venom","coach":"Cheryl Chambers","logo":"https://cdn.prod.website-files.com/67edd996ab58aa16079f9454/6892d6ae5308d544895c7473_6bf68ceb15c077bf61cffeca04762a3a_GEELONG%20VENOM%20LOGO.webp","source":"https://geelongvenom.wnbl.com.au/"},
 {"dataset_name":"Perth Lynx","name":"Perth Lynx","slug":"perth-lynx","coach":"Ryan Petrik","logo":"https://cdn.prod.website-files.com/67edd996ab58aa16079f9454/6892d6ae5308d544895c7479_55414e1a955b4dc1d24c60f70f589c7c_lynx-icon-full.svg","source":"https://perthlynx.wnbl.com.au/"},
 {"dataset_name":"Southside Melbourne Flyers","name":"Southside Melbourne Flyers","slug":"southside-melbourne-flyers","coach":"Sam MacKinnon","logo":"https://cdn.prod.website-files.com/67edd996ab58aa16079f9454/6892d6ae5308d544895c746f_5edc59139de271fbcea6eb756094311b_SM%20Flyers%20Monogram%20-%20POS.webp","source":"https://southsideflyers.wnbl.com.au/"},
 {"dataset_name":"Sydney Flames","name":"Sydney Flames","slug":"sydney-flames","coach":"Renae Garlepp","logo":"https://cdn.prod.website-files.com/67edd996ab58aa16079f9454/6892d6ae5308d544895c746b_a312dc63ee5a97748ee5d1f9a7b38ff6_Flames%203.webp","source":"https://sydneyflames.wnbl.com.au/"},
 {"dataset_name":"Townsville Fire","name":"Townsville Fire","slug":"townsville-fire","coach":"Shannon Seebohm","logo":"https://cdn.prod.website-files.com/67edd996ab58aa16079f9454/6892d6ae5308d544895c7471_5c064653e194eb49a1263ddfb25be3fd_Logo%20Townsville.webp","source":"https://townsvillefire.wnbl.com.au/"},
]
COUNT=["points","fg_made","fg_attempted","three_made","three_attempted","ft_made","ft_attempted","rebounds","offensive_rebounds","defensive_rebounds","assists","steals","turnovers","blocks","fouls"]
def n(v):
 try:return int(float(v))
 except:return 0
def short_team(name):
 if name=="University of Canberra Capitals":return "UC Capitals"
 if name=="Southside Melbourne Flyers":return "Southside Flyers"
 return name.split()[0] if name else name
def numeric(row):
 out={}
 for k,v in row.items():
  if v in ("",None):out[k]=None
  else:
   try:out[k]=float(v) if any(c in str(v).lower() for c in ".e") else int(v)
   except:out[k]=v
 return out

games=[]
with (PROCESSED/"games.csv").open(newline="",encoding="utf-8-sig") as f:games=list(csv.DictReader(f))
game_by_id={r["game_id"]:r for r in games}
team_game_box=defaultdict(lambda:{k:0 for k in COUNT});team_game_players=defaultdict(list)
with (PROCESSED/"player_game_stats.csv").open(newline="",encoding="utf-8-sig") as f:
 for r in csv.DictReader(f):
  x=team_game_box[(r["game_id"],r["team"])]
  for k in COUNT:x[k]+=n(r[k])
  team_game_players[(r["game_id"],r["team"])].append(r)

PAINT_FAMILIES={"Lay up","Floater","Hook","Alley oop","Dunk"}
paint=defaultdict(lambda:{"attempts":0,"makes":0,"points":0})
paint_allowed=defaultdict(lambda:{"attempts":0,"makes":0,"points":0})
second_chance_points=defaultdict(int);second_chance_points_allowed=defaultdict(int)
lead=defaultdict(lambda:{"seconds":0,"game_seconds":0})
events_by_game=defaultdict(list)
with (ANALYTICS/"play_by_play_enriched.csv").open(newline="",encoding="utf-8-sig") as f:
 for r in csv.DictReader(f):
  events_by_game[r["game_id"]].append(r)
  family=r["additional_data"].split(",")[0].strip() if r["additional_data"] else ""
  if r["is_field_goal_attempt"]=="True" and r["shot_value"]=="2" and family in PAINT_FAMILIES:
   x=paint[(r["season"],r["team"])]
   x["attempts"]+=1;x["makes"]+=r["shot_result"]=="made";x["points"]+=2*(r["shot_result"]=="made")
   g=game_by_id.get(r["game_id"])
   if g:
    defender=g["team_2"] if r["team"]==g["team_1"] else g["team_1"]
    dx=paint_allowed[(r["season"],defender)]
    dx["attempts"]+=1;dx["makes"]+=r["shot_result"]=="made";dx["points"]+=2*(r["shot_result"]=="made")
for game_id,rows in events_by_game.items():
 g=game_by_id.get(game_id)
 if not g:continue
 possessions=defaultdict(list)
 for r in rows:
  if r["team"] and r["possession_number"]:possessions[(r["team"],r["possession_number"])].append(r)
 for (team,_),possession in possessions.items():
  if not any(r["action"]=="Offensive rebound" for r in possession):continue
  points=sum(n(r["points_delta"]) for r in possession if r["team"]==team)
  defender=g["team_2"] if team==g["team_1"] else g["team_1"]
  second_chance_points[(g["season"],team)]+=points
  second_chance_points_allowed[(g["season"],defender)]+=points
 ordered=sorted(rows,key=lambda r:(n(r["game_seconds_elapsed"]),n(r["event_sequence"])))
 max_period=max((n(r["period_number"]) for r in ordered),default=4);duration=2400+max(0,max_period-4)*300
 lead[(g["season"],g["team_1"])]["game_seconds"]+=duration;lead[(g["season"],g["team_2"])]["game_seconds"]+=duration
 for i,r in enumerate(ordered):
  start=n(r["game_seconds_elapsed"]);end=n(ordered[i+1]["game_seconds_elapsed"]) if i+1<len(ordered) else duration
  span=max(0,end-start);s1=n(r["team_1_score_after"]);s2=n(r["team_2_score_after"])
  if s1>s2:lead[(g["season"],g["team_1"])]["seconds"]+=span
  elif s2>s1:lead[(g["season"],g["team_2"])]["seconds"]+=span

fingerprints={}
with (ANALYTICS/"broader_programme/team_tactical_fingerprints.csv").open(newline="",encoding="utf-8-sig") as f:
 for r in csv.DictReader(f):fingerprints[(r["season"],r["team"])]=numeric(r)
kills_by_team=defaultdict(int)
with (ANALYTICS/"advanced_decisions/kill_team_game.csv").open(newline="",encoding="utf-8-sig") as f:
 for r in csv.DictReader(f):kills_by_team[(r["season"],r["team"])]+=n(r["kills"])
play_types=defaultdict(list)
with (ANALYTICS/"broader_programme/team_play_type_shot_profile.csv").open(newline="",encoding="utf-8-sig") as f:
 for r in csv.DictReader(f):play_types[r["team"]].append(numeric(r))
player_seasons=defaultdict(list)
plus_minus_by_player=defaultdict(int)
with (PROCESSED/"player_plus_minus.csv").open(newline="",encoding="utf-8-sig") as f:
 for r in csv.DictReader(f):
  plus_minus_by_player[(r["season"],r["team"],canonical_player(r["player"]))]+=n(r["plus_minus"])
player_profile_source=json.loads((ROOT/"app/player-profiles.json").read_text(encoding="utf-8"))
on_off_fields=("on_minutes","off_minutes","on_plus_minus","off_plus_minus","on_plus_minus_per_40","off_plus_minus_per_40","on_off_plus_minus_per_40","team_relative_plus_minus_per_40","on_off_ci_low","on_off_ci_high","on_off_sample","offensive_rating","defensive_rating","offensive_win_shares","defensive_win_shares","win_shares","win_shares_per_40","team_win_share","adjustment_win_shares","adjusted_win_shares","adjusted_win_shares_per_40","adjusted_team_win_share")
on_off_by_player={(str(r["season"]),r["team"],p["name"]):{k:r.get(k) for k in on_off_fields} for p in player_profile_source["profiles"] for r in p["season_stats"]}
with (ANALYTICS/"broader_programme/player_impact_profiles.csv").open(newline="",encoding="utf-8-sig") as f:
 impact_rows=merge_player_season_rows([numeric(r) for r in csv.DictReader(f)])
 for r in impact_rows:
  key=(r["season"],r["team"],r["player_name"])
  if key not in plus_minus_by_player:
   raise ValueError(f"Missing official plus/minus for {key}")
  r["plus_minus"]=plus_minus_by_player[key]
  on_off_key=(r["season"],short_team(r["team"]),r["player_name"])
  if on_off_key not in on_off_by_player:
   raise ValueError(f"Missing same-game on/off for {on_off_key}")
  r.update(on_off_by_player[on_off_key])
  player_seasons[r["team"]].append(numeric(r))

profiles=[]
for bio in TEAMS:
 name=bio["dataset_name"];logs=[]
 for g in games:
  if name not in (g["team_1"],g["team_2"]):continue
  home=name==g["team_1"];own=n(g["score_1"] if home else g["score_2"]);opp=n(g["score_2"] if home else g["score_1"]);opponent=g["team_2"] if home else g["team_1"]
  box=team_game_box[(g["game_id"],name)]
  opponent_box=team_game_box[(g["game_id"],opponent)]
  row={**box,"season":g["season"],"game_id":g["game_id"],"date":g["game_date"],"opponent":opponent,"home_away":"Home" if home else "Away","points":own,"points_allowed":opp,"margin":own-opp,"result":"W" if own>opp else "L"}
  row["opponent_box"]=dict(opponent_box)
  row["bench_points"]=sum(n(r["points"]) for r in team_game_players[(g["game_id"],name)][5:])
  row["two_made"]=row["fg_made"]-row["three_made"];row["two_attempted"]=row["fg_attempted"]-row["three_attempted"]
  logs.append(row)
 grouped=defaultdict(list)
 for r in logs:grouped[r["season"]].append(r)
 seasons=[];defense_seasons=[]
 for season,rows in sorted(grouped.items()):
  x={"season":season,"games":len(rows),"wins":sum(r["result"]=="W" for r in rows),"losses":sum(r["result"]=="L" for r in rows),"points_allowed":sum(r["points_allowed"] for r in rows),"margin":sum(r["margin"] for r in rows)}
  for k in COUNT:x[k]=sum(r[k] for r in rows)
  x["points"]=sum(r["points"] for r in rows)
  x["two_made"]=x["fg_made"]-x["three_made"];x["two_attempted"]=x["fg_attempted"]-x["three_attempted"]
  for made,attempted,label in [("fg_made","fg_attempted","fg_percentage"),("two_made","two_attempted","two_percentage"),("three_made","three_attempted","three_percentage"),("ft_made","ft_attempted","ft_percentage")]:x[label]=x[made]/x[attempted] if x[attempted] else None
  x["win_percentage"]=x["wins"]/x["games"] if x["games"] else None;x["average_margin"]=x["margin"]/x["games"] if x["games"] else None
  seasons.append(x)
  d={"season":season,"games":len(rows)}
  for k in COUNT:d[k]=sum(r["opponent_box"][k] for r in rows)
  d["points"]=sum(r["points_allowed"] for r in rows)
  d["two_made"]=d["fg_made"]-d["three_made"];d["two_attempted"]=d["fg_attempted"]-d["three_attempted"]
  for made,attempted,label in [("fg_made","fg_attempted","fg_percentage"),("two_made","two_attempted","two_percentage"),("three_made","three_attempted","three_percentage"),("ft_made","ft_attempted","ft_percentage")]:d[label]=d[made]/d[attempted] if d[attempted] else None
  defense_seasons.append(d)
 latest=seasons[-1]
 short="UC Capitals" if name=="University of Canberra Capitals" else ("Southside Flyers" if name=="Southside Melbourne Flyers" else name.split()[0])
 advanced=[]
 for s in sorted(grouped):
  if (s,name) not in fingerprints:continue
  a=dict(fingerprints[(s,name)]);a["season"]=s;a["team"]=name;box=next(x for x in seasons if x["season"]==s);opp=next(x for x in defense_seasons if x["season"]==s);pip=paint[(s,name)];opp_pip=paint_allowed[(s,name)];lead_row=lead[(s,name)]
  a["offensive_rebound_percentage"]=box["offensive_rebounds"]/(box["offensive_rebounds"]+opp["defensive_rebounds"]) if box["offensive_rebounds"]+opp["defensive_rebounds"] else None
  a["defensive_rebound_percentage"]=box["defensive_rebounds"]/(box["defensive_rebounds"]+opp["offensive_rebounds"]) if box["defensive_rebounds"]+opp["offensive_rebounds"] else None
  a["free_throw_rate"]=box["ft_attempted"]/box["fg_attempted"] if box["fg_attempted"] else None
  a["three_point_rate"]=box["three_attempted"]/box["fg_attempted"] if box["fg_attempted"] else None
  a["effective_fg_percentage"]=(box["fg_made"]+.5*box["three_made"])/box["fg_attempted"] if box["fg_attempted"] else None
  a["points_in_paint"]=pip["points"];a["paint_attempts"]=pip["attempts"];a["paint_makes"]=pip["makes"]
  a["points_in_paint_share"]=pip["points"]/box["points"] if box["points"] else None
  a["paint_fg_percentage"]=pip["makes"]/pip["attempts"] if pip["attempts"] else None
  a["opponent_three_point_rate"]=opp["three_attempted"]/opp["fg_attempted"] if opp["fg_attempted"] else None
  a["opponent_free_throw_rate"]=opp["ft_attempted"]/opp["fg_attempted"] if opp["fg_attempted"] else None
  a["opponent_total_points"]=opp["points"]
  a["opponent_total_fga"]=opp["fg_attempted"]
  a["opponent_total_fta"]=opp["ft_attempted"]
  a["opponent_total_three_pa"]=opp["three_attempted"]
  a["opponent_points_in_paint"]=opp_pip["points"];a["opponent_paint_attempts"]=opp_pip["attempts"];a["opponent_paint_makes"]=opp_pip["makes"]
  a["opponent_points_in_paint_share"]=opp_pip["points"]/opp["points"] if opp["points"] else None
  a["opponent_paint_fg_percentage"]=opp_pip["makes"]/opp_pip["attempts"] if opp_pip["attempts"] else None
  a["second_chance_points"]=second_chance_points[(s,name)]
  a["opponent_second_chance_points"]=second_chance_points_allowed[(s,name)]
  a["kills"]=kills_by_team[(s,name)]
  a["kills_per_game"]=a["kills"]/box["games"] if box["games"] else None
  a["bench_points"]=sum(r["bench_points"] for r in grouped[s]);a["bench_points_share"]=a["bench_points"]/box["points"] if box["points"] else None
  a["time_leading_share"]=lead_row["seconds"]/lead_row["game_seconds"] if lead_row["game_seconds"] else None
  a["time_leading_seconds"]=lead_row["seconds"];a["recorded_game_seconds"]=lead_row["game_seconds"]
  a["total_points"]=box["points"];a["total_fouls"]=box["fouls"];a["total_fga"]=box["fg_attempted"];a["total_fgm"]=box["fg_made"];a["total_three_pa"]=box["three_attempted"];a["total_three_pm"]=box["three_made"];a["total_fta"]=box["ft_attempted"]
  a["total_offensive_rebounds"]=box["offensive_rebounds"];a["opponent_defensive_rebounds"]=opp["defensive_rebounds"];a["total_defensive_rebounds"]=box["defensive_rebounds"];a["opponent_offensive_rebounds"]=opp["offensive_rebounds"]
  advanced.append(a)
 profiles.append({**bio,"coach_source":COACH_SOURCE,"latest_record":{"season":latest["season"],"wins":latest["wins"],"losses":latest["losses"],"games":latest["games"]},"season_stats":seasons,"defense_season_stats":defense_seasons,"advanced":advanced,"play_types":play_types[name],"defense_play_types":[r for r in DEFENSE["play_types"] if r["team"]==short],"defense_shot_types":[r for r in DEFENSE["shot_types"] if r["team"]==short],"players":player_seasons[name],"game_log":sorted(logs,key=lambda r:(r["date"],int(r["game_id"])),reverse=True)})

for season in sorted({r["season"] for p in profiles for r in p["season_stats"]}):
 season_profiles=[p for p in profiles if any(r["season"]==season for r in p["season_stats"])]
 season_rows=[next(r for r in p["season_stats"] if r["season"]==season) for p in season_profiles]
 expected_per_game=sum(r["fouls"] for r in season_rows)/sum(r["games"] for r in season_rows)
 for p in season_profiles:
  box=next(r for r in p["season_stats"] if r["season"]==season)
  a=next((r for r in p["advanced"] if r["season"]==season),None)
  if a is None:
   raise ValueError(f"Missing advanced fingerprint for {p['name']} {season}")
  a["expected_fouls"]=expected_per_game*box["games"];a["fouls_above_expected"]=box["fouls"]-a["expected_fouls"]

player_profiles=json.loads((ROOT/"app/player-profiles.json").read_text(encoding="utf-8"))
team_slugs={x["dataset_name"]:x["slug"] for x in TEAMS}|{x["dataset_name"].split()[0] if x["dataset_name"]!="University of Canberra Capitals" else "Canberra":x["slug"] for x in TEAMS}
team_slugs.update({"UC Capitals":"canberra-capitals","Southside Flyers":"southside-melbourne-flyers","Southside":"southside-melbourne-flyers"})
out={"profiles":profiles,"slugs":team_slugs,"player_slugs":player_profiles["slugs"],"coach_source":COACH_SOURCE,"logo_source":"https://www.wnbl.com.au/players"}
(ROOT/"app/team-profiles.json").write_text(json.dumps(out,separators=(",",":"),ensure_ascii=False),encoding="utf-8")
print({p["name"]:f'{p["latest_record"]["wins"]}-{p["latest_record"]["losses"]}' for p in profiles})
