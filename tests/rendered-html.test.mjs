import assert from "node:assert/strict";
import test from "node:test";
import {readFile} from "node:fs/promises";

globalThis.__WNBL_ASSETS={async fetch(request){
  const path=new URL(request.url).pathname.replace(/^\/+/,"")||"analysis-hub.html";
  try{return new Response(await readFile(new URL("../dist/client/"+path,import.meta.url)),{status:200,headers:{"content-type":path.endsWith(".html")?"text/html":"application/octet-stream"}})}
  catch{return new Response("Not found",{status:404})}
}};

const worker=async()=>{const u=new URL(`../dist/server/index.js?t=${Date.now()}-${Math.random()}`,import.meta.url);return(await import(u)).default};
const fetchPage=async path=>{const w=await worker(),r=await w.fetch(new Request(`https://hub.test/${path}`));return{status:r.status,body:await r.text()}};
const jsonScript=(body,id)=>JSON.parse(body.match(new RegExp(`<script id="${id}" type="application/json">([\\s\\S]*?)<\\/script>`))[1]);

test("uses a concise analysis directory instead of the former mega page",async()=>{
  const{status,body}=await fetchPage("analysis-hub.html");assert.equal(status,200);
  for(const heading of ["Possessions and shots","Defence and late-game decisions","Creation and personnel","Game patterns and outcomes"])assert.ok(body.includes(heading),heading);
  for(const route of ["possession-speed.html","after-oreb-analysis.html","kills-analysis.html","late-game-analysis.html","assist-chemistry.html","win-thresholds.html","game-state-performance.html","player-dependency.html","roster-continuity.html","player-development.html"])assert.ok(body.includes(route),route);
  assert.ok(!body.includes("turnover-analysis.html"));
  for(const redundant of ["creator-scorer-connections.html","oreb-decision-tree.html","score-pressure.html","quarter-profiles.html","winning-context.html"])assert.ok(!body.includes(redundant),redundant);
  for(const old of ['id="speed"','id="players"','id="teams"','id="deep-dives"','iframe src="deep-dives.html'])assert.ok(!body.includes(old),old);
});

test("builds one route for every primary analysis",async()=>{
  const routes={"possession-speed.html":"speed","turnover-analysis.html":"turnovers","after-oreb-analysis.html":"rebounding","kills-analysis.html":"kills","late-game-analysis.html":"late","assist-chemistry.html":"chemistry","win-thresholds.html":"thresholds"};
  for(const[path,id]of Object.entries(routes)){const{status,body}=await fetchPage(path);assert.equal(status,200,path);assert.ok(body.includes(`section.id!==\"${id}\"`)||body.includes(`section.id!=="${id}"`),`${path}: isolated ${id}`);assert.ok(body.includes('section.page'),path);assert.ok(body.includes('table-enhancements.js'),path)}
});

test("builds one route for every deep dive",async()=>{
  const routes={"player-dependency.html":"dependence","roster-continuity.html":"continuity","scoring-runs.html":"runs","game-state-performance.html":"game-state","performance-variance.html":"sustainability","player-development.html":"development"};
  for(const[path,id]of Object.entries(routes)){const{status,body}=await fetchPage(path);assert.equal(status,200,path);assert.ok(body.includes(`section.id!==\"${id}\"`)||body.includes(`section.id!=="${id}"`),`${path}: isolated ${id}`);assert.ok(body.includes('section.deep'),path);assert.ok(body.includes('seasonFilter')&&body.includes('teamFilter'),path)}
});

test("keeps decision tools as dedicated pages",async()=>{
  const dashboard=await fetchPage("late-game-foul-dashboard.html"),calculator=await fetchPage("wnbl-hackulator.html");
  assert.equal(dashboard.status,200);assert.equal(calculator.status,200);
  for(const text of ["WNBL Late-Game Fouling Decision Lab","foul-data","All seasons"])assert.ok(dashboard.body.includes(text),text);
  for(const text of ["Late Game: Foul or Guard?","Leading: foul or guard","Trailing: get the ball back","The \"foul up 3\" dilemma","When to start fouling","Sources this model is built from"])assert.ok(calculator.body.includes(text),text);
  for(const token of ["function upThreeModel","function trailingDefendModel","function trailingFoulModel","function finalPossWinProb","holdTime","foulCost"])assert.ok(calculator.body.includes(token),token);
  assert.ok(calculator.body.includes('src="site-shell.js"'));
});

