import csv,json,math,statistics
from collections import defaultdict
from pathlib import Path
from player_identity import canonical_player

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT.parent/"outputs/WNBL_Data_Collector/wnbl_dataset"
AN=DATA/"analytics";BP=AN/"broader_programme";PR=DATA/"processed"

def rows(path):
 with path.open(newline="",encoding="utf-8-sig") as f:return list(csv.DictReader(f))
def n(v):
 try:return float(v)
 except:return 0.0
def minutes(v):
 try:
  m,s=v.split(":");return int(m)+int(s)/60
 except:return 0.0
def short(t):
 return "UC Capitals" if t=="University of Canberra Capitals" else "Southside Flyers" if t=="Southside Melbourne Flyers" else t.split()[0]
def clean(r):
 out={}
 for k,v in r.items():
  if v in ("",None):out[k]=None
  else:
   try:
    x=float(v);out[k]=int(x) if x.is_integer() else x
   except:out[k]=short(v) if k in ("team","offense_team","defense_team","similar_team") else canonical_player(v) if k in ("player_name","assister_name","scorer_name","primary_assister","leading_scorer","leading_creator") else v
 return out

games=rows(PR/"games.csv");game={g["game_id"]:g for g in games}
profiles=json.loads((ROOT/"app/data.json").read_text())

# 6. Creator–scorer connections.
connections=sorted(profiles["chemistry"],key=lambda r:(r["connection_lift"] or 0,r["assisted_makes"]),reverse=True)

# Individual creation credits. "Action-created" points are a transparent
# secondary-creation proxy: made PnR, PnP and hand-off shots with no official
# assist, credited to the teammate explicitly recorded on that action.
events=rows(AN/"play_by_play_enriched.csv")
label_name={}
for r in events:
 if r["player_label"] and r["player_name"]:label_name[(r["game_id"],short(r["team"]),r["player_label"])]=canonical_player(r["player_name"])
action_points=defaultdict(float)
for r in events:
 if r["shot_result"]!="made" or r["assisted_by"] or r["play_type"] not in ("Pick'n'Roll","Pick'n'pop","Hand offs") or not r["teammate"]:continue
 team=short(r["team"]);creator=label_name.get((r["game_id"],team,r["teammate"]))
 if creator and creator!=canonical_player(r["player_name"]):action_points[(r["season"],team,creator)]+=n(r["shot_value"])
direct={(r["season"],r["team"],r["assister_name"]):n(r["points_created"]) for r in profiles["creators"]}
box_points={(r["season"],r["team"],r["player_name"]):n(r["points"]) for r in profiles["players"]}
creation_dependency=[]
creation_keys=set(box_points)|set(direct)|set(action_points)
by_team_creation=defaultdict(float)
for key in creation_keys:by_team_creation[key[:2]]+=box_points.get(key,0)+direct.get(key,0)+action_points.get(key,0)
for key in creation_keys:
 own=box_points.get(key,0);assisted=direct.get(key,0);action=action_points.get(key,0);total=own+assisted+action
 creation_dependency.append({"season":key[0],"team":key[1],"player_name":key[2],"points_scored":own,"direct_assist_points_created":assisted,"action_created_points":action,"total_points_created":total,"creation_dependency_share":total/by_team_creation[key[:2]] if by_team_creation[key[:2]] else None})

# 7. Offensive dependence and resilience.
pg=rows(PR/"player_game_stats.csv")
season_player=defaultdict(lambda:defaultdict(float))
game_player=defaultdict(float)
for r in pg:
 player=canonical_player(r["player"]);key=(r["season"],short(r["team"]));season_player[key][player]+=n(r["points"])
 game_player[(r["season"],r["game_id"],short(r["team"]),player)]+=n(r["points"])
leaders={k:max(v,key=v.get) for k,v in season_player.items() if v}
team_games=defaultdict(list)
for g in games:
 if not g["score_1"] or not g["score_2"]:continue
 for team,own,opp in [(short(g["team_1"]),n(g["score_1"]),n(g["score_2"])),(short(g["team_2"]),n(g["score_2"]),n(g["score_1"]))]:
  team_games[(g["season"],team)].append((g["game_id"],own>opp,own,opp))
