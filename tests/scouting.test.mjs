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
