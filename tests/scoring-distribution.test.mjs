import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { buildDistribution, teamGames, selectGames, summarize, leagueBenchmark, depthResults } from '../static/scoring-distribution-core.js';

const source = JSON.parse(await readFile(new URL('../app/box-scores.json', import.meta.url)));
const games = buildDistribution(source.games.filter(g => g.season === '2026-27' && g.game_date <= '2026-11-22'));
const fire = teamGames(games, 'Townsville Fire');
const close = (actual, target) => assert.ok(Math.abs(actual - target) < 0.00001, actual + ' differs from ' + target);

test('reconciles the two Sydney event-log adjustments and keeps the published data intact', () => {
  for (const [id, name, expected] of [['2497248','Shuyu Yang',20], ['2497264','Lauren Nicholson',18]]) {
    const p = games.find(g => g.id === id).sides.flatMap(s => s.players).find(p => p.name === name);
    assert.equal(p.points, expected);
    assert.equal(source.games.find(g => String(g.game_id) === id).players.find(p => p.player === name).points, expected - 2);
  }
});
test('distinguishes nightly rank shares, fixed players and team points in the Fire’s first six', () => {
  const rows = selectGames(fire, 'first6'), stats = summarize(rows);
  assert.equal(stats.points, 516);
  assert.equal(stats.fixedPoints, 454);
  assert.equal(stats.players[0].name, 'Courtney Woods');
  close(stats.nightlyFive, 0.941553);
  close(stats.ranks[0].share, 0.339688);
  close(stats.ranks[4].ppg, 8);
  assert.deepEqual(rows[4].ranks, [24,21,20,16,15]);
  assert.equal(stats.fiveDouble, 1);
});
test('custom, last-two and empty windows use team-relative game numbers', () => {
  assert.deepEqual(selectGames(fire,'custom',7,8), selectGames(fire,'last2'));
  assert.equal(summarize(selectGames(fire,'last2')).fiveDouble, 2);
  assert.equal(summarize(selectGames(fire,'custom',9,12)), null);
});
test('league comparisons weight team-games equally and count matched fixtures once', () => {
  const all = [...new Set(games.flatMap(g => g.sides.map(s => s.team)))].flatMap(t => teamGames(games,t));
  assert.equal(all.length,64);
  close(leagueBenchmark(all).nightlyFive,0.864387);
  assert.deepEqual(depthResults(all), { games:32, more:[21,5], five:[9,0] });
  assert.deepEqual(depthResults(fire), { games:0, more:[0,0], five:[0,0] });
});
