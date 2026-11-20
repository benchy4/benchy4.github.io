import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {sumRows, buildComparisonData, metricValue, formatValue, metrics, readSelection, selectionParams} from '../static/comparison-core.js';

const load = async path => JSON.parse(await readFile(new URL('../' + path, import.meta.url), 'utf8'));
const data = await load('comparison-data.json');
const players = (await load('app/player-profiles.json')).profiles;
const teams = (await load('app/team-profiles.json')).profiles;
const games = (await load('app/box-scores.json')).games;

test('per-game and totals preserve rates, games and missing values', () => {
  const row = {games: 4, points: 80, minutes_seconds: 6000, fg_made: 20, fg_attempted: 50, three_made: 10, three_attempted: 25, ft_made: 0, ft_attempted: 0};
  assert.equal(metricValue(row, 'points'), 20);
  assert.equal(metricValue(row, 'points', 'total'), 80);
  assert.equal(metricValue(row, 'games'), 4);
  assert.equal(metricValue(row, 'minutes_seconds'), 25);
  assert.equal(metricValue(row, 'effective_fg_percentage'), .5);
  assert.equal(metricValue(row, 'fg_percentage', 'total'), .4);
  assert.equal(metricValue(row, 'two_percentage'), .4);
  assert.equal(metricValue(row, 'ft_percentage'), null);
  assert.equal(metricValue(row, 'assists'), null);
  assert.equal(metricValue({...row, assists: 0}, 'assists'), 0);
  assert.equal(metricValue({...row, games: 0}, 'points'), null);
  assert.equal(sumRows([{points: 4}, {points: null}]).points, null);
  assert.equal(sumRows([]).points, null);
});

test('all player stints contribute once, including transfers within one season', () => {
  for (const player of players) {
    for (const season of new Set(player.season_stats.map(row => row.season))) {
      const source = player.season_stats.filter(row => row.season === season);
      const matches = data.players.filter(row => row.slug === player.slug && row.season === season);
      assert.equal(matches.length, 1);
      for (const key of ['games', 'points', 'fg_made', 'fg_attempted', 'minutes_seconds']) {
        assert.equal(matches[0][key], source.reduce((sum, row) => sum + row[key], 0));
      }
    }
  }
  const transfer = data.players.find(row => row.name === 'Shyla Jade Heal' && row.team.includes(' / '));
  assert.ok(transfer, 'preserve both teams on a transferred player season');
});

test('league seasons count each game once and weight percentages by attempts', () => {
  for (const season of data.seasons) {
    const source = teams.flatMap(team => team.season_stats.filter(row => row.season === season.season));
    assert.equal(metricValue(season, 'games'), games.filter(game => game.season === season.season).length);
    const points = source.reduce((sum, row) => sum + row.points, 0);
    const appearances = source.reduce((sum, row) => sum + row.games, 0);
    assert.equal(metricValue(season, 'points'), points / appearances);
    assert.equal(metricValue(season, 'points', 'total'), points);
    assert.equal(metricValue(season, 'fg_percentage'), source.reduce((sum, row) => sum + row.fg_made, 0) / source.reduce((sum, row) => sum + row.fg_attempted, 0));
    assert.equal(metricValue(season, 'ppp'), points / data.teams.filter(row => row.season === season.season).reduce((sum, row) => sum + row.possessions, 0));
  }
});

test('synthetic unequal seasons do not average percentages or divide by matches', () => {
  const sample = buildComparisonData([], [
    {slug: 'a', name: 'A', season_stats: [{season: 's', games: 1, points: 80, fg_made: 1, fg_attempted: 2}], advanced: []},
    {slug: 'b', name: 'B', season_stats: [{season: 's', games: 3, points: 220, fg_made: 9, fg_attempted: 30}], advanced: []}
  ], {seasons: ['s']}).seasons[0];
  assert.equal(metricValue(sample, 'fg_percentage'), 10 / 32);
  assert.equal(metricValue(sample, 'points'), 75);
  assert.equal(metricValue(sample, 'games'), 2);
  assert.equal(metricValue(sample, 'ppp'), null);
});

test('share links round trip modes, independent seasons, empty slots and display settings', () => {
  for (const mode of ['players', 'teams', 'seasons']) {
    const state = readSelection(data, new URLSearchParams({mode}));
    state.basis = 'total'; state.group = 'shooting';
    state.picks.push({slug: '', season: ''});
    const restored = readSelection(data, selectionParams(state));
    assert.deepEqual(restored, state);
    assert.equal(state.picks.length, 3);
  }
  const shortcut = readSelection(data, new URLSearchParams('mode=players&pick=abbey-ellis%7C2025-26'));
  assert.equal(shortcut.picks[0].slug, 'abbey-ellis');
  assert.equal(shortcut.picks[1].slug, '');
  assert.equal(readSelection(data, new URLSearchParams('mode=players&pick=missing%7C1900')).invalid, true);
  const bounded = readSelection(data, new URLSearchParams('mode=seasons&pick=2020&pick=2020&pick=2020&pick=2020&pick=2020'));
  assert.equal(bounded.picks.length, 4);
});

test('differences use percentage points, retain zero and suppress negative zero', () => {
  const percentage = metrics.find(metric => metric.key === 'fg_percentage');
  assert.equal(formatValue(.1, percentage, 'game', true), '+10.0 pp');
  assert.equal(formatValue(-.000001, percentage, 'game', true), '0.0 pp');
  assert.equal(formatValue(0, percentage), '0.0%');
  assert.equal(formatValue(null, percentage), '—');
});

test('static destinations include comparison page, data, scripts and navigation', async () => {
  for (const prefix of ['', 'public/', 'dist/client/']) {
    const page = await readFile(new URL('../' + prefix + 'compare.html', import.meta.url), 'utf8');
    assert.match(page, /id="comparisonWorkspace"/);
    assert.match(page, /type="module" src="comparison.js"/);
    assert.doesNotMatch(page, /src="table-enhancements.js"/);
    assert.deepEqual(await load(prefix + 'comparison-data.json'), data);
    for (const name of ['comparison-core.js', 'comparison.js', 'comparison.css']) {
      assert.equal(await readFile(new URL('../' + prefix + name, import.meta.url), 'utf8'), await readFile(new URL('../static/' + name, import.meta.url), 'utf8'));
    }
    const shell = await readFile(new URL('../' + prefix + 'site-shell.js', import.meta.url), 'utf8');
    assert.match(shell, /href="compare.html"/);
    assert.match(shell, /Compare this /);
    assert.ok((await load(prefix + 'site-index.json')).some(row => row.href === 'compare.html'));
  }
});