test("provides a standalone, searchable player statistics page",async()=>{
  const{status,body}=await fetchPage("player-statistics.html");assert.equal(status,200);
  for(const text of ["Player statistics","Box stats","Advanced","Player name","Total points created","Creation dependency"])assert.ok(body.includes(text),text);
  const data=jsonScript(body,"player-table-data");assert.equal(data.players.length,864);assert.equal(data.seasons.length,8);assert.ok(Object.keys(data.slugs).length>=360);
});

test("creates all player profiles and supplies integrated creation data",async()=>{
  const profiles=JSON.parse(await readFile(new URL("../app/player-profiles.json",import.meta.url),"utf8"));assert.equal(profiles.profiles.length,389);
  for(const slug of ["abbey-ellis","miela-sowah","courtney-woods","alexandra-fowler"]){const{status,body}=await fetchPage(`player-${slug}.html`);assert.equal(status,200);const data=jsonScript(body,"profile-data");assert.equal(data.profiles[0].slug,slug);assert.ok(data.analysis);assert.ok(Array.isArray(data.analysis.creation));assert.ok(Array.isArray(data.analysis.connections));assert.ok(Array.isArray(data.analysis.development));assert.ok(body.includes("profile-analysis" )||body.includes("site-shell.js"));}
  const shell=(await fetchPage("site-shell.js")).body;for(const text of ["Creation and connections","Total points created","Creator–scorer connections","Season-to-season role change"])assert.ok(shell.includes(text),text);
});

test("integrates team dependency, runs, pressure and quarter analysis",async()=>{
  const{status,body}=await fetchPage("team-townsville-fire.html");assert.equal(status,200);const data=jsonScript(body,"team-data");
  for(const key of ["dependence","runs","score_pressure","quarter_profiles","sustainability","continuity","connections"]){assert.ok(Array.isArray(data.analysis[key]),key);assert.ok(data.analysis[key].length,key)}
  const shell=(await fetchPage("site-shell.js")).body;for(const text of ["Team analysis","Prior MIN retained","First-five record","Leading creator","Creator share","8–0 runs / game","Efficiency by score state","Quarter profile"])assert.ok(shell.includes(text),text);
  assert.ok(data.profiles[0].players.some(p=>p.total_points_created!=null&&p.creation_dependency_share!=null));
});

test("fixes the global dropdown menu and exposes every section",async()=>{
  const{status,body}=await fetchPage("site-shell.js");assert.equal(status,200);
  for(const route of ["analysis-hub.html","league-statistics.html","team-statistics.html","player-statistics.html","box-score-finder.html","possession-speed.html","late-game-analysis.html","assist-chemistry.html","game-state-performance.html","win-thresholds.html","late-game-foul-dashboard.html","wnbl-hackulator.html"])assert.ok(body.includes(route),route);
  for(const redundant of ["creator-scorer-connections.html","oreb-decision-tree.html","score-pressure.html","quarter-profiles.html","winning-context.html"])assert.ok(!body.includes(redundant),redundant);
  for(const behavior of ['addEventListener("toggle"','other.open=false','addEventListener("click"','e.key==="Escape"','shell.classList.remove("mobileOpen")'])assert.ok(body.includes(behavior),behavior);
  assert.ok(body.includes('a.href="player-statistics.html"'));
});

test("retains complete team, league and box-score pages",async()=>{
  for(const path of ["team-statistics.html","league-statistics.html","box-score-finder.html","team-townsville-fire.html","player-abbey-ellis.html"]){const{status,body}=await fetchPage(path);assert.equal(status,200,path);assert.ok(body.includes("site-shell.js"),path);assert.ok(body.includes("table-enhancements.js"),path)}
  const boxes=JSON.parse(await readFile(new URL("../app/box-scores.json",import.meta.url),"utf8"));assert.equal(boxes.games.length,610);const game=boxes.games.find(g=>g.players.length);const page=await fetchPage(`box-score-${game.game_id}.html`);assert.equal(page.status,200);assert.ok(page.body.includes(game.team_1)&&page.body.includes(game.team_2));
  for(const token of ["Final · WNBL","Away","Home","Box score","Team total","made-attempted","['fg','FG']","['three','3PT']","['ft','FT']"])assert.ok(page.body.includes(token),token);
  for(const removed of ["Team comparison","Game leaders","insightGrid","metricBars"])assert.ok(!page.body.includes(removed),removed);
});

