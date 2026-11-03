import assert from 'node:assert/strict';
import test from 'node:test';
import {readFile} from 'node:fs/promises';
const read=async name=>JSON.parse(await readFile(new URL('../app/'+name+'.json',import.meta.url),'utf8'));
const current='2026-27';

test('includes all 17 current-season games, reconciled lineups and nine clubs',async()=>{
  const boxes=await read('box-scores'),games=boxes.games.filter(g=>g.season===current);
  assert.equal(games.length,17);
  assert.equal(new Set(games.flatMap(g=>[g.team_1,g.team_2])).size,9);
  assert.deepEqual(games.map(g=>Number(g.game_id)).sort(),Array.from({length:17},(_,i)=>2497244+i));
  for(const g of games){
    assert.equal(g.plus_minus_validation,'pass');
    assert.ok(g.players.every(p=>Number.isFinite(p.plus_minus)));
    for(const [team,score,opp] of [[g.team_1,g.score_1,g.score_2],[g.team_2,g.score_2,g.score_1]]){
      const lineups=g.lineups.filter(l=>l.team===team);
      assert.ok(lineups.length);
      assert.ok(lineups.every(l=>l.players.length===5));
      assert.equal(lineups.reduce((n,l)=>n+l.points,0),score);
      assert.equal(lineups.reduce((n,l)=>n+l.plus_minus,0),score-opp);
    }
  }
  const discrepancy=games.find(g=>g.game_id==='2497248');
  assert.match(discrepancy.source_note,/93 points/);
  assert.equal(discrepancy.score_1,95);
  assert.equal(discrepancy.players.filter(p=>p.team===discrepancy.team_1).reduce((n,p)=>n+p.points,0),93);
});

test('refreshes analytical families and current team records',async()=>{
  const [data,deep,hack,teams,rotation]=await Promise.all(['data','deep-dives','hackulator-data','team-profiles','rotation-compression'].map(read));
  assert.equal(data.meta.games,608);
  assert.equal(data.meta.latest_game_date,'2026-11-03');
  assert.equal(data.meta.current_season_complete,false);
  for(const key of ['kills','clutch','networks','players','defensePlayers','teams'])assert.ok(data[key].some(r=>r.season===current),key);
  for(const key of ['connections','creation_dependency','dependence','runs','score_pressure','quarter_profiles','sustainability','development'])assert.ok(deep[key].some(r=>r.season===current),key);
  assert.ok(!deep.continuity.some(r=>r.season===current),'Do not mix partial seasons into the first-eight-game model');
  assert.ok(hack.meta.seasons.includes(current));
  assert.equal(rotation.team_games.filter(r=>r.season===current).length,34);
  const currentTeams=teams.profiles.flatMap(p=>p.season_stats.filter(r=>r.season===current));
  assert.equal(currentTeams.length,9);
  assert.equal(currentTeams.reduce((n,t)=>n+t.games,0),34);
  assert.equal(currentTeams.reduce((n,t)=>n+t.wins,0),17);
  assert.equal(currentTeams.reduce((n,t)=>n+t.losses,0),17);
  const tasmania=teams.profiles.find(t=>t.slug==='tasmania-jewels');
  assert.equal(tasmania.season_stats[0].games,3);
  assert.equal(tasmania.season_stats[0].wins,2);
});

test('preserves the public Index address and offers the current-season filter',async()=>{
  const home=await readFile(new URL('../public/Index.html',import.meta.url),'utf8');
  assert.equal(home,await readFile(new URL('../public/index.html',import.meta.url),'utf8'));
  assert.match(home,/17 completed games through 3 Nov 2026/);
  assert.match(home,/box-score-finder.html\?season=2026-27/);
  const dashboard=await readFile(new URL('../public/late-game-foul-dashboard.html',import.meta.url),'utf8');
  const evidence=JSON.parse(dashboard.match(/<script id="foul-data" type="application\/json">([\s\S]*?)<\/script>/)[1]);
  assert.ok(evidence.records.some(r=>r.season===current));
});
