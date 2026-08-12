import csv,json,re
from collections import Counter,defaultdict
from pathlib import Path
from player_identity import canonical_player

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT.parent/"outputs/WNBL_Data_Collector/wnbl_dataset"
PBP=DATA/"analytics/play_by_play_enriched.csv"
STATS=DATA/"processed/player_game_stats.csv"
GAMES=DATA/"processed/games.csv"

def n(v):
    try:return int(float(v))
    except:return 0
def clean(v):return re.sub(r"[^a-z0-9]","",(v or "").lower())
def shot_family(v):
    token=(v or "").split(",")[0].strip()
    return token if token in {"Lay up","Jumper","Floater","Hook","Alley oop"} else "Unspecified"
def short_team(name):
    if name=="University of Canberra Capitals":return "UC Capitals"
    if name=="Southside Melbourne Flyers":return "Southside Flyers"
    return name.split()[0] if name else name

game_teams={}
with GAMES.open(newline="",encoding="utf-8-sig") as f:
    for r in csv.DictReader(f):game_teams[r["game_id"]]=(r["team_1"],r["team_2"])

rosters=defaultdict(list);player_games=Counter()
with STATS.open(newline="",encoding="utf-8-sig") as f:
    for r in csv.DictReader(f):
        row={"name":canonical_player(r["player"]),"jersey":clean(r["jersey_number"]),"team":r["team"],"season":r["season"]}
        rosters[(r["game_id"],r["team"])].append(row);player_games[(r["season"],r["team"],canonical_player(r["player"]))]+=1

def defender_team(game_id,off_team):
    teams=game_teams.get(game_id,())
    return next((x for x in teams if x!=off_team),"")

def resolve(label,candidates):
    m=re.match(r"^\s*(\d+)?\s*([A-Za-z])?\.?\s*(.+?)\s*$",label or "")
    if not m:return None,"unmatched"
    jersey,initial,surname=m.groups();surname=clean(surname);initial=clean(initial)
    def name_ok(c):
        bits=c["name"].split();return bool(bits) and clean(bits[-1])==surname and (not initial or clean(bits[0]).startswith(initial))
    exact=[c for c in candidates if name_ok(c) and (not jersey or c["jersey"]==clean(jersey))]
    if len(exact)==1:return exact[0],"exact_jersey_name"
    named=[c for c in candidates if name_ok(c)]
    if len(named)==1:return named[0],"exact_name"
    numbered=[c for c in candidates if jersey and c["jersey"]==clean(jersey)]
    if len(numbered)==1:return numbered[0],"unique_jersey"
    return None,"ambiguous" if exact or named or numbered else "unmatched"

with PBP.open(newline="",encoding="utf-8-sig") as f:events=list(csv.DictReader(f))
shots=[];mapping=Counter();tagged=0
for i,r in enumerate(events):
    if r["is_shot_opportunity"]!="True":continue
    label=r["opponent"].strip()
    if not label: mapping["missing"]+=1;continue
    tagged+=1;dteam=defender_team(r["game_id"],r["team"]);defender,confidence=resolve(label,rosters[(r["game_id"],dteam)])
    mapping[confidence]+=1
    if not defender:continue
    points=n(r["points_delta"])
    foul=r["shot_result"]=="shooting_foul" or "Fouled" in r["action"] or "made and one" in r["action"].lower()
    if foul:
        j=i+1
        while j<len(events) and events[j]["game_id"]==r["game_id"] and events[j]["action"].startswith("FT "):
            if events[j]["team"]==r["team"]:points+=n(events[j]["points_delta"])
            j+=1
    fga=r["is_field_goal_attempt"]=="True";made=fga and r["shot_result"]=="made";value=n(r["shot_value"])
    contest="Uncontested" if "Uncontested" in r["additional_data"] else ("Contested" if "Contested" in r["additional_data"] else "Unknown")
    shots.append({"season":r["season"],"game_id":r["game_id"],"date":r["game_date"],"defender":defender["name"],"defender_team":dteam,
      "shooter":canonical_player(r["player_name"]),"offense_team":r["team"],"play_type":r["play_type"] or "Unclassified","shot_type":shot_family(r["additional_data"]),
      "contest":contest,"shot_value":value,"fga":int(fga),"make":int(made),"foul":int(foul),"stop":int(fga and not made),"points":points,"mapping_confidence":confidence})