dependence=[]
dependence_top_two=[]
network={(r["season"],r["team"]):r for r in profiles["networkStructure"]}
for key,gs in team_games.items():
 leader=leaders.get(key);total=sum(season_player[key].values());lead_total=season_player[key].get(leader,0);ppg=lead_total/len(gs) if gs else 0
 low=[x for x in gs if game_player[(key[0],x[0],key[1],leader)]<ppg]
 high=[x for x in gs if game_player[(key[0],x[0],key[1],leader)]>=ppg]
 net=network.get(key,{})
 dependence.append({"season":key[0],"team":key[1],"leading_scorer":leader,"leading_scorer_share":lead_total/total if total else None,"largest_assist_edge_share":net.get("largest_edge_share"),"assist_hhi":net.get("assist_edge_hhi"),"network_density":net.get("network_density"),"below_average_games":len(low),"below_average_win_rate":sum(x[1] for x in low)/len(low) if low else None,"at_or_above_games":len(high),"at_or_above_win_rate":sum(x[1] for x in high)/len(high) if high else None})
 top_two=sorted(season_player[key],key=season_player[key].get,reverse=True)[:2]
 combined_points=sum(season_player[key][player] for player in top_two)
 combined_ppg=combined_points/len(gs) if gs else 0
 top_two_low=[x for x in gs if sum(game_player[(key[0],x[0],key[1],player)] for player in top_two)<combined_ppg]
 top_two_high=[x for x in gs if sum(game_player[(key[0],x[0],key[1],player)] for player in top_two)>=combined_ppg]
 dependence_top_two.append({"season":key[0],"team":key[1],"top_two_players":" + ".join(top_two),"combined_points":combined_points,"combined_scoring_share":combined_points/total if total else None,"below_average_games":len(top_two_low),"below_average_win_rate":sum(x[1] for x in top_two_low)/len(top_two_low) if top_two_low else None,"at_or_above_games":len(top_two_high),"at_or_above_win_rate":sum(x[1] for x in top_two_high)/len(top_two_high) if top_two_high else None})

# 9. Scoring-run anatomy from consecutive scoring events.
by_game=defaultdict(list)
for r in events:by_game[r["game_id"]].append(r)
run_rows=[]
for gid,evs in by_game.items():
 g=game.get(gid)
 if not g:continue
 current=None;points=0;start=None;end=None;events_n=0
 def finish():
  if current and points>=8:
   won=(current==short(g["team_1"]) and n(g["score_1"])>n(g["score_2"])) or (current==short(g["team_2"]) and n(g["score_2"])>n(g["score_1"]))
   run_rows.append({"season":g["season"],"team":current,"game_id":gid,"run_points":points,"duration_seconds":max(0,(end or 0)-(start or 0)),"scoring_events":events_n,"won":won})
 for r in sorted(evs,key=lambda x:n(x["event_sequence"])):
  pts=n(r["points_delta"])
  if pts<=0 or not r["team"]:continue
  team=short(r["team"]);elapsed=n(r["game_seconds_elapsed"])
  if team!=current:
   finish();current=team;points=0;start=elapsed;events_n=0
  points+=pts;end=elapsed;events_n+=1
 finish()
run_groups=defaultdict(list)
for r in run_rows:run_groups[(r["season"],r["team"])].append(r)
runs=[]
for k,v in run_groups.items():
 largest=max(v,key=lambda x:x["run_points"])
 runs.append({"season":k[0],"team":k[1],"runs_8_plus":len(v),"runs_per_game":len(v)/len(team_games[k]) if team_games[k] else 0,"average_run":sum(x["run_points"] for x in v)/len(v),"largest_run":largest["run_points"],"largest_run_game_id":largest["game_id"],"average_duration_seconds":sum(x["duration_seconds"] for x in v)/len(v),"share_in_wins":sum(x["won"] for x in v)/len(v)})

