const $ = id => document.getElementById(id);
const escape = value => String(value ?? '').replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
const fixed = value => Number.isFinite(value) ? value.toFixed(1) : '—';
const rate = (n, d, scale = 100) => n != null && d > 0 ? scale * n / d : null;
const percent = value => Number.isFinite(value) ? fixed(value) + '%' : '—';
const difference = (a, b) => a == null || b == null ? null : a - b;
const periodName = p => p <= 4 ? 'Q' + p : 'OT' + (p - 4);
const dateName = d => new Date(d + 'T12:00:00Z').toLocaleDateString('en-AU', {day:'numeric',month:'short',year:'numeric',timeZone:'UTC'});
const views = ['shots','coverage','impact'];
const params = new URLSearchParams(location.search);
const state = Object.fromEntries(params);
const shotCache = new Map();
let data, efficiencyRequest, revision = 0;

function options(id, label, items, value) {
  return `<label>${label}<select id="${id}">${items.map(([k,v]) => `<option value="${escape(k)}"${String(k) === String(value) ? ' selected' : ''}>${escape(v)}</option>`).join('')}</select></label>`;
}
function table(headers, rows) {
  return `<div class="table-wrap"><table><thead><tr>${headers.map(h=>`<th scope="col">${h}</th>`).join('')}</tr></thead><tbody>${rows.join('')}</tbody></table></div>`;
}
const row = cells => `<tr>${cells.map(c=>`<td>${c}</td>`).join('')}</tr>`;
const empty = message => `<p class="empty" role="status">${escape(message)}</p>`;
const teamGames = () => data.games.filter(g=>g.season === state.season && [g.home,g.away].includes(state.team));
const matchup = g => `${dateName(g.date)} · ${data.teams[g.away]} at ${data.teams[g.home]}`;
function scopeNote(scope) {
  const ids = new Set(scope.games);
  const games = teamGames().filter(g=>ids.has(g.id)).sort((a,b)=>a.date.localeCompare(b.date));
  return `<p class="scope-note">${games.length} games · ${dateName(games[0].date)} – ${dateName(games.at(-1).date)}. Fixed InStat sample.</p>
    <details class="scope-list"><summary>Games in this sample</summary><ul>${games.map(g=>`<li>${g.box ? `<a href="box-score-${escape(g.box)}.html">${escape(matchup(g))}</a>` : escape(matchup(g))}</li>`).join('')}</ul></details>`;
}
async function readJson(name) {
  const response = await fetch(`scouting-data/${name}.json`);
  if (!response.ok) throw new Error('Data could not load');
  return response.json();
}

function court(shots) {
  const marks = shots.map((s,i)=>{
    const x = s.x, y = s.y;
    return `<g data-shot="${i}" transform="translate(${x} ${y})"><title>${escape(s.description)}</title>${s.made
      ? '<circle r="1.25" fill="#156654" opacity=".76"/>'
      : '<path d="M-1 -1 L1 1 M-1 1 L1 -1" fill="none" stroke="#ae3f1c" stroke-width=".58" opacity=".83"/>'}<circle r="1.5" fill="transparent"/></g>`;
  }).join('');
  return `<svg class="scout-court" viewBox="-2 -2 154 144" role="img" aria-label="Half-court shot map showing ${shots.length} attempts">
    <rect width="150" height="140" fill="#f4e8d4"/><rect x="50.5" width="49" height="58" fill="#e7d8bc"/>
    <g fill="none" stroke="#9a907d" stroke-width=".65"><path d="M0 0H150V140H0Z M50.5 0V58H99.5V0 M9 0V29.9 A67.5 67.5 0 0 0 141 29.9 V0 M57 12H93 M57 58 A18 18 0 0 0 93 58 M57 140 A18 18 0 0 1 93 140"/><circle cx="75" cy="15.75" r="2.25"/></g>${marks}</svg>`;
}

