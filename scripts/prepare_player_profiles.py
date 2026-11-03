import csv,hashlib,json,random,re
from collections import defaultdict
from pathlib import Path
from player_identity import ALIASES,canonical_player,player_aliases

ROOT=Path(__file__).resolve().parents[1]
PROCESSED=ROOT.parent/"outputs/WNBL_Data_Collector/wnbl_dataset/processed"
ENRICHED=ROOT.parent/"outputs/WNBL_Data_Collector/wnbl_dataset/analytics/play_by_play_enriched.csv"
DEFENSE=json.loads((ROOT/"app/defense.json").read_text(encoding="utf-8"))
FOUL_RISK=json.loads((ROOT/"app/foul-risk.json").read_text(encoding="utf-8"))
BIOS=[
{"name":"Abbey Ellis","slug":"abbey-ellis","number":"23","height":"168 cm","dob":"January 22, 2001","position":"Guard","photo":"https://cdn.prod.website-files.com/67edd996ab58aa16079f9490/68f078f64be48a8c2d1ec44d_4b75865bb3a440939dcd601a93340805.webp","source":"https://www.wnbl.com.au/player/abbey-ellis-7aab359a-45e3-11f0-bfde-d76608926233"},
{"name":"Miela Sowah","slug":"miela-sowah","number":"1","height":"180 cm","dob":"June 4, 2000","position":"","photo":"https://cdn.prod.website-files.com/67edd996ab58aa16079f9490/68f0794898ebff36edcc9135_bebe48ed66a44c9ba1178145cb900af3.webp","source":"https://www.wnbl.com.au/player/miela-sowah-63601774-45e3-11f0-8518-f11cbc5ce37c"},
{"name":"Chloe Forster","slug":"chloe-forster","number":"11","height":"178 cm","dob":"May 7, 2003","position":"Forward","photo":"https://cdn.prod.website-files.com/67edd996ab58aa16079f9490/6a20fea2e1eeba56879a86d1_0ef62b55152e41d8aee3488288b27b66.webp","source":"https://www.wnbl.com.au/player/chloe-forster-713b26b1-45e3-11f0-8b6f-c5864f4b75a8"},
{"name":"Courtney Woods","slug":"courtney-woods","number":"7","height":"183 cm","dob":"March 24, 1997","position":"Guard","photo":"https://cdn.prod.website-files.com/67edd996ab58aa16079f9490/68f07919c0db7ae860818d1d_27860f4307d6490794f60007af869763.webp","source":"https://www.wnbl.com.au/player/courtney-woods-70205f6b-45e3-11f0-9f25-c5864f4b75a8"},
{"name":"Alexandra Fowler","slug":"alexandra-fowler","number":"12","height":"183 cm","dob":"July 21, 2001","position":"Forward","photo":"https://cdn.prod.website-files.com/67edd996ab58aa16079f9490/68f07974022792de1d9e405c_f1924a2d77494078951ec90ef68fc1b0.webp","source":"https://www.wnbl.com.au/player/alexandra-fowler-584dd4b7-45e3-11f0-a6c9-79cf0a59c5e2"},
{"name":"Alicia Froling","slug":"alicia-froling","number":"9","height":"191 cm","dob":"January 30, 1996","position":"Forward","photo":"https://cdn.prod.website-files.com/67edd996ab58aa16079f9490/68f9c5835fa908c9e9f5cb93_8762feeb40a24948a46cddeaa2104276.webp","source":"https://www.wnbl.com.au/player/alicia-froling-c32612e5-45e4-11f0-ae88-4990fc5c3bac"},
{"name":"Isobel Borlase","slug":"isobel-borlase","number":"14","height":"180 cm","dob":"December 9, 2003","position":"Guard","photo":"https://cdn.prod.website-files.com/67edd996ab58aa16079f9490/68f9c63e0afbf426354c3c44_1709e26b48a3478da1f29008e8a34923.webp","source":"https://www.wnbl.com.au/player/isobel-borlase-70d52d7e-45e3-11f0-9ebc-c5864f4b75a8"},
{"name":"Cayla George","slug":"cayla-george","number":"3","height":"193 cm","dob":"May 1, 1989","position":"Forward","photo":"https://cdn.prod.website-files.com/67edd996ab58aa16079f9490/68f9c5a01feb4056c24c9b29_b171b7d4e0934bfea368d56ed8337f61.webp","source":"https://www.wnbl.com.au/player/cayla-george-57e5c694-45e3-11f0-8e9d-79cf0a59c5e2"},
{"name":"Kyana Weir","slug":"kyana-weir","number":"3","height":"—","dob":"October 17, 2005","position":"—","photo":"https://cdn.prod.website-files.com/67edd996ab58aa16079f9490/68f9c6277cee1ace90e80317_561b6d5fb8a64d3c95f7d9ade2c71a53.webp","source":"https://www.wnbl.com.au/player/kyana-weir-2e155f5c-921b-11f0-9933-0164fc3ae9ed"},
{"name":"Zitina Aokuso","slug":"zitina-aokuso","number":"15","height":"194 cm","dob":"November 23, 1998","position":"Centre","photo":"https://cdn.prod.website-files.com/67edd996ab58aa16079f9454/67edd996ab58aa16079f94bd_Player%20Silhouette.svg","source":"https://www.wnbl.com.au/player/zitina-aokuso-577211e6-45e3-11f0-a061-79cf0a59c5e2"},
{"name":"Ashlee Strawbridge","slug":"ashlee-strawbridge","number":"31","height":"182 cm","dob":"January 25, 2002","position":"—","photo":"https://cdn.prod.website-files.com/67edd996ab58aa16079f9454/67edd996ab58aa16079f94bd_Player%20Silhouette.svg","source":"https://www.wnbl.com.au/player/ashlee-strawbridge-96745cd7-69d5-11f0-97af-6b60ccde7f7f"},
{"name":"Akiene Tera Reed","slug":"akiene-tera-reed","number":"29","height":"185 cm","dob":"September 24, 1998","position":"—","photo":"https://cdn.prod.website-files.com/67edd996ab58aa16079f9454/67edd996ab58aa16079f94bd_Player%20Silhouette.svg","source":"https://www.wnbl.com.au/player/tera-reed-716b1833-45e3-11f0-b65d-c5864f4b75a8"},
]
for bio in BIOS:bio["bio_status"]="Official WNBL profile matched"
def slugify(value):
    return re.sub(r"[^a-z0-9]+","-",value.lower()).strip("-")
