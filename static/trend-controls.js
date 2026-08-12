(() => {
  const playerNode = document.getElementById("profile-data");
  const teamNode = document.getElementById("team-data");
  if (!playerNode && !teamNode) return;

  const data = JSON.parse((playerNode || teamNode).textContent);
  const profile = data.profiles[0];
  const kind = playerNode ? "player" : "team";
  const chart = document.getElementById(kind + "Trend");
  if (!chart) return;

  const metrics = [
    ["minutes_seconds", "Minutes"], ["points", "Points"], ["fg_made", "FGM"],
    ["fg_attempted", "FGA"], ["fg_percentage", "FG%"], ["effective_fg_percentage", "eFG%"],
    ["two_made", "2PM"], ["two_attempted", "2PA"], ["two_percentage", "2P%"],
    ["three_made", "3PM"], ["three_attempted", "3PA"], ["three_percentage", "3P%"],
    ["ft_made", "FTM"], ["ft_attempted", "FTA"], ["ft_percentage", "FT%"],
    ["rebounds", "Rebounds"], ["offensive_rebounds", "Offensive rebounds"],
    ["defensive_rebounds", "Defensive rebounds"], ["assists", "Assists"],
    ["steals", "Steals"], ["turnovers", "Turnovers"], ["blocks", "Blocks"],
    ["fouls", "Personal fouls"], ["total_points_created", "Total points created"]
  ];
  const availableMetrics = kind === "team" ? metrics.filter(([key]) => key !== "minutes_seconds") : metrics;
  let metric = "points", mode = "game";
  const card = chart.closest(".insightCard");
  card.querySelector("h3").textContent = "Stat trend";
  const note = card.querySelector("p");
  const controls = document.createElement("div");
  controls.className = "trendControls";
  controls.innerHTML = `<select aria-label="Trend statistic">${availableMetrics.map(([k,l]) => `<option value="${k}" ${k === "points" ? "selected" : ""}>${l}</option>`).join("")}</select><div class="toggle"><button class="active" data-mode="game">By game</button><button data-mode="season">By season</button></div>`;
  note.after(controls);

  const ratio = (r, made, attempted) => r[attempted] ? (r[made] || 0) / r[attempted] : null;
  function value(r, key, perGame) {
    if (key === "fg_percentage") return ratio(r, "fg_made", "fg_attempted");
    if (key === "effective_fg_percentage") return r.fg_attempted ? ((r.fg_made || 0) + .5 * (r.three_made || 0)) / r.fg_attempted : null;
    if (key === "two_percentage") {
      const attempts = (r.fg_attempted || 0) - (r.three_attempted || 0);
      return attempts ? ((r.fg_made || 0) - (r.three_made || 0)) / attempts : null;
    }
    if (key === "three_percentage") return ratio(r, "three_made", "three_attempted");
    if (key === "ft_percentage") return ratio(r, "ft_made", "ft_attempted");
    let result = r[key] || 0;
    if (key === "two_made") result = (r.fg_made || 0) - (r.three_made || 0);
    if (key === "two_attempted") result = (r.fg_attempted || 0) - (r.three_attempted || 0);
    if (key === "minutes_seconds") result /= 60;
    return perGame ? result / (r.games || 1) : result;
  }
  function render() {
    const selected = document.getElementById(kind === "player" ? "globalSeason" : "seasonSelect")?.value;
    const percentage = metric.endsWith("_percentage");
    const rows = mode === "season"
      ? profile.season_stats
      : profile.game_log.filter(r => r.season === (selected || profile.season_stats.at(-1)?.season)).slice().reverse();
    const points = rows.map((r, i) => {
      const v = value(r, metric, mode === "season");
      return {
        label: mode === "season" ? String(r.season).slice(-2) : String(i + 1),
        value: v,
        display: v == null ? "—" : percentage ? `${(v * 100).toFixed(1)}%` : Number(v).toFixed(1)
      };
    });
    note.textContent = mode === "season"
      ? `${metrics.find(x => x[0] === metric)[1]} per game across recorded seasons.`
      : `${metrics.find(x => x[0] === metric)[1]} in each game of ${selected || profile.season_stats.at(-1)?.season}.`;
    window.WNBLCharts?.line(chart, points);
  }
  controls.querySelector("select").onchange = e => { metric = e.target.value; render(); };
  controls.querySelectorAll("button").forEach(button => button.onclick = () => {
    mode = button.dataset.mode;
    controls.querySelectorAll("button").forEach(x => x.classList.toggle("active", x === button));
    render();
  });
  document.getElementById(kind === "player" ? "globalSeason" : "seasonSelect")?.addEventListener("change", () => {
    if (mode === "game") setTimeout(render);
  });
  document.addEventListener("wnblchartsready", render, {once:true});
  setTimeout(render);
})();