test("retains the validated eight-season analysis datasets",async()=>{
  const d=JSON.parse(await readFile(new URL("../app/data.json",import.meta.url),"utf8")),deep=JSON.parse(await readFile(new URL("../app/deep-dives.json",import.meta.url),"utf8"));
  assert.deepEqual(d.meta.seasons,["2019-20","2020","2021-22","2022-23","2023-24","2024-25","2025-26","2026-27"]);assert.equal(d.meta.games,608);assert.equal(d.meta.possessions,109112.4);assert.equal(d.meta.possession_definition,"Possessions used for PPP calculations");assert.equal(d.players.length,864);assert.equal(d.teams.length,65);
  assert.equal(deep.dependence.length,65);assert.equal(deep.runs.length,65);assert.equal(deep.sustainability.length,65);assert.equal(deep.continuity.length,48);assert.equal(deep.continuity_bins.length,3);assert.equal(deep.continuity_sensitivity.length,3);assert.equal(deep.identity_audit.length,7);assert.ok(deep.connections.length>4000);assert.ok(deep.creation_dependency.length>800);assert.ok(deep.score_pressure.length>300);assert.ok(deep.quarter_profiles.length>200);assert.ok(deep.development.length>250);
});

test("keeps tables sortable, centred, linked and explained",async()=>{
  const enhance=(await fetchPage("table-enhancements.js")).body,css=(await fetchPage("site-shell.css")).body,links=(await fetchPage("profile-links.js")).body;
  for(const token of ["aria-sort","sortAsc","sortDesc","if (th.dataset.sortReady) return","allHeaders","dataset.statHelp","table.tHead.rows.length - 1","On/off / 40","Prior MIN retained","Validation win%","Stabilized saved / 100"])assert.ok(enhance.includes(token),token);
  assert.match(css,/table th,table td\{text-align:center!important\}/);assert.ok(links.includes('"Townsville": "Townsville Fire"'));assert.ok(links.includes('"Miela Goodchild": "Miela Sowah"'));
  const{body}=await fetchPage("team-townsville-fire.html");for(const stat of ["FG%","eFG%","2P%","3P%","FT%","OREB","DREB","FTR","TOV%","PiP"])assert.ok(body.includes(stat),stat);assert.ok(body.includes("th:not([title])")&&body.includes("MutationObserver"));
});

test("indexes every new analysis page for site search",async()=>{
  const index=JSON.parse((await fetchPage("site-index.json")).body);for(const href of ["possession-speed.html","late-game-analysis.html","assist-chemistry.html","game-state-performance.html","player-dependency.html","roster-continuity.html","performance-variance.html","player-statistics.html"])assert.ok(index.some(x=>x.href===href),href);
  assert.ok(!index.some(x=>x.href==="turnover-analysis.html"));
  for(const redundant of ["creator-scorer-connections.html","oreb-decision-tree.html","score-pressure.html","quarter-profiles.html","winning-context.html"])assert.ok(!index.some(x=>x.href===redundant),redundant);
  assert.ok(index.some(x=>x.type==="Team"&&x.title==="Townsville Fire"));assert.ok(index.some(x=>x.type==="Player"&&x.title==="Miela Sowah"));
});

test("ships page-specific analysis data instead of the former combined payload",async()=>{
  const routes={"possession-speed.html":["speed","speed"],"turnover-analysis.html":["turnovers","turnovers"],"after-oreb-analysis.html":["rebounding","oreb"],"kills-analysis.html":["kills","kills"],"late-game-analysis.html":["late","clutch"],"assist-chemistry.html":["chemistry","chemistry"],"win-thresholds.html":["thresholds","thresholdResults"]};
  for(const[path,[focus,key]]of Object.entries(routes)){const{body}=await fetchPage(path),data=jsonScript(body,"data");assert.equal(data.meta.focus,focus,path);assert.ok(data[key].length,path);for(const other of ["speed","turnovers","oreb","kills","clutch","chemistry","thresholdResults"])if(other!==key)assert.equal(data[other].length,0,`${path}: ${other}`)}
});