all_players={}
with (PROCESSED/"player_game_stats.csv").open(newline="",encoding="utf-8-sig") as f:
    for row in csv.DictReader(f):
        name=canonical_player(row["player"]);all_players.setdefault(name,row)
known={x["name"] for x in BIOS}
for name,row in sorted(all_players.items()):
    if name in known:continue
    BIOS.append({"name":name,"slug":slugify(name),"number":"—","height":"—","dob":"—","position":"—","photo":"https://cdn.prod.website-files.com/67edd996ab58aa16079f9454/67edd996ab58aa16079f94bd_Player%20Silhouette.svg","source":"https://www.wnbl.com.au/players","bio_status":"Official WNBL profile details not yet matched"})
NAMES={x["name"] for x in BIOS}
COUNT=["points","fg_made","fg_attempted","three_made","three_attempted","ft_made","ft_attempted","rebounds","offensive_rebounds","defensive_rebounds","assists","steals","turnovers","blocks","fouls"]

def n(v):
    try:return int(float(v))
    except:return 0
def seconds(v):
    try:
        m,s=v.split(":");return int(m)*60+int(s)
    except:return 0
def short(name):
    if name=="University of Canberra Capitals":return "UC Capitals"
    if name=="Southside Melbourne Flyers":return "Southside Flyers"
    return name.split()[0]

