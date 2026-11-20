import {metrics, metricValue, formatValue, readSelection, selectionParams} from './comparison-core.js';

const $ = id => document.getElementById(id);
const esc = value => String(value ?? '').replace(/[&<>"']/g, char => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[char]));
const letters = ['A', 'B', 'C', 'D'];
let data, state;
const selectedRows = () => state.picks.map(pick => data[state.mode].find(row => row.slug === pick.slug && row.season === pick.season));
const visibleMetrics = () => metrics.filter(metric => (!metric.kinds || metric.kinds.includes(state.mode)) && (state.group === 'all' || metric.group === state.group));
const entityLabel = () => state.mode === 'players' ? 'Player' : 'Team';
const setStatus = message => { $('comparisonStatus').textContent = message; };

function updateURL() {
  const next = new URL(location.href);
  next.search = selectionParams(state).toString();
  history.replaceState(null, '', next);
}

function entityOptions(index, search = '') {
  const pick = state.picks[index];
  const candidates = data[state.mode].filter(row => row.season === pick.season);
  const matches = candidates.filter(row => row.slug === pick.slug || `${row.name} ${row.team || ''}`.toLowerCase().includes(search.trim().toLowerCase()))
    .sort((a, b) => a.name.localeCompare(b.name));
  const select = $('entity-' + index);
  select.innerHTML = `<option value="">Choose ${entityLabel().toLowerCase()}…</option>` + matches.map(row =>
    `<option value="${esc(row.slug)}" ${row.slug === pick.slug ? 'selected' : ''}>${esc(row.name)}${row.team ? ' · ' + esc(row.team) : ''}</option>`).join('');
  if (!matches.length) select.innerHTML = '<option value="">No matches in this season</option>';
}

function renderSlots() {
  $('comparisonSlots').innerHTML = state.picks.map((pick, index) => {
    const seasonOptions = [...data.meta.seasons].reverse().map(season => `<option value="${esc(season)}" ${pick.season === season ? 'selected' : ''}>${esc(season)}</option>`).join('');
    return `<article class="comparisonSlot" data-slot="${index}">
      <div class="comparisonSlotHead"><h2>Selection ${letters[index]}</h2><button type="button" data-remove="${index}" aria-label="Remove selection ${letters[index]}" ${state.picks.length <= 2 ? 'disabled' : ''}>Remove</button></div>
      <label for="season-${index}">Season ${letters[index]}<select id="season-${index}" data-season="${index}"><option value="">Choose season…</option>${seasonOptions}</select></label>
      ${state.mode === 'seasons' ? '<small>League-wide statistics across all teams.</small>' : `
        <label for="search-${index}">Find ${entityLabel().toLowerCase()} ${letters[index]}<input type="search" id="search-${index}" data-search="${index}" placeholder="Search by name" autocomplete="off"></label>
        <label for="entity-${index}">${entityLabel()} ${letters[index]}<select id="entity-${index}" data-entity="${index}"></select></label>`}
      <small id="selection-note-${index}"></small>
    </article>`;
  }).join('');
  if (state.mode !== 'seasons') state.picks.forEach((_, index) => entityOptions(index));
  $('comparisonSlots').querySelectorAll('[data-season]').forEach(select => select.addEventListener('change', () => {
    const index = Number(select.dataset.season), pick = state.picks[index];
    pick.season = select.value;
    if (state.mode === 'seasons') pick.slug = pick.season;
    else {
      if (!data[state.mode].some(row => row.slug === pick.slug && row.season === pick.season)) pick.slug = '';
      $('search-' + index).value = '';
      entityOptions(index);
    }
    changed();
  }));
  $('comparisonSlots').querySelectorAll('[data-entity]').forEach(select => select.addEventListener('change', () => {
    state.picks[Number(select.dataset.entity)].slug = select.value;
    changed();
  }));
  $('comparisonSlots').querySelectorAll('[data-search]').forEach(input => input.addEventListener('input', () => entityOptions(Number(input.dataset.search), input.value)));
  $('comparisonSlots').querySelectorAll('[data-remove]').forEach(button => button.addEventListener('click', () => {
    const index = Number(button.dataset.remove);
    state.picks.splice(index, 1);
    renderSlots();
    changed();
    $('season-' + Math.min(index, state.picks.length - 1)).focus();
  }));
  $('addComparison').disabled = state.picks.length >= 4;
}

function renderResults() {
  const rows = selectedRows(), ready = rows.filter(Boolean);
  document.querySelectorAll('[data-mode]').forEach(link => {
    if (link.dataset.mode === state.mode) link.setAttribute('aria-current', 'page');
    else link.removeAttribute('aria-current');
  });
  $('comparisonBasis').value = state.basis;
  $('comparisonGroup').value = state.group;
  $('comparisonHelp').textContent = state.mode === 'seasons'
    ? 'Compare up to four league seasons. Per-game figures represent one team per game.'
    : `Compare up to four ${state.mode}. Choose the same ${entityLabel().toLowerCase()} in different seasons to track change.`;
  $('comparisonContext').textContent = state.basis === 'game'
    ? `Counting statistics are per ${state.mode === 'seasons' ? 'team per ' : ''}game. Games${state.mode === 'teams' ? ', wins and losses' : ''} remain totals. Rates and percentages use the full selected season.`
    : `${state.mode === 'seasons' ? 'League totals include both teams in every game.' : 'Counting statistics are season totals.'} Rates and percentages use the full selected season.`;
  const current = ready.some(row => row.season === data.meta.current_season) && !data.meta.current_season_complete;
  $('comparisonCoverage').textContent = current ? `${data.meta.current_season} is in progress. Dataset through ${data.meta.latest_game_date}. Compare games played before interpreting totals.` : '';
  state.picks.forEach((pick, index) => {
    const row = rows[index];
    $('selection-note-' + index).textContent = row
      ? `${metricValue(row, 'games')} ${metricValue(row, 'games') === 1 ? 'game' : 'games'}${row.team ? ' · ' + row.team : ''}`
      : pick.slug ? 'This selection is unavailable. Choose another entry.' : 'Choose an entry to include it.';
  });
  $('exportComparison').disabled = ready.length < 2;
  if (ready.length < 2) {
    $('comparisonResults').innerHTML = '<p class="comparisonEmpty">Choose at least two entries to see their statistics side by side.</p>';
    return;
  }
  const shown = rows.map((row, index) => ({row, letter: letters[index]})).filter(item => item.row);
  const duplicate = new Set(ready.map(row => row.slug + '|' + row.season)).size < ready.length;
  const delta = shown.length === 2;
  $('comparisonResults').innerHTML = `${duplicate ? '<p>The same entry is selected more than once. Choose a different season or name to compare changes.</p>' : ''}
    <div class="comparisonTableWrap" role="region" aria-label="Comparison statistics" tabindex="0"><table class="comparisonTable" data-comparison-table data-enhanced="1">
      <caption class="sr-only">${esc(state.mode)} comparison, ${state.basis === 'game' ? 'per game' : 'totals'}</caption>
      <thead><tr><th scope="col">Statistic</th>${shown.map(({row, letter}) => `<th scope="col">${letter} · ${state.mode === 'seasons' ? esc(row.name) : `<a href="${state.mode === 'players' ? 'player' : 'team'}-${esc(row.slug)}.html">${esc(row.name)}</a>`}<small>${esc(row.season)}${row.team ? ' · ' + esc(row.team) : ''}</small></th>`).join('')}${delta ? `<th scope="col">Difference<small>${shown[1].letter} minus ${shown[0].letter}</small></th>` : ''}</tr></thead>
      <tbody>${visibleMetrics().map(metric => {
        const values = shown.map(({row}) => metricValue(row, metric.key, state.basis));
        const valid = values.filter(Number.isFinite);
        const best = metric.direction && valid.length >= 2 ? (metric.direction === 'low' ? Math.min(...valid) : Math.max(...valid)) : null;
        return `<tr><th scope="row">${esc(metric.label)}</th>${values.map(value => {
          const leading = best !== null && Number.isFinite(value) && Math.abs(value - best) < 1e-9;
          return `<td class="${leading ? 'comparisonLeader' : ''}">${leading ? '<span aria-label="Leading value">◆</span>' : ''}${formatValue(value, metric, state.basis)}</td>`;
        }).join('')}${delta ? `<td class="comparisonDelta">${formatValue(values.every(Number.isFinite) ? values[1] - values[0] : null, metric, state.basis, true)}</td>` : ''}</tr>`;
      }).join('')}</tbody></table></div>`;
}

function changed() {
  setStatus('');
  updateURL();
  renderResults();
}

function reset(mode = state.mode) {
  state = readSelection(data, new URLSearchParams({mode}));
  renderSlots();
  changed();
}

async function start() {
  try {
    const response = await fetch('comparison-data.json');
    if (!response.ok) throw new Error('Comparison data unavailable');
    data = await response.json();
    state = readSelection(data, new URLSearchParams(location.search));
    renderSlots();
    renderResults();
    $('comparisonWorkspace').hidden = false;
    setStatus(state.invalid ? 'Some linked selections are no longer available. Choose replacements below.' : '');
  } catch {
    setStatus('Comparison data could not be loaded.');
    const retry = document.createElement('button');
    retry.type = 'button';
    retry.textContent = 'Try again';
    retry.onclick = () => { retry.remove(); setStatus('Loading comparison data…'); start(); };
    $('comparisonStatus').append(' ', retry);
  }
}

document.querySelectorAll('[data-mode]').forEach(link => link.addEventListener('click', event => {
  if (!data || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
  event.preventDefault();
  reset(link.dataset.mode);
}));
$('addComparison').onclick = () => {
  if (state.picks.length >= 4) return;
  state.picks.push({slug: '', season: state.mode === 'seasons' ? '' : state.picks[0]?.season || data.meta.seasons.at(-1)});
  renderSlots();
  changed();
  $('season-' + (state.picks.length - 1)).focus();
};
$('resetComparison').onclick = () => reset();
$('comparisonBasis').onchange = event => { state.basis = event.target.value; changed(); };
$('comparisonGroup').onchange = event => { state.group = event.target.value; changed(); };
$('copyComparison').onclick = async () => {
  updateURL();
  try { await navigator.clipboard.writeText(location.href); setStatus('Comparison link copied.'); }
  catch {
    setStatus('Copy this comparison link: ');
    const input = document.createElement('input');
    input.readOnly = true;
    input.value = location.href;
    input.setAttribute('aria-label', 'Comparison link');
    $('comparisonStatus').append(input);
    input.select();
  }
};
$('exportComparison').onclick = () => {
  const rows = selectedRows().map((row, index) => ({row, letter: letters[index]})).filter(item => item.row);
  const delta = rows.length === 2;
  const lines = [
    ['WNBL comparison', state.mode, state.basis === 'game' ? state.mode === 'seasons' ? 'Per team per game' : 'Per game' : 'Totals'],
    ['Dataset through', data.meta.latest_game_date],
    ['Statistic', ...rows.map(({row, letter}) => `${letter}: ${row.name} · ${row.season}${row.team ? ' · ' + row.team : ''}`), ...(delta ? [`Difference (${rows[1].letter} minus ${rows[0].letter})`] : [])],
    ...visibleMetrics().map(metric => {
      const values = rows.map(({row}) => metricValue(row, metric.key, state.basis));
      return [metric.label, ...values.map(value => formatValue(value, metric, state.basis)), ...(delta ? [formatValue(values.every(Number.isFinite) ? values[1] - values[0] : null, metric, state.basis, true)] : [])];
    })
  ];
  const csv = '\uFEFF' + lines.map(line => line.map(cell => '"' + String(cell).replaceAll('"', '""') + '"').join(',')).join('\r\n');
  const url = URL.createObjectURL(new Blob([csv], {type: 'text/csv;charset=utf-8'}));
  const link = document.createElement('a');
  link.href = url;
  link.download = `wnbl-${state.mode}-comparison.csv`;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
  setStatus('Comparison exported.');
};
window.addEventListener('popstate', () => {
  if (!data) return;
  state = readSelection(data, new URLSearchParams(location.search));
  renderSlots(); renderResults();
});
start();