test("ships page-specific deep-dive data without breadcrumb strips",async()=>{
  const routes={"player-dependency.html":["dependence","dependence"],"roster-continuity.html":["continuity","continuity"],"scoring-runs.html":["runs","runs"],"performance-variance.html":["sustainability","sustainability"],"player-development.html":["development","development"]};
  for(const[path,[focus,key]]of Object.entries(routes)){const{body}=await fetchPage(path),data=jsonScript(body,"deep-data");assert.equal(data.meta.focus,focus,path);assert.ok(data[key].length,path);for(const token of ["analysisRead","relatedAnalysis","Evidence","Sample"])assert.ok(body.includes(token),`${path}: ${token}`);assert.ok(!body.includes("crumb.className='analysisBreadcrumb'"),path)}
  const gameState=await fetchPage("game-state-performance.html"),data=jsonScript(gameState.body,"deep-data");assert.equal(data.meta.focus,"game-state");assert.ok(data.score_pressure.length>300);assert.ok(data.quarter_profiles.length>200);for(const token of ["By score state","By quarter and overtime","analysisDetailPage"])assert.ok(gameState.body.includes(token),token);
});

test("merges connection and OREB detail into their primary analysis pages",async()=>{
  const chemistry=await fetchPage("assist-chemistry.html"),chemData=jsonScript(chemistry.body,"data");assert.ok(chemData.chemistry.length>4000);for(const text of ["Connection lift","Clutch makes","Play types","pageQuery.get('season')","pageQuery.get('team')"])assert.ok(chemistry.body.includes(text),text);
  const oreb=await fetchPage("after-oreb-analysis.html"),orebData=jsonScript(oreb.body,"data");assert.ok(orebData.orebDecision.attack_type.length);assert.ok(orebData.orebDecision.shot_family.length);for(const text of ["Decision tree summary","What follows the offensive rebound","orebDecisionTable","orebShotFamilyTable"])assert.ok(oreb.body.includes(text),text);
  const oldConnections=await fetchPage("creator-scorer-connections.html"),oldOreb=await fetchPage("oreb-decision-tree.html");assert.ok(oldConnections.body.includes('assist-chemistry.html'));assert.ok(oldOreb.body.includes('after-oreb-analysis.html'));
});

test("merges winning context and game-state analyses without losing data",async()=>{
  const thresholds=await fetchPage("win-thresholds.html"),thresholdData=jsonScript(thresholds.body,"data");assert.ok(thresholdData.selectedThresholds.length);assert.ok(thresholdData.thresholdCombinations.length);
  for(const text of ["thresholdColumnHeads","Win probability by threshold","predicted only from seasons that came before it","model_win_probability","rule_label","Rolling team-games","Seasons tested"])assert.ok(thresholds.body.includes(text),text);
  for(const removed of ["thresholdCurve","drawThresholdCurve","All-season model</span><span>Rolling season result","The line is the seven-season estimate. The dots are what actually happened"])assert.ok(!thresholds.body.includes(removed),removed);
  for(const removed of ["Complete games</span>","Metrics tested</span>","PTS and efficiency are closely tied","['direction','Direction'","Seasons represented","['validation_pass','Validated']","All team-games","All win rate","Held-out 95% low","Held-out 95% high"])assert.ok(!thresholds.body.includes(removed),removed);
  for(const removed of ["Held-out win rate is the percentage","first four seasons and tested on the final three","team-games in 2023–24 through 2025–26; 95% interval"])assert.ok(!thresholds.body.includes(removed),removed);
  const points=thresholdData.selectedThresholds.find(r=>r.metric==="points");assert.equal(points.threshold,80);assert.equal(points.rolling_folds,6);assert.equal(String(points.selection_target_reached).toLowerCase(),"true");assert.ok(points.model_win_probability>.7);assert.ok(points.validation_n>400);
  const oldWinning=await fetchPage("winning-context.html"),oldPressure=await fetchPage("score-pressure.html"),oldQuarters=await fetchPage("quarter-profiles.html");assert.ok(oldWinning.body.includes("win-thresholds.html"));assert.ok(oldPressure.body.includes("game-state-performance.html"));assert.ok(oldQuarters.body.includes("game-state-performance.html"));
});