# 11. Offensive-rebound decision tree.
oreb_detail=[clean(r) for r in rows(BP/"oreb_extension_context_detail.csv")]
def aggregate_oreb(key):
 groups=defaultdict(list)
 for r in oreb_detail:
  label=r.get(key) or "Unclear"
  if str(label).strip().lower() in ("none","unspecified","unavailable"):label="Unclear"
  groups[label].append(r)
 return [{"label":k,"extensions":len(v),"synergy_play_possessions":sum(n(x.get("extension_synergy_play_possessions")) for x in v),"multiple_rate":sum(bool(x["multiple_extension"] in (True,"True")) for x in v)/len(v),"scoring_rate":sum(bool(x["extension_scored"] in (True,"True")) for x in v)/len(v),"points_per_extension":sum(n(x["extension_points"]) for x in v)/sum(n(x.get("extension_synergy_play_possessions")) for x in v) if sum(n(x.get("extension_synergy_play_possessions")) for x in v) else None,"mean_seconds_to_next_attempt":sum(n(x["seconds_to_next_attempt"]) for x in v)/max(1,sum(x["seconds_to_next_attempt"] is not None for x in v))} for k,v in groups.items()]
oreb={"attack_type":aggregate_oreb("attack_type"),"shot_family":aggregate_oreb("next_shot_family"),"play_type":aggregate_oreb("next_shot_play_type")}

# 18 and 19. Score pressure and quarter profiles.
poss=rows(AN/"possessions.csv")
pressure=defaultdict(lambda:{"team_possessions":0,"possessions":0,"points":0,"turnovers":0,"oreb":0})
quarters=defaultdict(lambda:{"team_possessions":0,"possessions":0,"points":0,"turnovers":0,"oreb":0})
for r in poss:
 team=short(r["offense_team"]);margin=n(r["offense_margin_at_start"]);state="Leading" if margin>0 else "Trailing" if margin<0 else "Tied";a=abs(margin);band="0–3" if a<=3 else "4–8" if a<=8 else "9+"
 for d,key in [(pressure,(r["season"],team,state,band)),(quarters,(r["season"],team,int(n(r["period_number"]))))]:
  x=d[key];x["team_possessions"]+=1;x["possessions"]+=n(r.get("synergy_play_possessions"));x["points"]+=n(r["points"]);x["turnovers"]+=bool(r["turnover_type"]);x["oreb"]+=r["has_offensive_rebound_extension"]=="True"
def finish_groups(d,names):
 out=[]
 for key,x in d.items():
  p=x["possessions"];out.append({**dict(zip(names,key)),**x,"ppp":x["points"]/p if p else None,"turnover_rate":x["turnovers"]/p if p else None,"oreb_extension_rate":x["oreb"]/p if p else None})
 return out
score_pressure=finish_groups(pressure,["season","team","score_state","margin_band"])
quarter_profiles=finish_groups(quarters,["season","team","period"])

# 20. Sustainable performance indicators.
tg=defaultdict(lambda:{"games":0,"wins":0,"points":0,"allowed":0,"three_rates":[],"close_games":0,"close_wins":0})
for key,gs in team_games.items():
 x=tg[key]
 for gid,win,own,opp in gs:x["games"]+=1;x["wins"]+=win;x["points"]+=own;x["allowed"]+=opp;x["close_games"]+=abs(own-opp)<=5;x["close_wins"]+=win and abs(own-opp)<=5
game_shoot=defaultdict(lambda:[0,0])
for r in pg:
 k=(r["season"],r["game_id"],short(r["team"]));game_shoot[k][0]+=n(r["three_made"]);game_shoot[k][1]+=n(r["three_attempted"])
for (season,gid,team),(m,a) in game_shoot.items():
 if a:tg[(season,team)]["three_rates"].append(m/a)
sustainability=[]
for key,x in tg.items():
 pf=x["points"]/x["games"];pa=x["allowed"]/x["games"];pyth=pf**11.5/(pf**11.5+pa**11.5) if pf+pa else .5
 sustainability.append({"season":key[0],"team":key[1],"games":x["games"],"win_rate":x["wins"]/x["games"],"expected_win_rate":pyth,"wins_above_expected":x["wins"]-pyth*x["games"],"three_point_game_sd":statistics.pstdev(x["three_rates"]) if len(x["three_rates"])>1 else None,"close_games":x["close_games"],"close_win_rate":x["close_wins"]/x["close_games"] if x["close_games"] else None})