async function renderShots(version) {
  const schedule = teamGames().sort((a,b)=>a.date.localeCompare(b.date));
  if (!schedule.length) return '<h2>Shot maps</h2>' + empty('No official shot sample for this team and season.');
  const seasonKey = state.season;
  if (!shotCache.has(seasonKey)) shotCache.set(seasonKey, readJson(seasonKey).catch(e=>{shotCache.delete(seasonKey);throw e;}));
  const records = await shotCache.get(seasonKey);
  if (revision !== version) return '';
  const byId = new Map(records.map(g=>[g.id,g]));
  const game = schedule.find(g=>g.id===state.game || (g.box && g.box===state.game));
  if (state.game && !game) return '<h2>Shot maps</h2>' + empty('This game has no matching official shot record for the selected team and season.') + '<button type="button" id="all-games">See all games</button>';
  const selected = game ? [game] : schedule;
  const available = selected.filter(g=>g.verified && byId.has(g.id));
  const periods = Math.max(...selected.map(g=>g.periods));
  const side = state.side === 'defence' ? 'defence' : 'offence';
  const attempts = [];
  for (const g of available) {
    const record = byId.get(g.id);
    for (const [away, player, period, clock, rawX, rawY, made, value, zone] of record.shots) {
      const shooter = away ? g.away : g.home;
      if ((shooter===state.team) !== (side==='offence')) continue;
      const name = record.players[player];
      const description = `${name} · ${dateName(g.date)} · ${periodName(period)} ${clock} · ${made?'Made':'Missed'} ${value}pt`;
      attempts.push({name,period,made,value,zone,description,x:rawY*1.5,y:Math.min(rawX,100-rawX)*2.8});
    }
  }
  const names = Array.from(new Set(attempts.map(s=>s.name))).sort();
  if (state.player && !names.includes(state.player)) names.push(state.player);
  const shots = attempts.filter(s=>(!state.player || s.name===state.player) && (!state.period || s.period===Number(state.period)));
  const controls = options('side','Shots', [['offence','Team offence'],['defence','Opponent offence']],side) +
    options('game','Game',[['','All games'],...schedule.map(g=>[g.box || g.id,matchup(g)])],game?.box || game?.id || '') +
    options('player','Shooter',[['','All shooters'],...names.map(n=>[n,n])],state.player || '') +
    options('period','Period',[['','All periods'],...Array.from({length:periods},(_,i)=>[i+1,periodName(i+1)])],state.period || '');
  const omitted = selected.length - available.length;
  const note = `<p class="scope-note">${available.length} of ${selected.length} selected games have verified shot locations.${omitted ? ' Games that did not reconcile to the official box score are excluded.' : ''}</p>`;
  let result = `<h2>Shot maps</h2><div class="filters">${controls}</div>${note}`;
  if (!available.length) return result + empty('Shot locations are unavailable for this selection.');
  if (!shots.length) return result + empty('No recorded attempts match these filters.');
  const makes = shots.filter(s=>s.made).length;
  const zones = [['paint','Paint'],['mid','Mid-range'],['three','Three-point']];
  const zoneRows = zones.map(([key,label])=>{
    const list = shots.filter(s=>s.zone===key), hit = list.filter(s=>s.made).length;
    const points = list.reduce((n,s)=>n+s.value*s.made,0);
    return row([label,hit+' / '+list.length,percent(rate(list.length,shots.length)),percent(rate(hit,list.length)),list.length ? (points/list.length).toFixed(2) : '—']);
  });
  result += `<div class="shot-layout"><section class="figure-panel"><div class="legend"><b>● Made</b><b>× Missed</b></div>${court(shots)}<p class="shot-readout" id="shot-readout">Select a shot for the player, clock and result.</p></section>
    <section class="stats-panel"><h3>Shot distribution</h3><p class="metric">${makes} / ${shots.length}</p><p>Field goals made / attempted · ${percent(rate(makes,shots.length))}</p>${table(['Zone','Made / att.','Share','FG%','Pts / shot'],zoneRows)}
    <p class="scope-note">Both baskets are shown at one end. Paint is the rectangular key. Points per shot counts field goals.</p></section></div>`;
  return result;
}

const coverageOrder = ['Over','Under','Switch','Double (trap)','Hedge','ICE / Drop'];