test("keeps threshold charts focused and removes the retired coverage page",async()=>{
  const thresholds=(await fetchPage("win-thresholds.html")).body;for(const token of ["All-season model","selection_target_reached","allRows.slice(-5)"])assert.ok(thresholds.includes(token),token);
  const shell=(await fetchPage("site-shell.js")).body;assert.ok(shell.includes("WNBL Data"));assert.ok(!shell.includes("WNBL INTELLIGENCE"));assert.ok(!shell.includes("data-coverage.html"));
  const index=JSON.parse((await fetchPage("site-index.json")).body);assert.ok(!index.some(x=>x.href==="data-coverage.html"));assert.equal((await fetchPage("data-coverage.html")).status,404);
});

test("explains performance variance in plain basketball language",async()=>{
  const page=(await fetchPage("performance-variance.html")).body;for(const text of ["actual record with the record expected","same season-long points scored and points allowed","Wins +/-","does not adjust for schedule strength","higher number means less consistent shooting"])assert.ok(page.includes(text),text);
});

test("defaults every table to all columns and keeps shared navigation features",async()=>{
  const shell=(await fetchPage("site-shell.js")).body;for(const token of ['applyColumns(table,"all")','table.dataset.presetReady','select.value="all"','["season","team"]'])assert.ok(shell.includes(token),token);assert.ok(!shell.includes('applyColumns(table,"overview")'));const deep=(await fetchPage("game-state-performance.html")).body;assert.ok(deep.includes("history.replaceState"));
  const decision=await fetchPage("decision-tools.html");assert.equal(decision.status,200);assert.ok(decision.body.includes("analysis-hub.html"));
  const page=(await fetchPage("possession-speed.html")).body;for(const text of ["Data from InStat. Last updated:","Related analysis"])assert.ok(page.includes(text),text);
  const index=JSON.parse((await fetchPage("site-index.json")).body);assert.ok(!index.some(x=>x.href==="decision-tools.html"));
});

test("keeps specialist analysis columns visible and moves team analysis to the page bottom",async()=>{
  const shell=(await fetchPage("site-shell.js")).body;assert.ok(shell.includes('applyColumns(table,"all")'));assert.ok(shell.includes("note?note.before(section):content?.append(section)"));
  const dependency=await fetchPage("player-dependency.html");const data=jsonScript(dependency.body,"deep-data");const townsville=data.dependence.find(r=>r.season==="2025-26"&&r.team==="Townsville");for(const key of ["leading_creator","leading_creator_total","creation_dependency_share","leading_scorer","below_average_win_rate","at_or_above_win_rate"])assert.ok(townsville[key]!=null,key);
});

test("formats deep dives as full analysis pages and caps displayed precision",async()=>{
  for(const path of ["player-dependency.html","roster-continuity.html","scoring-runs.html","game-state-performance.html","performance-variance.html","player-development.html"]){const{body}=await fetchPage(path);for(const token of ["analysisDetailPage","group.replaceWith(page)","sectionHead h1","main.content{max-width:1500px"])assert.ok(body.includes(token),`${path}: ${token}`)}
  const enhancement=(await fetchPage("table-enhancements.js")).body;for(const token of ["roundDisplayedStatistics","maximumFractionDigits:2","\\.\\d{3,}"])assert.ok(enhancement.includes(token),token);
});

test("analyses roster continuity, early results and player identity changes",async()=>{
  const{status,body}=await fetchPage("roster-continuity.html");assert.equal(status,200);const data=jsonScript(body,"deep-data"),summary=data.continuity_summary;
  assert.equal(data.meta.focus,"continuity");assert.equal(data.continuity.length,48);assert.equal(summary.early_games,384);assert.equal(summary.early_definition_games,8);assert.equal(summary.high_continuity_team_seasons,11);assert.ok(summary.high_continuity_early_win_rate>summary.lower_continuity_early_win_rate);assert.ok(summary.adjusted_win_rate_change_per_10pp>0);assert.ok(summary.adjusted_margin_change_per_10pp>0);
  for(const text of ["Roster continuity and early results","First-eight win rate by continuity group","Sensitivity to the definition of early season"])assert.ok(body.includes(text),text);
  assert.ok(!body.includes("Player identity audit"));
  for(const mapping of [["Miela Goodchild","Miela Sowah"],["Chelsea Brooks","Chelsea Brook"],["Abby Kate Bishop","Abby Bishop"],["Isabel Borlase","Isobel Borlase"],["Kristy Anne Wallace","Kristy Wallace"],["Caitlin Martin","Caitlyn Martin"]])assert.ok(data.identity_audit.some(r=>r.source_name===mapping[0]&&r.canonical_name===mapping[1]),mapping.join(" → "));
});