def on_off_metrics(rows, seed_key):
    def calculate(sample):
        on_minutes=sum(r["minutes_seconds"] for r in sample)/60
        off_minutes=sum(max(0,r["game_minutes"]-r["minutes_seconds"]/60) for r in sample)
        on_margin=sum(r["plus_minus"] for r in sample)
        off_margin=sum(r["team_margin"]-r["plus_minus"] for r in sample)
        on_rate=40*on_margin/on_minutes if on_minutes else None
        off_rate=40*off_margin/off_minutes if off_minutes else None
        relative=sum(r["plus_minus"]-r["team_margin"]*(r["minutes_seconds"]/60)/r["game_minutes"] for r in sample)
        return {
            "on_minutes":on_minutes,"off_minutes":off_minutes,
            "on_plus_minus":on_margin,"off_plus_minus":off_margin,
            "on_plus_minus_per_40":on_rate,"off_plus_minus_per_40":off_rate,
            "on_off_plus_minus_per_40":on_rate-off_rate if on_rate is not None and off_rate is not None else None,
            "team_relative_plus_minus_per_40":40*relative/on_minutes if on_minutes else None,
        }
    result=calculate(rows)
    values=[]
    if len(rows)>1:
        rng=random.Random(int(hashlib.sha256(seed_key.encode()).hexdigest()[:16],16))
        for _ in range(1000):
            sampled=[rows[rng.randrange(len(rows))] for _ in rows]
            value=calculate(sampled)["on_off_plus_minus_per_40"]
            if value is not None:values.append(value)
    values.sort()
    if values:
        result["on_off_ci_low"]=values[int(.025*(len(values)-1))]
        result["on_off_ci_high"]=values[int(.975*(len(values)-1))]
    else:
        result["on_off_ci_low"]=result["on_off_ci_high"]=None
    if len(rows)<10 or result["on_minutes"]<200 or result["off_minutes"]<100:
        result["on_off_sample"]="Low"
    elif len(rows)<18 or result["on_minutes"]<400 or result["off_minutes"]<180:
        result["on_off_sample"]="Moderate"
    else:
        result["on_off_sample"]="Strong"
    return result

games={}
with (PROCESSED/"games.csv").open(newline="",encoding="utf-8-sig") as f:
    for r in csv.DictReader(f):
        games[r["game_id"]]=r

game_periods=defaultdict(lambda:4)
with ENRICHED.open(newline="",encoding="utf-8-sig") as f:
    for r in csv.DictReader(f):
        game_periods[r["game_id"]]=max(game_periods[r["game_id"]],n(r["period_number"]))

plus_minus={}
with (PROCESSED/"player_plus_minus.csv").open(newline="",encoding="utf-8-sig") as f:
    for r in csv.DictReader(f):
        plus_minus[(r["game_id"],short(r["team"]),canonical_player(r["player"]))]=n(r["plus_minus"])

WIN_SHARE_FIELDS=("offensive_rating","defensive_rating","offensive_win_shares","defensive_win_shares","win_shares","win_shares_per_40","team_win_share","adjustment_win_shares","adjusted_win_shares","adjusted_win_shares_per_40","adjusted_team_win_share")
win_shares={}
with (PROCESSED/"player_win_shares.csv").open(newline="",encoding="utf-8-sig") as f:
    for r in csv.DictReader(f):
        win_shares[(r["season"],r["team"],canonical_player(r["player"]))]={k:float(r[k]) for k in WIN_SHARE_FIELDS}

logs=defaultdict(list)
with (PROCESSED/"player_game_stats.csv").open(newline="",encoding="utf-8-sig") as f:
    for r in csv.DictReader(f):
        player=canonical_player(r["player"])
        if player not in NAMES:continue
        g=games[r["game_id"]];team=r["team"];is1=team==g["team_1"]
        own=n(g["score_1"] if is1 else g["score_2"]);opp=n(g["score_2"] if is1 else g["score_1"])
        row={"season":r["season"],"game_id":r["game_id"],"date":r["game_date"],"team":short(team),
             "opponent":short(g["team_2"] if is1 else g["team_1"]),"result":("W" if own>opp else "L")+f" {own}–{opp}",
             "minutes_seconds":seconds(r["minutes"]),"minutes":r["minutes"],"jersey_number":r["jersey_number"]}
        row["game_minutes"]=40+max(0,game_periods[r["game_id"]]-4)*5
        row["team_margin"]=own-opp
        key=(r["game_id"],short(team),player)
        if key not in plus_minus:
            raise ValueError(f"Missing official plus/minus for {key}")
        row["plus_minus"]=plus_minus[key]
        row.update({k:n(r[k]) for k in COUNT});logs[player].append(row)

event_groups={"play_type":defaultdict(lambda:defaultdict(lambda:{"opportunities":0,"attempts":0,"makes":0,"fouls_drawn":0,"points":0})),
              "shot_type":defaultdict(lambda:defaultdict(lambda:{"opportunities":0,"attempts":0,"makes":0,"fouls_drawn":0,"points":0}))}
