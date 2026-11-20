// Shared by the static builder, browser and statistics tests.
export const countKeys = ['games', 'minutes_seconds', 'points', 'rebounds', 'offensive_rebounds',
  'defensive_rebounds', 'assists', 'steals', 'blocks', 'turnovers', 'fouls', 'plus_minus',
  'fg_made', 'fg_attempted', 'three_made', 'three_attempted', 'ft_made', 'ft_attempted',
  'wins', 'losses', 'points_allowed', 'possessions', 'defensive_possessions'];

export function sumRows(rows) {
  // Missing coverage must stay missing, rather than becoming a recorded zero.
  return Object.fromEntries(countKeys.map(key => [key, rows.length && rows.every(row => Number.isFinite(row[key]))
    ? rows.reduce((sum, row) => sum + row[key], 0) : null]));
}

const ratio = (a, b) => Number.isFinite(a) && Number.isFinite(b) && b > 0 ? a / b : null;
export function metricValue(row, key, basis = 'game') {
  if (!row) return null;
  if (key === 'games') return row.kind === 'seasons' ? row.games / 2 : row.games;
  const twoMade = Number.isFinite(row.fg_made) && Number.isFinite(row.three_made) ? row.fg_made - row.three_made : null;
  const twoAttempts = Number.isFinite(row.fg_attempted) && Number.isFinite(row.three_attempted) ? row.fg_attempted - row.three_attempted : null;
  const rates = {
    fg_percentage: () => ratio(row.fg_made, row.fg_attempted),
    two_percentage: () => ratio(twoMade, twoAttempts),
    three_percentage: () => ratio(row.three_made, row.three_attempted),
    ft_percentage: () => ratio(row.ft_made, row.ft_attempted),
    effective_fg_percentage: () => ratio(Number.isFinite(row.fg_made) && Number.isFinite(row.three_made) ? row.fg_made + .5 * row.three_made : null, row.fg_attempted),
    win_percentage: () => ratio(row.wins, row.games),
    ppp: () => ratio(row.points, row.possessions),
    defensive_ppp: () => ratio(row.points_allowed, row.defensive_possessions),
    average_margin: () => ratio(Number.isFinite(row.points) && Number.isFinite(row.points_allowed) ? row.points - row.points_allowed : null, row.games)
  };
  if (rates[key]) return rates[key]();
  let value = key === 'two_made' ? twoMade : key === 'two_attempted' ? twoAttempts : row[key];
  if (!Number.isFinite(value)) return null;
  if (key === 'minutes_seconds') value /= 60;
  if (['wins', 'losses', 'team_count'].includes(key)) return value;
  return basis === 'game' ? ratio(value, row.games) : value;
}

const metric = (key, label, group, direction = null, format = 'count', kinds = null) => ({key, label, group, direction, format, kinds});
export const metrics = [
  metric('games', 'Games played', 'overview', null, 'integer'),
  metric('team_count', 'Teams', 'overview', null, 'integer', ['seasons']),
  metric('wins', 'Wins', 'overview', 'high', 'integer', ['teams']),
  metric('losses', 'Losses', 'overview', 'low', 'integer', ['teams']),
  metric('win_percentage', 'Win %', 'overview', 'high', 'percent', ['teams']),
  metric('minutes_seconds', 'Minutes', 'overview', null, 'count', ['players']),
  metric('points', 'Points', 'overview', 'high'),
  metric('points_allowed', 'Points allowed', 'overview', 'low', 'count', ['teams', 'seasons']),
  metric('average_margin', 'Average margin', 'overview', 'high', 'decimal', ['teams']),
  metric('rebounds', 'Rebounds', 'overview', 'high'),
  metric('assists', 'Assists', 'overview', 'high'),
  metric('steals', 'Steals', 'overview', 'high'),
  metric('blocks', 'Blocks', 'overview', 'high'),
  metric('turnovers', 'Turnovers', 'overview', 'low'),
  metric('fouls', 'Fouls', 'other', 'low'),
  metric('plus_minus', 'Plus / minus', 'other', 'high', 'count', ['players']),
  metric('offensive_rebounds', 'Offensive rebounds', 'other', 'high'),
  metric('defensive_rebounds', 'Defensive rebounds', 'other', 'high'),
  metric('fg_made', 'Field goals made', 'shooting'),
  metric('fg_attempted', 'Field goals attempted', 'shooting'),
  metric('fg_percentage', 'Field goal %', 'shooting', 'high', 'percent'),
  metric('effective_fg_percentage', 'Effective field goal %', 'shooting', 'high', 'percent'),
  metric('two_made', 'Two-pointers made', 'shooting'),
  metric('two_attempted', 'Two-pointers attempted', 'shooting'),
  metric('two_percentage', 'Two-point %', 'shooting', 'high', 'percent'),
  metric('three_made', 'Three-pointers made', 'shooting'),
  metric('three_attempted', 'Three-pointers attempted', 'shooting'),
  metric('three_percentage', 'Three-point %', 'shooting', 'high', 'percent'),
  metric('ft_made', 'Free throws made', 'shooting'),
  metric('ft_attempted', 'Free throws attempted', 'shooting'),
  metric('ft_percentage', 'Free throw %', 'shooting', 'high', 'percent'),
  metric('ppp', 'Offensive PPP', 'other', 'high', 'ppp', ['teams', 'seasons']),
  metric('defensive_ppp', 'Defensive PPP', 'other', 'low', 'ppp', ['teams', 'seasons'])
];