test("populates latest player development and links largest runs to games",async()=>{
  const development=await fetchPage("player-development.html"),developmentData=jsonScript(development.body,"deep-data");assert.ok(developmentData.development.filter(r=>r.season==="2026-27").length>50);assert.ok(development.body.includes("previous recorded season"));
  const runs=await fetchPage("scoring-runs.html"),runData=jsonScript(runs.body,"deep-data");assert.ok(runData.runs.every(r=>r.largest_run_game_id));for(const token of ["Largest-run game","box-score-${encodeURIComponent(v)}.html","Box score ↗"])assert.ok(runs.body.includes(token),token);
});

test("adds category tabs to site search and simplifies game-state evidence",async()=>{
  const shell=(await fetchPage("site-shell.js")).body;for(const token of ["siteSearchTabs","Players","Teams","Games","Analysis","searchGroup"])assert.ok(shell.includes(token),token);
  const gameState=(await fetchPage("game-state-performance.html")).body;assert.ok(!gameState.includes("Score state is measured at the start"));assert.ok(gameState.includes("document.querySelector('.analysisRead')?.remove()"));assert.ok(gameState.includes("Margin Impact"));assert.ok(!gameState.includes("Game-state performance"));
});

test("adds rotation compression and a reconciled plus-minus lineup pilot",async()=>{
  const rotation=await fetchPage("rotation-compression.html"),rotationData=jsonScript(rotation.body,"rotation-data");assert.equal(rotation.status,200);assert.equal(rotationData.meta.team_games,1210);assert.equal(rotationData.meta.games,605);assert.equal(rotationData.meta.seasons.length,8);assert.equal(rotationData.bands.length,4);assert.equal(rotationData.team_games.length,1210);for(const token of ["Rotation compression","Top 5 MIN%","q4_net_ppp","Final margin within 10"])assert.ok(rotation.body.includes(token),token);
  const box=await fetchPage("box-score-2357804.html"),boxes=JSON.parse(await readFile(new URL("../app/box-scores.json",import.meta.url),"utf8")),game=boxes.games.find(g=>g.game_id==="2357804");assert.equal(box.status,200);assert.equal(game.players.filter(r=>r.plus_minus!=null).length,18);assert.equal(game.lineups.length,31);assert.equal(game.lineup_validation.player_plus_minus_reconciles,true);assert.equal(game.lineup_validation.lineup_plus_minus_reconciles,true);for(const token of ["Official five-player combinations","Player and lineup plus/minus reconcile","PTS allowed","ORtg","DRtg","+/-"])assert.ok(box.body.includes(token),token);
  const team=(await fetchPage("team-townsville-fire.html")).body,teamData=jsonScript(team,"team-data"),shell=(await fetchPage("site-shell.js")).body;assert.equal(teamData.analysis.rotation.length,8);for(const token of ["rotation-compression.html","Top 5 MIN%","Players used"])assert.ok(shell.includes(token),token);
  const index=JSON.parse((await fetchPage("site-index.json")).body);assert.ok(index.some(x=>x.href==="rotation-compression.html"));
});

test("integrates official player plus-minus across all collected seasons",async()=>{
  const boxes=JSON.parse(await readFile(new URL("../app/box-scores.json",import.meta.url),"utf8"));
  const available=boxes.games.filter(g=>g.plus_minus_status==="complete"),unavailable=boxes.games.filter(g=>g.plus_minus_status.startsWith("unavailable"));
  assert.equal(available.length,608);assert.deepEqual(unavailable.map(g=>g.game_id).sort(),["236477","831081"]);
  assert.equal(available.flatMap(g=>g.players).filter(r=>r.plus_minus==null).length,0);
  assert.ok(available.every(g=>g.plus_minus_validation==="pass"));
  const profiles=JSON.parse(await readFile(new URL("../app/player-profiles.json",import.meta.url),"utf8"));
  assert.ok(profiles.profiles.flatMap(p=>p.season_stats).every(r=>Number.isFinite(r.plus_minus)));
  assert.ok(profiles.profiles.flatMap(p=>p.game_log).every(r=>Number.isFinite(r.plus_minus)));
  const playerPage=(await fetchPage("player-abbey-ellis.html")).body,teamPage=(await fetchPage("team-townsville-fire.html")).body,tablePage=(await fetchPage("player-statistics.html")).body;
  for(const page of [playerPage,teamPage,tablePage])assert.ok(page.includes("+/-"));
});