events=[]
with ENRICHED.open(newline="",encoding="utf-8-sig") as f:
    for r in csv.DictReader(f):
        events.append(r)
        player=canonical_player(r["player_name"])
        if player not in NAMES or r["is_shot_opportunity"]!="True":continue
        play=r["play_type"] or "Unclassified"
        token=(r["additional_data"].split(",")[0].strip() if r["additional_data"] else "")
        shot=token if token in {"Lay up","Jumper","Floater","Hook","Alley oop"} else "Unspecified"
        for dimension,label in (("play_type",play),("shot_type",shot)):
            x=event_groups[dimension][player][(r["season"],label)]
            x["opportunities"]+=1;x["attempts"]+=r["is_field_goal_attempt"]=="True"
            x["makes"]+=r["is_field_goal_attempt"]=="True" and r["shot_result"]=="made"
            x["fouls_drawn"]+=("Fouled" in r["action"] or "made and one" in r["action"])
            x["points"]+=n(r["points_delta"])

# Resolve the source's compact player labels once, then attach creation credits to
# the same player-game rows used everywhere else on the site.
label_name={}
for r in events:
    if r["player_label"] and r["player_name"]:
        label_name[(r["game_id"],short(r["team"]),r["player_label"])]=canonical_player(r["player_name"])
direct_created=defaultdict(int);action_created=defaultdict(int)
for r in events:
    if r["shot_result"]!="made":continue
    team=short(r["team"]);value=n(r["shot_value"])
    assister=label_name.get((r["game_id"],team,r["assisted_by"])) if r["assisted_by"] else None
    if assister:direct_created[(r["game_id"],team,assister)]+=value
    elif r["play_type"] in ("Pick'n'Roll","Pick'n'pop","Hand offs") and r["teammate"]:
        creator=label_name.get((r["game_id"],team,r["teammate"]))
        if creator and creator!=canonical_player(r["player_name"]):
            action_created[(r["game_id"],team,creator)]+=value
for player,player_logs in logs.items():
    for row in player_logs:
        key=(row["game_id"],row["team"],player)
        row["points_scored"]=row["points"]
        row["direct_assist_points_created"]=direct_created[key]
        row["action_created_points"]=action_created[key]
        row["total_points_created"]=row["points"]+direct_created[key]+action_created[key]

