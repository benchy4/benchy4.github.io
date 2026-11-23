import { teamGames, selectGames, summarize, leagueBenchmark, depthResults } from './scoring-distribution-core.js';

const games = JSON.parse(document.getElementById('distribution-data').textContent);
const get = id => document.getElementById('sd-' + id);
const esc = value => String(value).replace(/[&<>"']/g, ch => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[ch]));
const pct = value => value == null ? '—' : (value * 100).toFixed(1) + '%';
const dec = value => value == null ? '—' : value.toFixed(1);
const day = new Intl.DateTimeFormat('en-AU', { day: 'numeric', month: 'short', timeZone: 'UTC' });
const date = value => day.format(new Date(value + 'T12:00:00Z'));
const short = team => ({ 'University of Canberra Capitals': 'UC Capitals', 'Southside Melbourne Flyers': 'Southside Flyers' }[team] || team);
const teams = [...new Set(games.flatMap(game => game.sides.map(side => side.team)))].sort();
const schedules = new Map(teams.map(team => [team, teamGames(games, team)]));
const maxGames = Math.max(1, ...Array.from(schedules.values(), rows => rows.length));
const labels = ['1st', '2nd', '3rd', '4th', '5th'];
const modes = ['all', 'first6', 'last2', 'custom'];
const params = new URLSearchParams(location.search);
const slug = name => name.toLowerCase().replace(/[^a-z0-9]+/g, ' ').trim();
const match = (params.get('team') || '').trim();
const teamMatch = match && teams.find(t => [t, short(t)].some(n => slug(n) === slug(match) || slug(n).startsWith(slug(match) + ' ')));
const gameNumber = (value, fallback) => {
  const n = Number(value);
  return Number.isInteger(n) && n > 0 ? Math.min(n, maxGames) : fallback;
};
const option = (text, value) => new Option(text, value);
const cell = value => '<td>' + value + '</td>';
const row = (label, cells, attrs = '') => '<tr' + attrs + '><th scope="row">' + label + '</th>' + cells.map(cell).join('') + '</tr>';
const emptyRow = (n, text) => '<tr><td colspan="' + n + '">' + esc(text) + '</td></tr>';
const selections = () => ({ team: get('team').value, mode: get('range').value, from: Number(get('from').value), to: Number(get('to').value) });

function selectionUrl(team, mode, from, to) {
  const url = new URL(location.href);
  url.searchParams.set('team', team);
  if (mode === 'all') url.searchParams.delete('range'); else url.searchParams.set('range', mode);
  for (const [key, value] of [['from', from], ['to', to]]) {
    if (mode === 'custom') url.searchParams.set(key, value); else url.searchParams.delete(key);
  }
  return url;
}

function bar(name, shares) {
  const segments = shares.map((s, i) => '<span class="sd-c' + (i + 1) + '" style="width:' + (100 * s) + '%">' + Math.round(s * 100) + '%</span>').join('');
  return '<div class="sd-bar-row"><span class="sd-bar-label">' + esc(name) + '</span><div class="sd-bar" aria-hidden="true">' + segments + '</div></div>';
}
function render() {
  const { team, mode, from, to } = selections();
  get('custom').hidden = mode !== 'custom';
  const league = teams.map(name => {
    const rows = selectGames(schedules.get(name), mode, from, to);
    return { name, rows, stats: summarize(rows) };
  }).sort((a,b) => (b.stats?.nightlyFive ?? -1) - (a.stats?.nightlyFive ?? -1) || a.name.localeCompare(b.name));
  const { rows, stats } = league.find(x => x.name === team);
  const leagueRows = league.flatMap(t => t.rows);
  const benchmark = leagueBenchmark(leagueRows);
  const results = depthResults(leagueRows);
  get('scope').textContent = games[0].season.replace('-', '–') + ' · Through ' + date(games.at(-1).date) + ' ' + games.at(-1).date.slice(0,4);
  get('team-title').textContent = short(team);
  get('period').textContent = rows.length ? rows.length + (rows.length === 1 ? ' game' : ' games') + ' · ' + date(rows[0].date) + (rows.length > 1 ? ' – ' + date(rows.at(-1).date) : '') + ' · ' + stats.points + ' points' : 'No games for this team in the selected range.';
  const metrics = [[pct(stats?.nightlyFive),'Nightly top-five share'],[pct(stats?.fixedShare),'Fixed top-five share'],
    [dec(stats?.others),'PPG outside the nightly five'],[stats ? stats.fiveDouble + ' / ' + rows.length : '—','Games with five in double figures']];
  get('metrics').innerHTML = metrics.map(([v,label]) => '<div class="sd-metric"><strong>' + v + '</strong><span>' + label + '</span></div>').join('');
  get('bars').innerHTML = (stats ? bar(short(team), stats.ranks.map(r => r.share)) : '') + (benchmark.nightlyFive != null ? bar('League', benchmark.shares) : '');
  get('ranks').innerHTML = labels.map((label,i) => row('<i aria-hidden="true" class="sd-dot sd-c' + (i+1) + '"></i>' + label,
    [pct(stats?.ranks[i].share), pct(benchmark.shares[i]), dec(stats?.ranks[i].ppg)])).join('');
  get('league').innerHTML = league.map(({name,stats:s}) => row('<a class="sd-link" href="' + esc(selectionUrl(name,mode,from,to).search) + '"' + (name === team ? ' aria-current="true"' : '') + '>' + esc(short(name)) + '</a>',
    [s?.count ?? 0, pct(s?.nightlyThree), pct(s?.fixedThree), pct(s?.nightlyFive), pct(s?.fixedShare), dec(s?.others), s ? s.fiveDouble + ' / ' + s.count : '—'],
    name === team ? ' class="sd-selected"' : '')).join('');
  get('result-scope').textContent = results.games + ' league games have both teams in the selected range. Each row counts the games that met its condition.';
  get('results').innerHTML = [['More double-figure scorers than the opponent',results.more],['Five or more in double figures, opponent had fewer than five',results.five]]
    .map(([label,[wins,losses]]) => row(label,[wins,losses,pct(wins + losses ? wins/(wins+losses) : null)])).join('');
  get('players').innerHTML = stats ? stats.players.map((p,i) => row(esc(p.name), [p.gp, p.points, dec(p.points / p.gp), pct(p.points / stats.points), i < 5 ? pct(p.points / stats.fixedPoints) : '—'])).join('') : emptyRow(6,'No player totals for this range.');
  get('games').innerHTML = rows.map(g => row(g.number, [date(g.date), '<a class="sd-link" href="box-score-' + encodeURIComponent(g.id) + '.html">' + esc(short(g.opponent)) + '</a>',
    (g.score > g.against ? 'W ' : 'L ') + g.score + '–' + g.against, ...g.ranks, pct(g.five / g.score), g.doubleFigures])).join('') || emptyRow(11,'No games for this range.');
  get('report').hidden = false;
}
if (teams.length) {
  for (const team of teams) get('team').add(option(short(team), team));
  for (let n=1; n<=maxGames; n++) for (const id of ['from','to']) get(id).add(option(String(n), String(n)));
  get('team').value = teamMatch || (teams.includes('Townsville Fire') ? 'Townsville Fire' : teams[0]);
  get('range').value = modes.includes(params.get('range')) ? params.get('range') : 'all';
  get('from').value = gameNumber(params.get('from'), 1);
  get('to').value = Math.max(Number(get('from').value),gameNumber(params.get('to'),maxGames));
  for (const id of ['team','range','from','to']) get(id).addEventListener('change', () => {
    if (Number(get('from').value) > Number(get('to').value)) {
      if (id === 'to') get('from').value = get('to').value; else get('to').value = get('from').value;
    }
    const {team,mode,from,to} = selections();
    history.replaceState(null,'',selectionUrl(team,mode,from,to));
    render();
  });
  render();
} else {
  get('scope').textContent = 'No completed box scores for this season.';
  get('team').disabled = get('range').disabled = true;
}