test("shows all six same-game on-off measures and preserves lineup coverage",async()=>{
  const profiles=JSON.parse(await readFile(new URL("../app/player-profiles.json",import.meta.url),"utf8")),courtney=profiles.profiles.find(p=>p.name==="Courtney Woods").season_stats.find(r=>r.season==="2025-26"&&r.team==="Townsville");
  assert.equal(courtney.games,23);assert.ok(Math.abs(courtney.on_minutes-706.48)<.02);assert.ok(Math.abs(courtney.off_minutes-218.52)<.02);assert.ok(Math.abs(courtney.on_plus_minus_per_40-15.46)<.02);assert.ok(Math.abs(courtney.off_plus_minus_per_40-2.75)<.02);assert.ok(Math.abs(courtney.on_off_plus_minus_per_40-12.71)<.02);assert.ok(Math.abs(courtney.team_relative_plus_minus_per_40-3.72)<.02);assert.ok(Number.isFinite(courtney.on_off_ci_low)&&Number.isFinite(courtney.on_off_ci_high));assert.equal(courtney.on_off_sample,"Strong");
  const teamData=JSON.parse(await readFile(new URL("../app/team-profiles.json",import.meta.url),"utf8")),teamCourtney=teamData.profiles.find(t=>t.slug==="townsville-fire").players.find(r=>r.season==="2025-26"&&r.player_name==="Courtney Woods");assert.ok(Math.abs(teamCourtney.on_off_plus_minus_per_40-12.71)<.02);
  for(const path of ["player-courtney-woods.html","team-townsville-fire.html","player-statistics.html"]){const body=(await fetchPage(path)).body;for(const token of ["On +/- / 40","Off +/- / 40","On/off / 40","+/-"])assert.ok(body.includes(token),`${path}: ${token}`);for(const removed of ["Team-relative / 40","On MIN","Off MIN","95% low","95% high","Uncertainty","Stronger sample","Moderate sample","Low sample"])assert.ok(!body.includes(removed),`${path}: ${removed}`)}
  const boxes=JSON.parse(await readFile(new URL("../app/box-scores.json",import.meta.url),"utf8")),lineupGames=boxes.games.filter(g=>Array.isArray(g.lineups)&&g.lineups.length);assert.equal(lineupGames.length,18);assert.equal(lineupGames[0].game_id,"2357804");
});

test("calculates and displays traditional and WNBL-adjusted Win Shares",async()=>{
  const winShares=JSON.parse(await readFile(new URL("../app/win-shares.json",import.meta.url),"utf8"));
  assert.equal(winShares.meta.player_seasons,864);assert.equal(winShares.meta.team_seasons,65);assert.equal(winShares.records.length,864);
  for(const row of winShares.records){for(const key of ["offensive_win_shares","defensive_win_shares","win_shares","win_shares_per_40","adjusted_win_shares","adjusted_win_shares_per_40"])assert.ok(Number.isFinite(row[key]),`${row.player}: ${key}`);assert.ok(Math.abs(row.win_shares-row.offensive_win_shares-row.defensive_win_shares)<1e-9,row.player)}
  assert.ok(winShares.reconciliation.every(row=>Math.abs(row.adjusted_player_win_shares-row.player_win_shares)<1e-9));
  const profiles=JSON.parse(await readFile(new URL("../app/player-profiles.json",import.meta.url),"utf8")),alicia=profiles.profiles.find(p=>p.name==="Alicia Froling").season_stats.find(r=>r.season==="2025-26"&&r.team==="Townsville");
  assert.ok(alicia.win_shares>5);assert.ok(alicia.adjusted_win_shares>alicia.win_shares);assert.ok(alicia.win_shares_per_40>0);
  for(const path of ["player-alicia-froling.html","team-townsville-fire.html","player-statistics.html"]){const body=(await fetchPage(path)).body;for(const token of ["OWS","DWS","WS/40","Adj WS","Adj WS/40"])assert.ok(body.includes(token),`${path}: ${token}`)}
  const tooltips=(await fetchPage("table-enhancements.js")).body;for(const token of ["offensive_win_shares","defensive_win_shares","adjusted_win_shares","Team totals are preserved"])assert.ok(tooltips.includes(token),token);
});

