import { readFile, writeFile, mkdir } from "node:fs/promises";
import { resolve } from "node:path";

const root = resolve(import.meta.dirname, "..");
const profilePath = resolve(root, "app/player-profiles.json");
const photoDir = resolve(root, "static/player-photos");
const data = JSON.parse(await readFile(profilePath, "utf8"));

const clean = value => String(value || "")
  .normalize("NFKD")
  .replace(/[\u0300-\u036f]/g, "")
  .toLowerCase()
  .replace(/[^a-z0-9]+/g, " ")
  .trim();
const compact = value => clean(value).replaceAll(" ", "");
const slug = value => clean(value).replaceAll(" ", "-");

const manualNames = new Map(Object.entries({
  "alexandra sharp": "Alex Sharp",
  "chantel anais horvat": "Chantel-Anais Horvat",
  "caitlin martin": "Caitlyn Martin",
  "isabel borlase": "Isobel Borlase",
  "xu han": "Han Xu",
  "mackenzie clinch hoycard": "Mackenzie Clinch",
  "maddy freer": "Madison Freer",
  "manuela puoch": "Manuala Puoch"
}));
for (const [source, target] of Object.entries(data.aliases || {})) manualNames.set(clean(source), target);

const seasonProfiles = data.profiles.filter(profile => profile.season_stats.some(row => row.season === "2025-26"));
const byName = new Map(seasonProfiles.map(profile => [clean(profile.name), profile]));
const byCompact = new Map(seasonProfiles.map(profile => [compact(profile.name), profile]));

const sitemap = await fetch("https://www.wnbl.com.au/sitemap.xml").then(response => {
  if (!response.ok) throw new Error(`WNBL sitemap returned ${response.status}`);
  return response.text();
});
const urls = [...sitemap.matchAll(/<loc>(https:\/\/www\.wnbl\.com\.au\/player\/[^<]+)<\/loc>/g)].map(match => match[1]);

async function mapLimit(items, limit, worker) {
  const results = new Array(items.length);
  let next = 0;
  async function run() {
    while (next < items.length) {
      const index = next++;
      try { results[index] = await worker(items[index]); }
      catch (error) { results[index] = { url: items[index], error: error.message }; }
    }
  }
  await Promise.all(Array.from({ length: Math.min(limit, items.length) }, run));
  return results;
}

const pages = await mapLimit(urls, 8, async url => {
  const html = await fetch(url).then(response => {
    if (!response.ok) throw new Error(`profile returned ${response.status}`);
    return response.text();
  });
  const name = html.match(/<h1 class="white-text">([^<]+)<\/h1>/)?.[1]
    ?.replaceAll("&amp;", "&").replaceAll("&#x27;", "'").trim();
  const photo = html.match(/<img src="([^"]+)"[^>]*class="player large-player"/)?.[1]?.replaceAll("&amp;", "&");
  return { url, name, photo };
});

function matchedProfile(name) {
  if (!name) return null;
  const corrected = manualNames.get(clean(name));
  if (corrected && byName.has(clean(corrected))) return byName.get(clean(corrected));
  if (byName.has(clean(name))) return byName.get(clean(name));
  if (byCompact.has(compact(name))) return byCompact.get(compact(name));
  const parts = clean(name).split(" "), surname = parts.at(-1), first = parts[0];
  const candidates = seasonProfiles.filter(profile => {
    const p = clean(profile.name).split(" ");
    return p.at(-1) === surname && (p[0].startsWith(first) || first.startsWith(p[0]));
  });
  return candidates.length === 1 ? candidates[0] : null;
}

await mkdir(photoDir, { recursive: true });
const matched = [], unavailable = [], failed = [];
for (const page of pages) {
  if (page.error) { failed.push(page); continue; }
  const profile = matchedProfile(page.name);
  if (!profile || !page.photo) continue;
  const response = await fetch(page.photo);
  if (!response.ok) { failed.push({ ...page, error: `image returned ${response.status}` }); continue; }
  const type = response.headers.get("content-type") || "";
  const extension = type.includes("png") ? "png" : type.includes("jpeg") ? "jpg" : "webp";
  const filename = `${slug(profile.name)}.${extension}`;
  await writeFile(resolve(photoDir, filename), Buffer.from(await response.arrayBuffer()));
  profile.photo = `player-photos/${filename}`;
  profile.source = page.url;
  profile.bio_status = "Official WNBL profile matched";
  matched.push({ player: profile.name, page_name: page.name, file: filename, source: page.url });
}

const matchedNames = new Set(matched.map(row => row.player));
for (const profile of seasonProfiles) if (!matchedNames.has(profile.name)) unavailable.push(profile.name);

await writeFile(profilePath, JSON.stringify(data, null, 2) + "\n");
await writeFile(resolve(root, "app/wnbl-player-photo-audit.json"), JSON.stringify({
  generated_at: new Date().toISOString(), season: "2025-26", official_pages_checked: urls.length,
  matched_count: matched.length, unavailable_count: unavailable.length, matched, unavailable, failed
}, null, 2) + "\n");

console.log(JSON.stringify({ official_pages: urls.length, matched: matched.length, unavailable: unavailable.length, failed: failed.length }, null, 2));
