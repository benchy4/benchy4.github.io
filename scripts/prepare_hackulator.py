import csv,json,math
import numpy as np
from collections import defaultdict
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT.parent/"outputs/WNBL_Data_Collector/wnbl_dataset"
WP=DATA/"analytics/model_adjusted_decisions/win_probability_oof_possessions.csv"
CLUTCH=DATA/"analytics/late_game_foul_policy/clutch_team_season_efficiency.csv"
POLICY=DATA/"analytics/late_game_foul_policy/foul_decision_policy_by_state.csv"
PBP=DATA/"processed/play_by_play.csv"

def num(v,default=0.0):
    try:return float(v)
    except:return default

def features(t,m):
    s=math.sqrt(max(t,1))
    return [m,m/s,m*m*(1 if m>=0 else -1)/max(t,1),s,1/s]

training=[];cells=defaultdict(int)
with WP.open(newline="") as f:
    for r in csv.DictReader(f):
        t=num(r["stage_seconds_remaining"],999)
        period=int(num(r["period_number"]))
        margin=num(r["offense_margin_at_start"])
        if period<4 or not 0<t<=300 or abs(margin)>20:continue
        training.append((t,margin,1.0 if r["offense_won"]=="True" else 0.0))
        if t<=120 and abs(margin)<=15:
            tb=int(round(t/5)*5);mb=int(round(margin))
            cells[("user",tb,mb)]+=1;cells[("opponent",tb,-mb)]+=1

X=np.array([features(t,m) for t,m,_ in training],dtype=float);y=np.array([w for _,_,w in training])
mu=X.mean(axis=0);sd=X.std(axis=0);Xs=np.c_[(X-mu)/sd,np.ones(len(X))]
beta=np.zeros(Xs.shape[1]);ridge=.5
for _ in range(60):
    z=np.clip(Xs@beta,-30,30);p=1/(1+np.exp(-z));w=p*(1-p)
    h=Xs.T@(Xs*w[:,None])+np.diag([ridge]*(Xs.shape[1]-1)+[0])
    g=Xs.T@(y-p)-np.r_[ridge*beta[:-1],0]
    step=np.linalg.solve(h,g);beta+=step
    if np.max(np.abs(step))<1e-9:break

def offense_wp(t,m):
    x=(np.array(features(t,m))-mu)/sd
    z=float(np.r_[x,1]@beta)
    return 1/(1+math.exp(-max(-30,min(30,z))))

grid=[]
for possession in ("user","opponent"):
    for t in range(0,91,5):
        for margin in range(-12,13):
            if t==0:
                wp=1.0 if margin>0 else 0.0 if margin<0 else .5
                support=0
            else:
                wp=offense_wp(t,margin) if possession=="user" else 1-offense_wp(t,-margin)
                support=sum(n for (pos,tt,mm),n in cells.items() if pos==possession and abs(tt-t)<=10 and abs(mm-margin)<=1)
            grid.append({"p":possession,"t":t,"m":margin,"wp":round(wp,6),"n":support})

clutch=[]
with CLUTCH.open(newline="") as f:
    for r in csv.DictReader(f):
        clutch.append({
            "season":r["season"],"team":r["team"],
            "off_n":round(num(r["offensive_possessions"]),2),"off_ppp":round(num(r["clutch_offensive_ppp"]),4),
            "def_n":round(num(r["defensive_possessions"]),2),"def_ppp":round(num(r["clutch_defensive_ppp_allowed"]),4),
            "to_rate":round(num(r["clutch_turnover_rate"]),4),
        })

policy=[]
with POLICY.open(newline="") as f:
    for r in csv.DictReader(f):
        if r["period_context"]!="fourth quarter" or not r["seconds_band"] in ("0-30","31-60","61-90"):continue
        policy.append({
            "band":r["seconds_band"],"margin":int(num(r["defense_margin"])),"n":int(num(r["opportunities"])),
            "fouls":int(num(r["foul_candidates"])),"adv":round(num(r["estimated_foul_advantage"]),6),
            "supported":r["supported_for_estimation"]=="True","guidance":r["model_guidance"],
        })