profiles=[]
for bio in BIOS:
    player_logs=sorted(logs[bio["name"]],key=lambda x:(x["date"],int(x["game_id"])))
    grouped=defaultdict(list)
    for r in player_logs:grouped[(r["season"],r["team"])].append(r)
    seasons=[]
    for (season,team),rs in sorted(grouped.items()):
        total={"season":season,"team":team,"games":len(rs),"minutes_seconds":sum(x["minutes_seconds"] for x in rs)}
        total.update({k:sum(x[k] for x in rs) for k in COUNT})
        total["plus_minus"]=sum(x["plus_minus"] for x in rs)
        total.update(on_off_metrics(rs,f"{bio['name']}|{season}|{team}"))
        win_share_key=(season,team,bio["name"])
        if win_share_key not in win_shares:raise ValueError(f"Missing Win Shares for {win_share_key}")
        total.update(win_shares[win_share_key])
        for k in ("points_scored","direct_assist_points_created","action_created_points","total_points_created"):
            total[k]=sum(x[k] for x in rs)
        total["fg_percentage"]=total["fg_made"]/total["fg_attempted"] if total["fg_attempted"] else None
        total["three_percentage"]=total["three_made"]/total["three_attempted"] if total["three_attempted"] else None
        total["ft_percentage"]=total["ft_made"]/total["ft_attempted"] if total["ft_attempted"] else None
        total["two_made"]=total["fg_made"]-total["three_made"]
        total["two_attempted"]=total["fg_attempted"]-total["three_attempted"]
        total["two_percentage"]=total["two_made"]/total["two_attempted"] if total["two_attempted"] else None
        seasons.append(total)
    career={"games":len(player_logs),"seasons":len({x["season"] for x in player_logs}),"minutes_seconds":sum(x["minutes_seconds"] for x in player_logs)}
    career.update({k:sum(x[k] for x in player_logs) for k in COUNT})
    career["plus_minus"]=sum(x["plus_minus"] for x in player_logs)
    if player_logs:career.update(on_off_metrics(player_logs,f"{bio['name']}|career"))
    for k in ("offensive_win_shares","defensive_win_shares","win_shares","adjustment_win_shares","adjusted_win_shares"):
        career[k]=sum(x.get(k,0) for x in seasons)
    career_minutes=career["minutes_seconds"]/60
    career["win_shares_per_40"]=career["win_shares"]/(career_minutes/40) if career_minutes else None
    career["adjusted_win_shares_per_40"]=career["adjusted_win_shares"]/(career_minutes/40) if career_minutes else None
    for k in ("points_scored","direct_assist_points_created","action_created_points","total_points_created"):
        career[k]=sum(x[k] for x in player_logs)
    analyses={}
    for dimension in ("play_type","shot_type"):
        label_key=dimension
        analyses[dimension]=[]
        for (season,label),values in sorted(event_groups[dimension][bio["name"]].items()):
            analyses[dimension].append({"season":season,"label":label,label_key:label,**values,
                "fg_percentage":values["makes"]/values["attempts"] if values["attempts"] else None,
                "points_per_opportunity":values["points"]/values["opportunities"] if values["opportunities"] else None})
    defense={"seasons":[{**r,"player_name":bio["name"]} for r in DEFENSE["player_seasons"] if canonical_player(r["player_name"])==bio["name"]],
             "matchups":[{**r,"player_name":bio["name"]} for r in DEFENSE["matchups"] if canonical_player(r["player_name"])==bio["name"]],
             "play_types":[{**r,"player_name":bio["name"]} for r in DEFENSE["play_types"] if canonical_player(r["player_name"])==bio["name"]],
             "shot_types":[{**r,"player_name":bio["name"]} for r in DEFENSE["shot_types"] if canonical_player(r["player_name"])==bio["name"]]}
    foul_risk=[{**r,"player_name":bio["name"]} for r in FOUL_RISK["records"] if canonical_player(r["player_name"])==bio["name"]]
    latest_team=next((x["team"] for x in reversed(player_logs) if x["season"]==max(r["season"] for r in player_logs)),player_logs[-1]["team"] if player_logs else "—")
    profiles.append({**bio,"team":latest_team,"season_stats":seasons,"game_log":list(reversed(player_logs)),"career":career,"defense":defense,"foul_risk":foul_risk,**analyses})

slugs={x["name"]:x["slug"] for x in BIOS}
photo_audit=ROOT/"app/wnbl-player-photo-audit.json"
if photo_audit.exists():
    photos={canonical_player(row["player"]):row for row in json.loads(photo_audit.read_text())["matched"]}
    for profile in profiles:
        matched=photos.get(profile["name"])
        if matched and (ROOT/"static/player-photos"/matched["file"]).is_file():
            profile.update(photo="player-photos/"+matched["file"],source=matched["source"],bio_status="Official WNBL profile matched")
for alias,target in ALIASES.items():slugs[alias]=slugs[target]
out={"profiles":profiles,"slugs":slugs,"aliases":ALIASES,"foul_risk_meta":FOUL_RISK["meta"],"win_shares_meta":json.loads((ROOT/"app/win-shares.json").read_text(encoding="utf-8"))["meta"],"stat_source":"Hudl/InStat box scores collected in the WNBL dataset"}
(ROOT/"app/player-profiles.json").write_text(json.dumps(out,separators=(",",":"),ensure_ascii=False),encoding="utf-8")
on_off_fields=["season","team","games","on_minutes","off_minutes","on_plus_minus","off_plus_minus","on_plus_minus_per_40","off_plus_minus_per_40","on_off_plus_minus_per_40","team_relative_plus_minus_per_40","on_off_ci_low","on_off_ci_high","on_off_sample"]
with (PROCESSED/"player_same_game_on_off.csv").open("w",newline="",encoding="utf-8") as f:
    writer=csv.DictWriter(f,fieldnames=["player",*on_off_fields]);writer.writeheader()
    for p in profiles:
        for r in p["season_stats"]:writer.writerow({"player":p["name"],**{k:r.get(k) for k in on_off_fields}})
print({x["name"]:len(x["game_log"]) for x in profiles})