season_tot=defaultdict(lambda:[0,0]);context_tot=defaultdict(lambda:[0,0]);shooter_tot=defaultdict(lambda:[0,0])
for r in shots:
    season_tot[r["season"]][0]+=r["points"];season_tot[r["season"]][1]+=1
    context=(r["season"],r["shot_value"],r["shot_type"],r["play_type"],r["contest"])
    context_tot[context][0]+=r["points"];context_tot[context][1]+=1
    shooter_tot[(r["season"],r["shooter"])][0]+=r["points"];shooter_tot[(r["season"],r["shooter"])][1]+=1
for r in shots:
    sp,sn=season_tot[r["season"]];base=sp/sn if sn else 0
    cp,cn=context_tot[(r["season"],r["shot_value"],r["shot_type"],r["play_type"],r["contest"])]
    hp,hn=shooter_tot[(r["season"],r["shooter"])]
    context_rate=(cp+40*base)/(cn+40);shooter_rate=(hp+75*base)/(hn+75)
    r["expected_points"]=(context_rate+shooter_rate)/2

def blank():return {"opportunities":0,"fga":0,"fgm":0,"two_pa":0,"two_pm":0,"three_pa":0,"three_pm":0,"fouls":0,"contested":0,"stops":0,"points_allowed":0,"expected_points":0.0,"matchups":Counter(),"plays":set()}
def add(x,r):
    x["opportunities"]+=1;x["fga"]+=r["fga"];x["fgm"]+=r["make"];x["fouls"]+=r["foul"];x["contested"]+=r["contest"]=="Contested";x["stops"]+=r["stop"]
    x["points_allowed"]+=r["points"];x["expected_points"]+=r["expected_points"];x["matchups"][r["shooter"]]+=1;x["plays"].add(r["play_type"])
    if r["shot_value"]==2:x["two_pa"]+=r["fga"];x["two_pm"]+=r["make"]
    if r["shot_value"]==3:x["three_pa"]+=r["fga"];x["three_pm"]+=r["make"]
def finish(x,season,team,defender,label=None):
    opp=x["opportunities"];fga=x["fga"];saved=x["expected_points"]-x["points_allowed"]
    out={"season":season,"team":short_team(team),"player_name":defender,"games":player_games[(season,team,defender)],**{k:x[k] for k in ["opportunities","fga","fgm","two_pa","two_pm","three_pa","three_pm","fouls","contested","stops","points_allowed"]},
      "defended_fg_percentage":x["fgm"]/fga if fga else None,"defended_two_percentage":x["two_pm"]/x["two_pa"] if x["two_pa"] else None,"defended_three_percentage":x["three_pm"]/x["three_pa"] if x["three_pa"] else None,
      "points_per_opportunity":x["points_allowed"]/opp if opp else None,"shooting_foul_rate":x["fouls"]/opp if opp else None,"contested_rate":x["contested"]/opp if opp else None,"stop_rate":x["stops"]/opp if opp else None,
      "expected_points":x["expected_points"],"expected_points_per_opportunity":x["expected_points"]/opp if opp else None,"points_saved":saved,"points_saved_per_100":saved/opp*100 if opp else None,"stabilized_points_saved_per_100":(saved/opp*100)*(opp/(opp+150)) if opp else None,
      "unique_matchups":len(x["matchups"]),"top_matchup_share":max(x["matchups"].values(),default=0)/opp if opp else None,"play_types_faced":len(x["plays"])}
    if label is not None:out["label"]=label
    return out

players=defaultdict(blank);matchups=defaultdict(blank);plays=defaultdict(blank);types=defaultdict(blank)
for r in shots:
    key=(r["season"],r["defender_team"],r["defender"]);add(players[key],r);add(matchups[key+(r["shooter"],)],r);add(plays[key+(r["play_type"],)],r);add(types[key+(r["shot_type"],)],r)
player_rows=[finish(x,*k) for k,x in players.items()]
def details(groups):return [finish(x,k[0],k[1],k[2],k[3]) for k,x in groups.items()]
audit={"total_events":len(events),"shot_opportunities":sum(1 for r in events if r["is_shot_opportunity"]=="True"),"tagged_shot_opportunities":tagged,"resolved_shot_opportunities":len(shots),"mapping":dict(mapping)}
out={"audit":audit,"player_seasons":sorted(player_rows,key=lambda r:(r["season"],r["team"],r["player_name"])),"matchups":details(matchups),"play_types":details(plays),"shot_types":details(types)}
(ROOT/"app/defense.json").write_text(json.dumps(out,separators=(",",":"),ensure_ascii=False),encoding="utf-8")
print(audit)
