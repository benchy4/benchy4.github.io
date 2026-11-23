import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';

const load = async file => JSON.parse(await readFile(new URL('../app/scouting/' + file + '.json', import.meta.url)));
const index = await load('index');

test('mapped games, audited attempts and local box-score links agree', async () => {
  for (const season of new Set(index.games.map(g=>g.season))) {
    const games = index.games.filter(g=>g.season===season);
    const shots = await load(season);
    assert.deepEqual(new Set(shots.map(g=>g.id)), new Set(games.filter(g=>g.verified).map(g=>g.id)));
    for (const g of games.filter(g=>g.box)) {
      assert.match(await readFile(new URL('../box-score-'+g.box+'.html',import.meta.url),'utf8'), /id="game-data"/);
    }
    for (const g of shots) {
      const {periods} = games.find(x=>x.id===g.id);
      for (const [side,player,period,,x,y,made,value] of g.shots) {
        assert.ok([0,1].includes(side) && g.players[player] && period>=1 && period<=periods);
        assert.ok(x>=0 && x<=100 && y>=0 && y<=100 && [0,1].includes(made) && [2,3].includes(value));
      }
    }
  }
});

test('clip counts and each player split retain their own game scope and denominators', () => {
  for (const type of ['coverage','impact']) {
    for (const [season, teams] of Object.entries(index[type])) {
      for (const [team,scope] of Object.entries(teams)) {
        const games=scope.games.map(id=>index.games.find(g=>g.id===id));
        assert.ok(games.every(g=>g?.season===season && [g.home,g.away].includes(team)));
        if (type==='coverage') {
          for (const side of [scope.offence,scope.defence]) {
            const counts=Object.values(side.counts);
            if (counts.every(Number.isFinite)) assert.equal(counts.reduce((a,b)=>a+b,0),side.total);
          }
        } else {
          const sums = s=>['seconds','points','allowed','possessions','opponent_possessions'].map(k=>s.on[k]+s.off[k]);
          const splits=Object.values(scope.players);
          for (const s of splits) assert.deepEqual(sums(s),sums(splits[0]));
          const onSeconds=splits.reduce((total,s)=>total+s.on.seconds,0);
          assert.equal(onSeconds,5*sums(splits[0])[0]);
        }
      }
    }
  }
});

test('PnR efficiency uses full possessions and keeps unclassified turnovers in the sample', async () => {
  const records = await load('pnr-efficiency');
  for (const [id, teams] of Object.entries(records)) {
    const game = index.games.find(g => g.id === id);
    assert.ok(game?.box);
    if (teams === null) continue;
    assert.deepEqual(new Set(Object.keys(teams)), new Set([game.home, game.away]));
    for (const group of Object.values(teams)) {
      for (const {possessions, points, turnovers} of Object.values(group)) {
        assert.ok(Number.isInteger(possessions) && possessions > 0);
        assert.ok(Number.isInteger(points) && points >= 0);
        assert.ok(Number.isInteger(turnovers) && turnovers >= 0 && turnovers <= possessions);
      }
    }
  }
  const fireFlames = records[index.games.find(g => g.box === '2497254').id];
  assert.deepEqual(fireFlames.TSV.Over, {points:31, possessions:20, turnovers:0});
  assert.deepEqual(fireFlames.TSV.Untagged, {points:0, possessions:7, turnovers:7});
  assert.deepEqual(fireFlames.SYD['Multiple coverages'], {points:2, possessions:1, turnovers:0});
  const total = Object.values(fireFlames).flatMap(Object.values).reduce((n, s) => n + s.possessions, 0);
  assert.equal(total, 50);
});