function efficiencyPanel(label, groups) {
  const byCoverage = new Map();
  let possessions = 0, points = 0, turnovers = 0;
  for (const group of groups) {
    for (const [name, stats] of Object.entries(group)) {
      const totals = byCoverage.get(name) || {possessions:0, points:0, turnovers:0};
      totals.possessions += stats.possessions;
      totals.points += stats.points;
      totals.turnovers += stats.turnovers;
      byCoverage.set(name, totals);
      possessions += stats.possessions;
      points += stats.points;
      turnovers += stats.turnovers;
    }
  }
  const other = [...byCoverage.keys()].filter(name => !coverageOrder.includes(name) && name!=='Untagged').sort();
  const names = [...coverageOrder, ...other];
  if (byCoverage.has('Untagged')) names.push('Untagged');
  const cells = (name, n, pts, lost) => [
    escape(name), n ? '<strong>' + (pts / n).toFixed(2) + '</strong>' : '—', n, n ? pts : '—', n ? lost : '—'
  ];
  const rows = names.map(name => {
    const stats = byCoverage.get(name);
    return row(cells(name, stats?.possessions ?? 0, stats?.points ?? 0, stats?.turnovers ?? 0));
  });
  const total = cells('All PnR', possessions, points, turnovers);
  rows.push(`<tr class="chosen"><th scope="row">${total[0]}</th>${total.slice(1).map(v => `<td>${v}</td>`).join('')}</tr>`);
  return `<section class="stats-panel"><h3>${escape(label)}</h3>${table(['Coverage','PPP','Poss','Pts','<abbr title="Turnovers">TO</abbr>'],rows)}</section>`;
}

function coverageEfficiency(records) {
  const reviewed = teamGames().filter(g => Object.hasOwn(records, g.id)).sort((a,b) => a.date.localeCompare(b.date));
  const tagged = reviewed.filter(g => records[g.id] != null);
  if (!reviewed.length) return empty('No possession outcomes have been published for this team and season.');
  const list = reviewed.map(g => `<li><a href="box-score-${escape(g.box)}.html">${escape(matchup(g))}</a> · ${records[g.id] ? 'Included' : 'No play-type tags'}</li>`).join('');
  const sample = `<p class="scope-note">${tagged.length} of ${reviewed.length} reviewed Hudl ${reviewed.length===1?'game':'games'} with ball-screen tags · ${dateName(reviewed[0].date)} – ${dateName(reviewed.at(-1).date)}.</p>
    <details class="scope-list"><summary>Games reviewed for efficiency</summary><ul>${list}</ul></details>`;
  if (!tagged.length) return sample + empty('These games have no tagged ball-screen possessions.');
  const name = data.teams[state.team];
  const offence = tagged.map(g => records[g.id][state.team]);
  const defence = tagged.map(g => records[g.id][g.home===state.team ? g.away : g.home]);
  const untagged = [...offence, ...defence].flatMap(group => group.Untagged ?? []);
  const untaggedCount = untagged.reduce((sum, stats) => sum + stats.possessions, 0);
  const untaggedTurnovers = untagged.reduce((sum, stats) => sum + stats.turnovers, 0);
  const missing = untaggedCount ? ` Across both sides of the ball, ${untaggedTurnovers} of ${untaggedCount} untagged possessions ended in turnovers. These count towards All PnR.` : '';
  return sample + '<p>PPP is points per possession. Each tagged ball-screen possession counts once, including linked free throws and points after offensive rebounds.</p>' +
    '<div class="details-grid">' + efficiencyPanel(name + ' scoring against coverage', offence) +
    efficiencyPanel(name + ' points allowed by coverage', defence) + '</div>' +
    '<p class="scope-note">Over and Under describe the on-ball defender’s route. ICE / Drop has both tags. Possessions with different coverages appear under Multiple coverages. Untagged means a ball screen was recorded without a coverage call.' + missing + '</p>';
}