test("merges Xu Han into Han Xu and keeps the old address usable",async()=>{
  const profiles=JSON.parse(await readFile(new URL("../app/player-profiles.json",import.meta.url),"utf8")),han=profiles.profiles.filter(p=>p.name==="Han Xu"),xu=profiles.profiles.filter(p=>p.name==="Xu Han");
  assert.equal(han.length,1);assert.equal(xu.length,0);assert.equal(han[0].game_log.length,21);assert.equal(han[0].season_stats.length,2);assert.equal(han[0].season_stats.find(r=>r.season==="2025-26").games,18);assert.equal(han[0].season_stats.find(r=>r.season==="2025-26").points,292);assert.equal(han[0].season_stats.find(r=>r.season==="2025-26").plus_minus,229);
  const winShares=JSON.parse(await readFile(new URL("../app/win-shares.json",import.meta.url),"utf8"));assert.equal(winShares.records.filter(r=>r.player==="Han Xu").length,2);assert.equal(winShares.records.filter(r=>r.player==="Xu Han").length,0);
  const canonical=await fetchPage("player-han-xu.html"),alias=await fetchPage("player-xu-han.html");assert.equal(canonical.status,200);assert.equal(alias.status,200);assert.ok(canonical.body.includes('"name":"Han Xu"'));assert.ok(alias.body.includes("player-han-xu.html"));
});

test("ships a separate purple-led visual refresh demo without changing navigation",async()=>{
  const demo=await fetchPage("visual-refresh-demo.html");assert.equal(demo.status,200);for(const token of ["Visual refresh demo · not applied","Player profile","Team page","Analysis page","#7651a8","White","Deep purple","Purple accent","data-panel=\"player\"","data-panel=\"team\"","data-panel=\"analysis\"","Advanced statistics","7th of 114","2nd of 8","1st of 8","Townsville Fire","fire-logo.png","Townsville Fire logo","fire-mark.png","class=\"analysisTitle\"","class=\"tableWrap fullTable\"","<span>DREB%</span>","<span>TOV%</span>"])assert.ok(demo.body.includes(token),token);
  for(const removed of ["<h2>Efficiency trend</h2>","<h2>Team profile</h2>","<h2>Win Shares</h2>","<h2>Rankings</h2>","class=\"rankingCard\"","<span>BLK / game</span>","<span>FG%</span>","<span>Net / 100</span>","class=\"analysisHero\""])assert.ok(!demo.body.includes(removed),removed);
  assert.equal((demo.body.match(/class=\"metricRank\"/g)||[]).length,14);
  const shell=(await fetchPage("site-shell.js")).body,index=JSON.parse((await fetchPage("site-index.json")).body);assert.ok(!shell.includes("visual-refresh-demo.html"));assert.ok(!index.some(x=>x.href==="visual-refresh-demo.html"));
});

test("applies the visual refresh site-wide and packages official WNBL portraits",async()=>{
  for(const path of ["analysis-hub.html","player-abbey-ellis.html","team-townsville-fire.html","league-statistics.html","box-score-2357804.html","wnbl-hackulator.html"]){const body=(await fetchPage(path)).body;assert.ok(body.includes('href="visual-refresh-live.css"'),path)}
  const shell=(await fetchPage("site-shell.js")).body;assert.ok(shell.includes('<img src="fire-mark.png"'));
  const audit=JSON.parse(await readFile(new URL("../app/wnbl-player-photo-audit.json",import.meta.url),"utf8"));assert.equal(audit.matched_count,107);assert.equal(audit.unavailable_count,7);assert.equal(audit.matched_count+audit.unavailable_count,114);
  const profiles=JSON.parse(await readFile(new URL("../app/player-profiles.json",import.meta.url),"utf8")),latest=profiles.profiles.filter(profile=>profile.season_stats.some(row=>row.season==="2025-26"));assert.equal(latest.filter(profile=>profile.photo.startsWith("player-photos/")).length,107);
  const amy=(await fetchPage("player-amy-atwell.html")).body;assert.ok(amy.includes('"photo":"player-photos/amy-atwell.webp"'));
});