export function buildComparisonData(players, teams, meta) {
  const playerRows = players.flatMap(player => [...new Set(player.season_stats.map(row => row.season))].map(season => {
    const stints = player.season_stats.filter(row => row.season === season);
    return {...sumRows(stints), kind: 'players', slug: player.slug, name: player.name, season,
      team: [...new Set(stints.map(row => row.team))].join(' / ')};
  }));
  const teamRows = teams.flatMap(team => team.season_stats.map(row => {
    const advanced = team.advanced.find(item => item.season === row.season);
    return {...sumRows([row]), kind: 'teams', slug: team.slug, name: team.name, season: row.season,
      possessions: advanced?.possessions ?? null, defensive_possessions: advanced?.defensive_possessions ?? null};
  }));
  const seasonRows = meta.seasons.map(season => {
    const rows = teamRows.filter(row => row.season === season);
    return {...sumRows(rows), kind: 'seasons', slug: season, name: season, season, team_count: rows.length};
  }).filter(row => row.games > 0);
  return {meta: {seasons: meta.seasons, current_season: meta.current_season,
    current_season_complete: meta.current_season_complete, latest_game_date: meta.latest_game_date},
  players: playerRows, teams: teamRows, seasons: seasonRows};
}

export function formatValue(value, metric, basis = 'game', difference = false) {
  if (!Number.isFinite(value)) return '—';
  const digits = metric.format === 'integer' ? 0 : metric.format === 'ppp' ? 3
    : metric.format === 'percent' || metric.format === 'decimal' || basis === 'game' || metric.key === 'minutes_seconds' ? 1 : 0;
  const scaled = metric.format === 'percent' ? value * 100 : value;
  const rounded = Number(scaled.toFixed(digits));
  const sign = difference && rounded > 0 ? '+' : '';
  const suffix = metric.format === 'percent' ? difference ? ' pp' : '%' : '';
  return sign + (Object.is(rounded, -0) ? 0 : rounded).toLocaleString('en-AU', {minimumFractionDigits: digits, maximumFractionDigits: digits}) + suffix;
}

export function readSelection(data, params) {
  const mode = ['players', 'teams', 'seasons'].includes(params.get('mode')) ? params.get('mode') : 'players';
  const basis = params.get('basis') === 'total' ? 'total' : 'game';
  const group = ['overview', 'shooting', 'all'].includes(params.get('stats')) ? params.get('stats') : 'overview';
  const requested = params.getAll('pick').slice(0, 4);
  const latest = data.meta.seasons.includes(params.get('season')) ? params.get('season') : data.meta.seasons.at(-1);
  const defaults = mode === 'seasons' ? [...data.seasons].reverse().slice(0, 2)
    : data[mode].filter(row => row.season === latest).sort((a, b) => (b.points ?? -1) - (a.points ?? -1)).slice(0, 2);
  const picks = requested.length ? requested.map(pick => {
    const [slug, season] = mode === 'seasons' ? [pick, pick] : pick.split('|');
    return {slug, season};
  }) : defaults.map(({slug, season}) => ({slug, season}));
  // A profile shortcut supplies one pick; leave the other slot open for the user.
  if (picks.length < 2) picks.push({slug: '', season: picks[0]?.season || latest});
  const invalid = picks.some(pick => pick.slug && !data[mode].some(row => row.slug === pick.slug && row.season === pick.season));
  return {mode, basis, group, picks, invalid};
}

export function selectionParams(state) {
  const params = new URLSearchParams({mode: state.mode, basis: state.basis, stats: state.group});
  for (const pick of state.picks) params.append('pick', state.mode === 'seasons' ? pick.season || '' : `${pick.slug || ''}|${pick.season || ''}`);
  return params;
}