async function renderCoverage() {
  const scope = data.coverage[state.season]?.[state.team];
  function coverageTable(label, group) {
    const rows = Object.entries(group.counts).map(([name,count])=>{
      const share = rate(count,group.total);
      return row([escape(name),count ?? '—',`<span class="coverage-bar"><i style="width:${share ?? 0}%"></i></span>${percent(share)}`]);
    });
    return `<section class="stats-panel"><h3>${label}</h3><p>${group.total} tagged clips</p>${table(['Coverage','Clips','Share'],rows)}</section>`;
  }
  const frequency = scope ? scopeNote(scope) + '<div class="details-grid">' +
    coverageTable('Faced on offence',scope.offence) + coverageTable('Used on defence',scope.defence) +
    '</div><p class="scope-note">Share is the percentage of InStat clips on that side of the ball. The clip snapshot has its own game sample.</p>' :
    empty('No pick-and-roll clip counts have been published for this team and season.');
  let efficiency;
  try {
    efficiencyRequest ??= readJson('pnr-efficiency').catch(error => { efficiencyRequest = null; throw error; });
    efficiency = coverageEfficiency(await efficiencyRequest);
  } catch {
    efficiency = empty('Possession outcomes could not load.') + '<button type="button" id="retry">Try again</button>';
  }
  return '<h2>Pick-and-roll efficiency</h2>' + efficiency + '<h2>Coverage frequency</h2>' + frequency;
}

function ratings(split) {
  const off = rate(split.points,split.possessions);
  const def = rate(split.allowed,split.opponent_possessions);
  return {off,def,net:difference(off,def)};
}
function detailRows(on, off, side) {
  const measures = [
    ['FG made / attempted',s=>pair(s.fgm,s.fga)],['3PT made / attempted',s=>pair(s.tpm,s.tpa)],
    ['FT made / attempted',s=>pair(s.ftm,s.fta)],['Effective FG%',s=>percent(rate(s.fgm==null || s.tpm==null ? null : s.fgm+.5*s.tpm,s.fga))],
    ['Free-throw rate',s=>percent(rate(s.fta,s.fga))],['Offensive rebounds',s=>s.oreb],['Defensive rebounds',s=>s.dreb],
    ['Assists',s=>s.ast],['Steals',s=>s.stl],['Turnovers',s=>s.tov],['Fouls',s=>s.foul]
  ];
  function pair(m,a){return m==null || a==null ? '—' : m+' / '+a;}
  const rows = measures.map(([label,fn])=>row([label,fn(on[side]) ?? '—',fn(off[side]) ?? '—']));
  const denom = side==='team' ? 'possessions' : 'opponent_possessions';
  rows.push(row(['Turnover rate',percent(rate(on[side].tov,on[denom])),percent(rate(off[side].tov,off[denom]))]));
  const other = side==='team' ? 'opponent' : 'team';
  for (const [label,won,lost] of [['Offensive rebound %','oreb','dreb'],['Defensive rebound %','dreb','oreb']]) {
    const reboundShare = s => {
      const a=s[side][won], b=s[other][lost];
      return a==null || b==null ? '—' : percent(rate(a,a+b));
    };
    rows.push(row([label,reboundShare(on),reboundShare(off)]));
  }
  return table(['Statistic','On court','Off court'],rows);
}
function renderImpact() {
  const scope = data.impact[state.season]?.[state.team];
  if (!scope) return '<h2>Player on/off</h2>' + empty('No possession-based lineup sample has been published for this team and season.');
  const players = Object.entries(scope.players).sort((a,b)=>b[1].on.seconds-a[1].on.seconds);
  const chosen = state.player || players[0][0];
  const names = players.map(([n])=>[n,n]);
  if (!scope.players[chosen]) names.push([chosen,chosen]);
  const header = '<h2>Player on/off</h2>' + scopeNote(scope) + '<div class="filters">' + options('player','Player',names,chosen) + '</div>';
  const rows = players.map(([n,p])=>{
    const a=ratings(p.on), b=ratings(p.off);
    return `<tr class="${n===chosen?'chosen':''}"><td><button type="button" data-player="${escape(n)}">${escape(n)}</button></td>${[p.on.seconds/60,p.off.seconds/60,a.off,a.def,a.net,b.off,b.def,b.net,difference(a.net,b.net)].map(v=>`<td>${fixed(v)}</td>`).join('')}</tr>`;
  });
  const overview = `<section class="stats-panel"><h3>Team efficiency by player</h3>${table(['Player','On min','Off min','On ORtg','On DRtg','On net','Off ORtg','Off DRtg','Off net','Net on − off'],rows)}</section>`;
  const p = scope.players[chosen];
  if (!p) return header + empty('This player has no recorded lineup minutes in this sample.') + overview;
  const denomNote = `<p class="scope-note">On court: ${p.on.possessions} offensive and ${p.on.opponent_possessions} defensive possessions. Off court: ${p.off.possessions} offensive and ${p.off.opponent_possessions} defensive possessions.</p>`;
  return header + overview + `<h3>${escape(chosen)} · on and off court</h3>${denomNote}
    <div class="details-grid"><section class="stats-panel"><h3>Team totals</h3>${detailRows(p.on,p.off,'team')}</section><section class="stats-panel"><h3>Opponent totals</h3>${detailRows(p.on,p.off,'opponent')}</section></div>
    <p class="scope-note">Ratings are points per 100 listed offensive or defensive possessions. Net on − off compares team net ratings. Totals cover the five-player units in this sample. ${scope.unallocatedSeconds} seconds of unallocated game time are excluded. Teammates and opponents affect these numbers.</p>`;
}

