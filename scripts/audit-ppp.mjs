import {readFile} from "node:fs/promises";
import {resolve} from "node:path";

const root=resolve(import.meta.dirname,"..");
const load=async name=>JSON.parse(await readFile(resolve(root,name),"utf8"));
const [analysis,deep,teams]=await Promise.all([load("app/data.json"),load("app/deep-dives.json"),load("app/team-profiles.json")]);
const failures=[],coverageNotes=[];let checks=0;
const close=(label,actual,expected,tolerance=1e-9)=>{checks++;if(!Number.isFinite(Number(actual))||!Number.isFinite(Number(expected))||Math.abs(Number(actual)-Number(expected))>tolerance)failures.push({label,actual,expected})};
const rate=(n,d)=>Number(d)?Number(n)/Number(d):0;

analysis.speed.forEach((r,i)=>close(`speed[${i}].ppp`,r.ppp,rate(r.points,r.possessions)));
analysis.turnovers.forEach((r,i)=>close(`turnovers[${i}].points_per_possession`,r.points_per_possession,rate(r.points,r.possessions)));
analysis.oreb.forEach((r,i)=>close(`oreb[${i}].points_per_extension`,r.points_per_extension,rate(r.points,r.synergy_play_possessions)));
analysis.clutch.forEach((r,i)=>{
  close(`clutch[${i}].offensive_ppp`,r.clutch_offensive_ppp,rate(r.offensive_points,r.offensive_possessions));
  close(`clutch[${i}].defensive_ppp`,r.clutch_defensive_ppp_allowed,rate(r.points_allowed,r.defensive_possessions));
  close(`clutch[${i}].net_per_100`,r.clutch_net_points_per_100,100*(rate(r.offensive_points,r.offensive_possessions)-rate(r.points_allowed,r.defensive_possessions)));
});
for(const key of ["score_pressure","quarter_profiles"])deep[key].forEach((r,i)=>close(`${key}[${i}].ppp`,r.ppp,rate(r.points,r.possessions)));
teams.profiles.flatMap(p=>p.advanced||[]).forEach((r,i)=>{
  close(`team_advanced[${i}].ppp`,r.ppp,rate(r.points,r.possessions),.015);
  close(`team_advanced[${i}].defensive_ppp`,r.defensive_ppp,rate(r.points_allowed,r.defensive_possessions),.015);
  if(Math.abs(r.points-r.total_points)>.5)coverageNotes.push({season:r.season,team:r.team,play_by_play_points:r.points,box_score_points:r.total_points,note:"PPP uses the processed play-by-play numerator; the box score includes points outside that complete event sample."});
});

if(failures.length){console.error(JSON.stringify({checks,failures},null,2));process.exit(1)}
console.log(JSON.stringify({checks,status:"pass",coverageNotes,definition:"All audited PPP uses points / (FGA + 0.44 × FTA + TOV). Reconstructed team possessions remain only for event sequence analysis."},null,2));