# Season-to-season roster continuity and early results. The primary measure is
# backward-looking: the share of the prior season's minutes belonging to players
# who appeared for the same team in the next season. This avoids giving a fringe
# returner the same weight as a major rotation player.
seasons=profiles["meta"]["seasons"]
rosters=defaultdict(lambda:defaultdict(lambda:{"minutes":0.0,"points":0.0,"games":0}))
player_game_minutes=defaultdict(float)
for r in pg:
 key=(r["season"],short(r["team"]),canonical_player(r["player"]));rosters[key[:2]][key[2]]["minutes"]+=minutes(r["minutes"]);rosters[key[:2]][key[2]]["points"]+=n(r["points"]);rosters[key[:2]][key[2]]["games"]+=1
 player_game_minutes[(r["season"],r["game_id"],short(r["team"]),canonical_player(r["player"]))]+=minutes(r["minutes"])
dated_games=defaultdict(list)
for g in games:
 if not g["score_1"] or not g["score_2"]:continue
 for team,own,opp in [(short(g["team_1"]),n(g["score_1"]),n(g["score_2"])),(short(g["team_2"]),n(g["score_2"]),n(g["score_1"]))]:dated_games[(g["season"],team)].append({"date":g["game_date"],"game_id":g["game_id"],"win":own>opp,"margin":own-opp})
continuity=[]
for i in range(1,len(seasons)):
 previous,season=seasons[i-1],seasons[i]
 for team in sorted(t for s,t in dated_games if s==season):
  prior,current=rosters[(previous,team)],rosters[(season,team)];returners=set(prior)&set(current);prior_minutes=sum(x["minutes"] for x in prior.values());prior_points=sum(x["points"] for x in prior.values());ordered=sorted(dated_games[(season,team)],key=lambda x:(x["date"],x["game_id"]));early=ordered[:8];next_five=ordered[8:13]
  early_ids={x["game_id"] for x in early};early_minutes=defaultdict(float)
  for (s,gid,t,player),value in player_game_minutes.items():
   if s==season and t==team and gid in early_ids:early_minutes[player]+=value
  top_five=sorted(prior,key=lambda x:prior[x]["minutes"],reverse=True)[:5]
  def rate(rows,key):return sum(x[key] for x in rows)/len(rows) if rows else None
  continuity.append({"season":season,"prior_season":previous,"team":team,"prior_roster_players":len(prior),"returning_players":len(returners),"returning_player_rate":len(returners)/len(prior) if prior else None,"core_returners":sum(x in returners for x in top_five),"prior_minutes_retained":sum(prior[x]["minutes"] for x in returners)/prior_minutes if prior_minutes else None,"prior_points_retained":sum(prior[x]["points"] for x in returners)/prior_points if prior_points else None,"early_rotation_continuity":sum(v for p,v in early_minutes.items() if p in returners)/sum(early_minutes.values()) if early_minutes else None,"early_games":len(early),"early_wins":sum(x["win"] for x in early),"early_losses":sum(not x["win"] for x in early),"early_win_rate":rate(early,"win"),"early_average_margin":rate(early,"margin"),"next_five_win_rate":rate(next_five,"win"),"full_season_win_rate":rate(ordered,"win"),"full_season_average_margin":rate(ordered,"margin")})
def correlation(xs,ys):
 mx,my=statistics.mean(xs),statistics.mean(ys);den=(sum((x-mx)**2 for x in xs)*sum((y-my)**2 for y in ys))**.5
 return sum((x-mx)*(y-my) for x,y in zip(xs,ys))/den if den else None
def slope(xs,ys):
 mx,my=statistics.mean(xs),statistics.mean(ys);den=sum((x-mx)**2 for x in xs)
 return sum((x-mx)*(y-my) for x,y in zip(xs,ys))/den if den else None
