import csv, math, statistics
from collections import defaultdict
from pathlib import Path

HERE=Path(__file__).resolve().parent
BASE=HERE.parent
EARLY={"2019-20","2020","2021-22","2022-23"}
LATE={"2023-24","2024-25","2025-26","2026-27"}

def read(path):
    with open(path,encoding="utf-8",newline="") as f:
        return list(csv.DictReader(f))
def num(v):
    try:return float(v) if v not in ("",None) else 0.0
    except:return 0.0
def short(name):
    return "Canberra" if name=="University of Canberra Capitals" else name.split()[0]
def write(name,rows):
    if not rows:return
    with open(HERE/name,"w",encoding="utf-8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def div(a,b): return a/b if b else None
def wilson(w,n,z=1.96):
    if not n:return (None,None)
    p=w/n;d=1+z*z/n;c=(p+z*z/(2*n))/d;m=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/d
    return c-m,c+m
def pvalue(w,n):
    if not n:return 1
    z=abs((w/n-.5)/math.sqrt(.25/n))
    return math.erfc(z/math.sqrt(2))
def bh(rows):
    ordered=sorted(enumerate(rows),key=lambda x:x[1]["p_value"]);m=len(rows);q=[1]*m;running=1
    for rank,(idx,row) in reversed(list(enumerate(ordered,1))):
        running=min(running,row["p_value"]*m/rank);q[idx]=running
    for row,v in zip(rows,q):row["q_value"]=v

player=read(BASE/"player_game_stats_numeric.csv")
kills=read(BASE/"advanced_decisions/kill_team_game.csv")
poss=read(BASE/"true_possession_speed/first_decision_possession_detail.csv")
games=read(BASE/"games_analytics.csv")

sums=defaultdict(lambda:defaultdict(float))
names={}
for r in player:
    key=(r["game_id"],r["team_id"]);names[key]=(r["﻿season"],r["game_date"],r["team"])
    for k in ["points","fg_made","fg_attempted","three_made","three_attempted","ft_made","ft_attempted","rebounds","offensive_rebounds","defensive_rebounds","assists","steals","turnovers","blocks","fouls"]:
        sums[key][k]+=num(r[k])

possum=defaultdict(lambda:defaultdict(float))
for r in poss:
    key=(r["game_id"],r["offense_team_id"]);g=possum[key];g["team_possessions"]+=1;g["possession_points"]+=num(r["points"])
    g["live_ball_turnovers"]+=r["turnover_type"]=="live_ball_stolen"

killmap={(r["game_id"],r["team_id"]):int(r["kills"]) for r in kills}
wonmap={(r["game_id"],r["team_id"]):r["won"]=="True" for r in kills}
opp={}
final_points={}
for r in games:
    opp[(r["game_id"],r["team_1_id"])]=r["team_2_id"];opp[(r["game_id"],r["team_2_id"])]=r["team_1_id"]
    final_points[(r["game_id"],r["team_1_id"])]=num(r["score_1"])
    final_points[(r["game_id"],r["team_2_id"])]=num(r["score_2"])

team_games=[]
for key,won in wonmap.items():
    gid,tid=key;oid=opp.get(key)
    if not oid or key not in sums or (gid,oid) not in sums or key not in possum or (gid,oid) not in possum:continue
    season,date,name=names[key];s=sums[key];o=sums[(gid,oid)];p=possum[key];op=possum[(gid,oid)]
    s["points"]=final_points[key];o["points"]=final_points[(gid,oid)]
    two_m=s["fg_made"]-s["three_made"];two_a=s["fg_attempted"]-s["three_attempted"]
    fga=s["fg_attempted"];fta=s["ft_attempted"];poss_n=fga+.44*fta+s["turnovers"];opp_fga=o["fg_attempted"];opp_fta=o["ft_attempted"];opp_poss=opp_fga+.44*opp_fta+o["turnovers"]
    row={"season":season,"game_id":gid,"game_date":date,"team_id":tid,"team":short(name),"opponent":short(names[(gid,oid)][2]),"won":int(won)}
    row.update({
      "points":s["points"],"points_allowed":o["points"],"point_margin":s["points"]-o["points"],
      "offensive_rating":div(s["points"]*100,poss_n),"defensive_rating":div(o["points"]*100,opp_poss),"net_rating":div(s["points"]*100,poss_n)-div(o["points"]*100,opp_poss),
      "fg_pct":div(s["fg_made"],fga),"two_pct":div(two_m,two_a),"three_pct":div(s["three_made"],s["three_attempted"]),"ft_pct":div(s["ft_made"],fta),
      "efg_pct":div(s["fg_made"]+.5*s["three_made"],fga),"free_throw_rate":div(fta,fga),
      "three_made":s["three_made"],"three_attempted":s["three_attempted"],"fga_plus_fta":fga+fta,"fga_plus_fta_margin":(fga+fta)-(opp_fga+opp_fta),
      "assists":s["assists"],"turnovers":s["turnovers"],"turnover_rate":div(s["turnovers"],poss_n),
      "assist_turnover_ratio":div(s["assists"],s["turnovers"]),"turnover_margin":o["turnovers"]-s["turnovers"],
      "offensive_rebound_pct":div(s["offensive_rebounds"],s["offensive_rebounds"]+o["defensive_rebounds"]),
      "defensive_rebound_pct":div(s["defensive_rebounds"],s["defensive_rebounds"]+o["offensive_rebounds"]),
      "rebound_margin":s["rebounds"]-o["rebounds"],"steals":s["steals"],
      "live_ball_turnovers_forced":op["live_ball_turnovers"],"kills":killmap.get(key,0),"possessions":poss_n
    })
    team_games.append(row)

configs={
 "points":("Points scored","at_least",5), "points_allowed":("Points allowed","at_most",5),
 "offensive_rating":("Offensive rating","at_least",5),"defensive_rating":("Defensive rating","at_most",5),"net_rating":("Net rating","at_least",5),
 "fg_pct":("FG%","at_least",.025),"two_pct":("2P%","at_least",.025),"three_pct":("3P%","at_least",.025),"ft_pct":("FT%","at_least",.025),
 "efg_pct":("eFG%","at_least",.025),"free_throw_rate":("Free throw rate (FTA/FGA)","at_least",.05),
 "three_made":("3PM","at_least",1),"three_attempted":("3PA","at_least",2),"fga_plus_fta":("FGA + FTA","at_least",5),"fga_plus_fta_margin":("FGA + FTA differential","at_least",5),"possessions":("Possessions","at_least",5),
 "assists":("Assists","at_least",2),"turnovers":("Turnovers","at_most",2),
 "turnover_rate":("Turnover rate","at_most",.02),"assist_turnover_ratio":("Assist/turnover ratio","at_least",.25),"turnover_margin":("Turnover margin","at_least",2),
 "offensive_rebound_pct":("Offensive rebound %","at_least",.025),"defensive_rebound_pct":("Defensive rebound %","at_least",.025),"rebound_margin":("Rebound margin","at_least",2),
 "steals":("Steals","at_least",1),"live_ball_turnovers_forced":("Live-ball turnovers forced","at_least",1),"kills":("Kills","at_least",1)
}
def candidates(metric,step):
    vals=sorted(r[metric] for r in team_games if r[metric] is not None)
    lo,hi=vals[int(.1*len(vals))],vals[int(.9*len(vals))]
    start=math.ceil(lo/step)*step;end=math.floor(hi/step)*step
    out=[];x=start
    while x<=end+step/100:
        out.append(round(x,6));x+=step
    return out
def meets(v,t,d):return v>=t if d=="at_least" else v<=t
def evaluate(rows,metric,t,d):
    q=[r for r in rows if r[metric] is not None and meets(r[metric],t,d)];w=sum(r["won"] for r in q);n=len(q);lo,hi=wilson(w,n)
    return n,w,div(w,n),lo,hi

results=[]
for metric,(label,direction,step) in configs.items():
    for threshold in candidates(metric,step):
        n,w,rate,lo,hi=evaluate(team_games,metric,threshold,direction)
        dn,dw,dr,_,_=evaluate([r for r in team_games if r["season"] in EARLY],metric,threshold,direction)
        vn,vw,vr,vlo,vhi=evaluate([r for r in team_games if r["season"] in LATE],metric,threshold,direction)
        season_rates=[];represented=0
        for season in sorted(EARLY|LATE):
            sn,sw,sr,_,_=evaluate([r for r in team_games if r["season"]==season],metric,threshold,direction)
            if sn>=10:season_rates.append(sr);represented+=1
        results.append({"metric":metric,"metric_label":label,"direction":direction,"threshold":threshold,"team_games":n,"wins":w,"win_rate":rate,"ci_low":lo,"ci_high":hi,"win_rate_lift":rate-.5 if rate is not None else None,"discovery_n":dn,"discovery_win_rate":dr,"validation_n":vn,"validation_win_rate":vr,"validation_ci_low":vlo,"validation_ci_high":vhi,"seasons_with_10_plus":represented,"season_min_win_rate":min(season_rates) if season_rates else None,"season_max_win_rate":max(season_rates) if season_rates else None,"p_value":pvalue(w,n)})
bh(results)

selected=[]
for metric in configs:
    eligible=[r for r in results if r["metric"]==metric and r["discovery_n"]>=40 and r["validation_n"]>=25 and r["team_games"]<=.8*len(team_games)]
    if not eligible:continue
    best=max(eligible,key=lambda r:(r["discovery_win_rate"],r["discovery_n"]))
    best=dict(best);best["validation_pass"]=best["validation_win_rate"]>.5 and best["validation_ci_low"]>.5
    selected.append(best)

actionable={"fg_pct","two_pct","three_pct","efg_pct","free_throw_rate","three_attempted","fga_plus_fta","fga_plus_fta_margin","possessions","turnovers","turnover_rate","assist_turnover_ratio","turnover_margin","offensive_rebound_pct","defensive_rebound_pct","rebound_margin","steals","live_ball_turnovers_forced","kills"}
rules=[r for r in selected if r["metric"] in actionable and r["validation_win_rate"] is not None]
pairs=[]
for i,a in enumerate(rules):
    for b in rules[i+1:]:
        def both(r):return meets(r[a["metric"]],a["threshold"],a["direction"]) and meets(r[b["metric"]],b["threshold"],b["direction"])
        dr=[r for r in team_games if r["season"] in EARLY and r[a["metric"]] is not None and r[b["metric"]] is not None and both(r)]
        vr=[r for r in team_games if r["season"] in LATE and r[a["metric"]] is not None and r[b["metric"]] is not None and both(r)]
        if len(dr)<40 or len(vr)<20:continue
        dw=sum(r["won"] for r in dr);vw=sum(r["won"] for r in vr);lo,hi=wilson(vw,len(vr))
        pairs.append({"metric_1":a["metric"],"label_1":a["metric_label"],"direction_1":a["direction"],"threshold_1":a["threshold"],"metric_2":b["metric"],"label_2":b["metric_label"],"direction_2":b["direction"],"threshold_2":b["threshold"],"discovery_n":len(dr),"discovery_win_rate":dw/len(dr),"validation_n":len(vr),"validation_win_rate":vw/len(vr),"validation_ci_low":lo,"validation_ci_high":hi})
pairs=sorted(pairs,key=lambda r:(r["validation_win_rate"],r["validation_n"]),reverse=True)[:30]

write("team_game_metrics.csv",team_games);write("threshold_results.csv",results);write("selected_thresholds.csv",selected);write("combination_rules.csv",pairs)

best=sorted(selected,key=lambda r:(bool(r["validation_pass"]),r["validation_win_rate"]),reverse=True)
with open(HERE/"FINDINGS.md","w",encoding="utf-8") as f:
    f.write("# Winning threshold findings\n\n")
    f.write(f"- Complete games: {len(team_games)//2}\n- Team-game observations: {len(team_games)}\n- Discovery seasons: 2019–20 through 2022–23\n- Validation seasons: 2023–24 through 2025–26\n\n")
    f.write("## Strongest held-out single-stat thresholds\n\n")
    for r in best[:12]:
        op="at least" if r["direction"]=="at_least" else "at most"
        f.write(f"- {r['metric_label']} {op} {r['threshold']:.3f}: {r['validation_win_rate']:.1%} wins in {r['validation_n']} validation team-games (95% CI {r['validation_ci_low']:.1%}–{r['validation_ci_high']:.1%}).\n")
    f.write("\nThese thresholds were selected on earlier seasons and evaluated on later seasons. They remain descriptive associations, not causal targets. Scoring and efficiency thresholds are especially close to the game outcome.\n")
with open(HERE/"VALIDATION_REPORT.md","w",encoding="utf-8") as f:
    f.write("# Validation report\n\n")
    f.write(f"- Reconstructed {len(team_games)} paired team-game rows from {len(team_games)//2} games.\n")
    f.write("- Threshold candidates are limited to the central 10th–90th percentile range and natural metric increments.\n")
    f.write("- Selection requires at least 40 discovery and 25 validation observations, with no more than 80% overall coverage.\n")
    f.write("- Wilson intervals and Benjamini–Hochberg q-values are supplied.\n")
    f.write("- Earlier four seasons are used for threshold discovery; the latest three seasons are held out for validation.\n")
    f.write("- Combination rules require at least 40 discovery and 20 validation observations.\n")
    f.write("- Results are observational. Opponent quality, roster strength and game context remain possible confounders.\n")
print({"team_games":len(team_games),"thresholds":len(results),"selected":len(selected),"pairs":len(pairs)})