function syncUrl() {
  const query = new URLSearchParams();
  for (const key of ['view','season','team','game','side','player','period']) if (state[key]) query.set(key,state[key]);
  history.replaceState(null,'','?'+query);
}
async function render() {
  const version = ++revision;
  $('analysis').setAttribute('aria-busy','true');
  const seasons = [...new Set(data.games.map(g=>g.season))].sort().reverse();
  const teams = Object.entries(data.teams).sort((a,b)=>a[1].localeCompare(b[1]));
  $('scope').innerHTML = options('season','Season',seasons.map(s=>[s,s]),state.season) + options('team','Team',teams,state.team);
  for (const a of $('views').querySelectorAll('a')) {
    if (a.dataset.view===state.view) a.setAttribute('aria-current','page'); else a.removeAttribute('aria-current');
    const q = new URLSearchParams({view:a.dataset.view,season:state.season,team:state.team});
    if (state.player && state.side!=='defence' && a.dataset.view!=='coverage') q.set('player',state.player);
    a.href = '?'+q;
  }
  syncUrl();
  try {
    const content = state.view==='shots' ? await renderShots(version) : state.view==='coverage' ? await renderCoverage() : renderImpact();
    if (revision===version) $('analysis').innerHTML = content;
  } catch {
    if (revision===version) $('analysis').innerHTML = empty('The scouting data could not load.') + '<button id="retry">Try again</button>';
  } finally { if (revision===version) $('analysis').setAttribute('aria-busy','false'); }
}
function change(key,value) {
  if (key==='season') { delete state.game; delete state.player; delete state.period; }
  if (key==='team') {
    const selected = data.games.find(g=>g.box===state.game || g.id===state.game);
    if (!selected || ![selected.home,selected.away].includes(value)) {delete state.game; delete state.period;}
    delete state.player;
  }
  if (key==='side') delete state.player;
  if (key==='game') {delete state.period;}
  state[key]=value;
  render();
}
document.querySelector('.scout-main').addEventListener('change',event=>{
  if (event.target.matches('select')) change(event.target.id,event.target.value);
});
function showShot(target) {
  const mark=target.closest('[data-shot]');
  if (mark && $('shot-readout')) $('shot-readout').textContent=mark.querySelector('title').textContent;
}
$('analysis').addEventListener('pointerover',event=>showShot(event.target));
$('analysis').addEventListener('click',event=>{
  showShot(event.target);
  const button = event.target.closest('button');
  if (button?.dataset.player) change('player',button.dataset.player);
  if (button?.id==='all-games') change('game','');
  if (button?.id==='retry') render();
});
try {
  data=await readJson('index');
  const seasons=[...new Set(data.games.map(g=>g.season))].sort().reverse();
  state.view=views.includes(state.view) ? state.view : 'shots';
  state.season=state.season || seasons[0];
  const aliases = {'southside flyers':'SMF','canberra':'UCC','university of canberra capitals':'UCC'};
  const requested = (state.team || '').toLowerCase();
  const desired=Object.entries(data.teams).find(([code,name])=>code===aliases[requested] || code.toLowerCase()===requested || (requested && name.toLowerCase().startsWith(requested)));
  state.team=desired?.[0] || 'TSV';
  await render();
} catch {
  $('analysis').setAttribute('aria-busy','false');
  $('analysis').innerHTML=empty('The scouting data could not load. Reload the page to try again.');
}