rows=list(csv.DictReader(PBP.open(newline="")))
orb=reb=0
ft_rebounds={"clutch":{"oreb":0,"opportunities":0},"non_clutch":{"oreb":0,"opportunities":0}}
ft_rebounds_by_season=defaultdict(lambda:{"clutch":{"oreb":0,"opportunities":0},"non_clutch":{"oreb":0,"opportunities":0}})
shooting={"all":{"three_made":0,"three_attempted":0,"ft_made":0,"ft_attempted":0},"clutch":{"three_made":0,"three_attempted":0,"ft_made":0,"ft_attempted":0}}
three_rebounds={"all":{"oreb":0,"opportunities":0},"clutch":{"oreb":0,"opportunities":0}}
last_score={}
excluded_from_split=0
for i,a in enumerate(rows):
    game=a["game_id"]
    prior_score=last_score.get(game)
    event_score=None
    if a["score"]:
        try:event_score=tuple(int(v) for v in a["score"].split(":"))
        except:pass
    score=prior_score or event_score
    if event_score is not None:last_score[game]=event_score
    try:
        minutes,seconds=(int(v) for v in a["clock"].split(":"))
        clock_seconds=minutes*60+seconds
    except:
        clock_seconds=None
    margin=abs(score[0]-score[1]) if score is not None else None
    is_clutch=bool(score is not None and clock_seconds is not None and (((a["period"]=="4Q" and clock_seconds<=300) or a["period"]=="OV") and margin<=5))
    if a["action"] in ("3-PT Made","3-PT Missed"):
        shooting["all"]["three_attempted"]+=1
        shooting["all"]["three_made"]+=a["action"]=="3-PT Made"
        if is_clutch:
            shooting["clutch"]["three_attempted"]+=1
            shooting["clutch"]["three_made"]+=a["action"]=="3-PT Made"
    if a["action"] in ("FT Made","FT Missed"):
        shooting["all"]["ft_attempted"]+=1
        shooting["all"]["ft_made"]+=a["action"]=="FT Made"
        if is_clutch:
            shooting["clutch"]["ft_attempted"]+=1
            shooting["clutch"]["ft_made"]+=a["action"]=="FT Made"
    if a["action"]=="3-PT Missed" and i+1<len(rows):
        b=rows[i+1]
        if game==b["game_id"] and b["action"] in ("Offensive rebound","Defensive rebound"):
            is_oreb=b["action"]=="Offensive rebound"
            three_rebounds["all"]["opportunities"]+=1;three_rebounds["all"]["oreb"]+=is_oreb
            if is_clutch:
                three_rebounds["clutch"]["opportunities"]+=1;three_rebounds["clutch"]["oreb"]+=is_oreb
    if a["action"]!="FT Missed" or i+1>=len(rows):continue
    b=rows[i+1]
    if game!=b["game_id"] or b["action"] not in ("Offensive rebound","Defensive rebound"):continue
    is_oreb=b["action"]=="Offensive rebound"
    reb+=1;orb+=is_oreb
    if score is None or clock_seconds is None:
        excluded_from_split+=1
        continue
    group="clutch" if is_clutch else "non_clutch"
    season=a["\ufeffseason"]
    ft_rebounds[group]["opportunities"]+=1
    ft_rebounds[group]["oreb"]+=is_oreb
    ft_rebounds_by_season[season][group]["opportunities"]+=1
    ft_rebounds_by_season[season][group]["oreb"]+=is_oreb

def wilson(successes,total,z=1.96):
    p=successes/total;den=1+z*z/total
    mid=(p+z*z/(2*total))/den
    half=z*math.sqrt(p*(1-p)/total+z*z/(4*total*total))/den
    return mid-half,mid+half

for group in ft_rebounds.values():
    group["rate"]=group["oreb"]/group["opportunities"]
    group["ci_low"],group["ci_high"]=wilson(group["oreb"],group["opportunities"])
for season_groups in ft_rebounds_by_season.values():
    for group in season_groups.values():
        group["rate"]=group["oreb"]/group["opportunities"] if group["opportunities"] else None
clutch_ft,regular_ft=ft_rebounds["clutch"],ft_rebounds["non_clutch"]
pooled=(clutch_ft["oreb"]+regular_ft["oreb"])/(clutch_ft["opportunities"]+regular_ft["opportunities"])
se=math.sqrt(pooled*(1-pooled)*(1/clutch_ft["opportunities"]+1/regular_ft["opportunities"]))
z=(clutch_ft["rate"]-regular_ft["rate"])/se
ft_oreb_comparison={
    **ft_rebounds,
    "all":{"oreb":orb,"opportunities":reb,"rate":orb/reb},
    "difference":clutch_ft["rate"]-regular_ft["rate"],
    "rate_ratio":clutch_ft["rate"]/regular_ft["rate"],
    "two_sided_p_value":math.erfc(abs(z)/math.sqrt(2)),
    "excluded_from_split":excluded_from_split,
    "definition":"Clutch is the final 5:00 of the fourth quarter or any overtime while the score margin is within five points. Non-clutch covers all other missed-free-throw rebound opportunities.",
    "by_season":dict(sorted(ft_rebounds_by_season.items())),
}
for group in shooting.values():
    group["three_pct"]=group["three_made"]/group["three_attempted"]
    group["ft_pct"]=group["ft_made"]/group["ft_attempted"]
for group in three_rebounds.values():
    group["rate"]=group["oreb"]/group["opportunities"]

total_off=sum(r["off_n"] for r in clutch);total_def=sum(r["def_n"] for r in clutch)
league_off=sum(r["off_n"]*r["off_ppp"] for r in clutch)/total_off
league_def=sum(r["def_n"]*r["def_ppp"] for r in clutch)/total_def
out={
    "meta":{"games":len({r["game_id"] for r in csv.DictReader((DATA/"analytics/possessions.csv").open(encoding="utf-8-sig"))}),"seasons":sorted({r["season"] for r in clutch}),"ft_oreb_rate":round(orb/reb,4),
            "ft_oreb_n":reb,"shrinkage_prior":75,"league_off_ppp":round(league_off,4),"league_def_ppp":round(league_def,4),
            "league_ft_pct":round(shooting["all"]["ft_pct"],6),"league_three_pct":round(shooting["all"]["three_pct"],6),
            "clutch_ft_pct":round(shooting["clutch"]["ft_pct"],6),"clutch_three_pct":round(shooting["clutch"]["three_pct"],6),
            "three_miss_oreb_rate":round(three_rebounds["all"]["rate"],6),"clutch_three_miss_oreb_rate":round(three_rebounds["clutch"]["rate"],6),
            "shooting_samples":shooting,"three_rebound_samples":three_rebounds,
            "wp_scope":"Regularized state-only model fitted to fourth-quarter and overtime WNBL outcomes",
            "wp_training_states":len(training),"wp_ridge":ridge,"ft_oreb_comparison":ft_oreb_comparison},
    "grid":grid,"clutch":clutch,"policy":policy,
}
(ROOT/"app/hackulator-data.json").write_text(json.dumps(out,separators=(",",":")))
print({"grid":len(grid),"clutch":len(clutch),"policy":len(policy),"ft_oreb_rate":out["meta"]["ft_oreb_rate"]})
