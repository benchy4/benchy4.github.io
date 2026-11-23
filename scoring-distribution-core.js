// The two Sydney overrides use the event-log totals documented on these box scores.
const corrections = new Map([
  ['2497248:522850', { box: 18, verified: 20 }],
  ['2497264:708901', { box: 16, verified: 18 }]
]);
const sum = values => values.reduce((total, value) => total + value, 0);
const mean = values => values.length ? sum(values) / values.length : null;
const rankPlayers = (a, b) => b.points - a.points || a.name.localeCompare(b.name) || a.id.localeCompare(b.id);

export function buildDistribution(source) {
  return [...source].sort((a, b) => a.game_date.localeCompare(b.game_date) || String(a.game_id).localeCompare(String(b.game_id)))
    .map(game => {
      const sides = [1, 2].map(side => {
        const team = game['team_' + side];
        const score = Number(game['score_' + side]);
        const players = game.players.filter(p => p.team === team && (Number(p.points) > 0 || /[1-9]/.test(p.minutes || '')))
          .map(p => {
            const id = String(p.hudl_player_id || p.player);
            const box = Number(p.points);
            const adjustment = corrections.get(game.game_id + ':' + id);
            const points = adjustment?.box === box ? adjustment.verified : box;
            return { id, name: p.player, points };
          }).sort(rankPlayers);
        if (score <= 0 || sum(players.map(p => p.points)) !== score) {
          throw new Error('Player points do not reconcile for ' + team + ' in game ' + game.game_id);
        }
        return { team, score, players };
      });
      return { id: String(game.game_id), season: game.season, date: game.game_date, sides };
    });
}

export function teamGames(games, team) {
  const rows = [];
  for (const game of games) {
    const side = game.sides.find(s => s.team === team);
    if (!side) continue;
    const opponent = game.sides.find(s => s !== side);
    const ranks = Array.from({ length: 5 }, (_, i) => side.players[i]?.points ?? 0);
    rows.push({ ...side, id: game.id, date: game.date, opponent: opponent.team, against: opponent.score,
      number: rows.length + 1, ranks, five: sum(ranks), doubleFigures: side.players.filter(p => p.points >= 10).length });
  }
  return rows;
}

export function selectGames(rows, mode, from, to) {
  if (mode === 'first6') return rows.slice(0, 6);
  if (mode === 'last2') return rows.slice(-2);
  if (mode === 'custom') return rows.filter(row => row.number >= from && row.number <= to);
  return rows;
}

export function summarize(rows) {
  if (!rows.length) return null;
  const byPlayer = new Map();
  for (const game of rows) for (const p of game.players) {
    const player = byPlayer.get(p.id) || { id: p.id, name: p.name, gp: 0, points: 0 };
    player.gp++;
    player.points += p.points;
    byPlayer.set(p.id, player);
  }
  const players = [...byPlayer.values()].sort(rankPlayers);
  const points = sum(rows.map(g => g.score));
  const fixedPoints = sum(players.slice(0, 5).map(p => p.points));
  const ranks = Array.from({ length: 5 }, (_, i) => ({
    share: mean(rows.map(g => g.ranks[i] / g.five)),
    ppg: mean(rows.map(g => g.ranks[i]))
  }));
  return { count: rows.length, points, players, fixedPoints, fixedShare: fixedPoints / points, ranks,
    fixedThree: sum(players.slice(0, 3).map(p => p.points)) / points,
    nightlyFive: mean(rows.map(g => g.five / g.score)),
    nightlyThree: mean(rows.map(g => sum(g.ranks.slice(0, 3)) / g.score)),
    others: mean(rows.map(g => g.score - g.five)),
    fiveDouble: rows.filter(g => g.doubleFigures >= 5).length };
}

// A player can represent two clubs. League rank benchmarks only need the ranked game scores.
export function leagueBenchmark(rows) {
  return {
    nightlyFive: mean(rows.map(g => g.five / g.score)),
    shares: Array.from({ length: 5 }, (_, i) => mean(rows.map(g => g.ranks[i] / g.five)))
  };
}

export function depthResults(rows) {
  const opponents = new Map();
  const results = { games: 0, more: [0, 0], five: [0, 0] };
  for (const row of rows) {
    const other = opponents.get(row.id);
    if (!other) { opponents.set(row.id, row); continue; }
    results.games++;
    if (row.doubleFigures === other.doubleFigures) continue;
    const [deeper, fewer] = row.doubleFigures > other.doubleFigures ? [row, other] : [other, row];
    const outcome = deeper.score > fewer.score ? 0 : 1;
    results.more[outcome]++;
    if (deeper.doubleFigures >= 5 && fewer.doubleFigures < 5) results.five[outcome]++;
  }
  return results;
}