def adjusted_slope(rows,outcome):
 # Frisch-Waugh residualisation: season fixed effects plus prior-season margin.
 groups=defaultdict(list)
 for r in rows:groups[r["season"]].append(r)
 x=[];y=[];z=[]
 for group in groups.values():
  mx=statistics.mean(r["prior_minutes_retained"] for r in group);my=statistics.mean(r[outcome] for r in group);mz=statistics.mean(r["prior_season_average_margin"] for r in group)
  x.extend(r["prior_minutes_retained"]-mx for r in group);y.extend(r[outcome]-my for r in group);z.extend(r["prior_season_average_margin"]-mz for r in group)
 sxx=sum(a*a for a in x);szz=sum(a*a for a in z);sxz=sum(a*b for a,b in zip(x,z));sxy=sum(a*b for a,b in zip(x,y));szy=sum(a*b for a,b in zip(z,y));den=sxx*szz-sxz*sxz
 return (sxy*szz-sxz*szy)/den if den else None
for r in continuity:
 prior_games=dated_games[(r["prior_season"],r["team"])];r["prior_season_win_rate"]=sum(x["win"] for x in prior_games)/len(prior_games);r["prior_season_average_margin"]=sum(x["margin"] for x in prior_games)/len(prior_games)
ordered_continuity=sorted(continuity,key=lambda x:x["prior_minutes_retained"])
continuity_bins=[]
for index,label in enumerate(("Low","Middle","High")):
 group=ordered_continuity[index*len(ordered_continuity)//3:(index+1)*len(ordered_continuity)//3]
 continuity_bins.append({"group":label,"team_seasons":len(group),"minimum_continuity":min(x["prior_minutes_retained"] for x in group),"maximum_continuity":max(x["prior_minutes_retained"] for x in group),"average_continuity":statistics.mean(x["prior_minutes_retained"] for x in group),"early_win_rate":statistics.mean(x["early_win_rate"] for x in group),"early_average_margin":statistics.mean(x["early_average_margin"] for x in group),"full_season_win_rate":statistics.mean(x["full_season_win_rate"] for x in group)})
x=[r["prior_minutes_retained"] for r in continuity];early_win=[r["early_win_rate"] for r in continuity];early_margin=[r["early_average_margin"] for r in continuity]
high=[r for r in continuity if r["prior_minutes_retained"]>=.6];low=[r for r in continuity if r["prior_minutes_retained"]<.6]
continuity_summary={"team_seasons":len(continuity),"early_games":sum(r["early_games"] for r in continuity),"early_definition_games":8,"average_prior_minutes_retained":statistics.mean(x),"early_win_correlation":correlation(x,early_win),"early_margin_correlation":correlation(x,early_margin),"next_five_win_correlation":correlation(x,[r["next_five_win_rate"] for r in continuity]),"full_season_win_correlation":correlation(x,[r["full_season_win_rate"] for r in continuity]),"full_season_margin_correlation":correlation(x,[r["full_season_average_margin"] for r in continuity]),"raw_win_rate_change_per_10pp":slope(x,early_win)*.1,"raw_margin_change_per_10pp":slope(x,early_margin)*.1,"adjusted_win_rate_change_per_10pp":adjusted_slope(continuity,"early_win_rate")*.1,"adjusted_margin_change_per_10pp":adjusted_slope(continuity,"early_average_margin")*.1,"high_continuity_cutoff":.6,"high_continuity_team_seasons":len(high),"high_continuity_early_win_rate":statistics.mean(r["early_win_rate"] for r in high),"high_continuity_early_margin":statistics.mean(r["early_average_margin"] for r in high),"lower_continuity_team_seasons":len(low),"lower_continuity_early_win_rate":statistics.mean(r["early_win_rate"] for r in low),"lower_continuity_early_margin":statistics.mean(r["early_average_margin"] for r in low)}
continuity_sensitivity=[]
for count in (3,5,8):
 win_rates=[];margins=[]
 for r in continuity:
  sample=sorted(dated_games[(r["season"],r["team"])],key=lambda x:(x["date"],x["game_id"]))[:count];win_rates.append(sum(x["win"] for x in sample)/len(sample));margins.append(sum(x["margin"] for x in sample)/len(sample))
 continuity_sensitivity.append({"games":count,"team_seasons":len(continuity),"win_rate_correlation":correlation(x,win_rates),"margin_correlation":correlation(x,margins),"win_rate_change_per_10pp":slope(x,win_rates)*.1,"margin_change_per_10pp":slope(x,margins)*.1})
identity_audit=[
 {"source_name":"Miela Goodchild","canonical_name":"Miela Sowah","classification":"Confirmed name change","basis":"Married name confirmed for this project","action":"Merged"},
 {"source_name":"Chantel Anais Horvat","canonical_name":"Chantel-Anais Horvat","classification":"Punctuation variant","basis":"Same full name apart from hyphenation","action":"Merged"},
 {"source_name":"Chelsea Brooks","canonical_name":"Chelsea Brook","classification":"Likely source typo","basis":"Same Adelaide team and no. 8; WNBL media guides use Chelsea Brook","action":"Merged"},
 {"source_name":"Abby Kate Bishop","canonical_name":"Abby Bishop","classification":"Full / shortened name","basis":"Same player name and Southside no. 10","action":"Merged"},
 {"source_name":"Isabel Borlase","canonical_name":"Isobel Borlase","classification":"Likely source typo","basis":"Official Basketball Australia spelling is Isobel","action":"Merged"},
 {"source_name":"Kristy Anne Wallace","canonical_name":"Kristy Wallace","classification":"Full / shortened name","basis":"Same Geelong player and no. 3","action":"Merged"},
 {"source_name":"Caitlin Martin","canonical_name":"Caitlyn Martin","classification":"Likely source spelling variant","basis":"Same Sydney player and no. 12; Basketball Australia uses Caitlyn","action":"Merged"},
]

# 21, 22 and 24. Rebuild role changes from the current seven-season player
# profiles so the latest season and canonical player names are included.
season_order={s:i for i,s in enumerate(profiles["meta"]["seasons"])}
development_base={}
for raw in profiles["development"]:
 r=clean(raw);r["player_name"]=canonical_player(r["player_name"]);key=(r["season"],r["player_name"])
 if key not in development_base or n(r.get("points_created"))>n(development_base[key].get("points_created")):development_base[key]=r
development=[]
by_player=defaultdict(list)
for r in development_base.values():by_player[r["player_name"]].append(r)
for player,player_rows in by_player.items():
 ordered=sorted(player_rows,key=lambda r:season_order.get(r["season"],999))
 for previous,current in zip(ordered,ordered[1:]):
  row=dict(current);row["previous_season"]=previous["season"]
  for field in ("points_created","observed_assists","scorer_partners","play_types_created","assisted_make_share"):
   row["change_in_"+field]=n(current.get(field))-n(previous.get(field))
  development.append(row)
style=[clean(r) for r in rows(BP/"team_tactical_fingerprints.csv")]
similarity=[clean(r) for r in rows(BP/"team_style_similarity.csv") if r["comparison_rank"]=="1"]
thresholds=profiles["selectedThresholds"];threshold_combinations=profiles["thresholdCombinations"]

for r in dependence:
 candidates=[x for x in creation_dependency if x["season"]==r["season"] and x["team"]==r["team"]]
 if candidates:
  leader=max(candidates,key=lambda x:x["total_points_created"])
  r.update({"leading_creator":leader["player_name"],"leading_creator_total":leader["total_points_created"],"creation_dependency_share":leader["creation_dependency_share"]})
out={"meta":profiles["meta"],"connections":connections,"creation_dependency":creation_dependency,"dependence":dependence,"dependence_top_two":dependence_top_two,"runs":runs,"oreb":oreb,"score_pressure":score_pressure,"quarter_profiles":quarter_profiles,"sustainability":sustainability,"continuity":continuity,"continuity_bins":continuity_bins,"continuity_summary":continuity_summary,"continuity_sensitivity":continuity_sensitivity,"identity_audit":identity_audit,"development":development,"style":style,"similarity":similarity,"thresholds":thresholds,"threshold_combinations":threshold_combinations}
(ROOT/"app/deep-dives.json").write_text(json.dumps(out,separators=(",",":")),encoding="utf-8")
print(json.dumps({k:len(v) if isinstance(v,(list,dict)) else 1 for k,v in out.items() if k!="meta"},indent=2))
