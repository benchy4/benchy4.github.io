(() => {
  const aliases = {
    "Adelaide": "Adelaide Lightning",
    "Bendigo": "Bendigo Spirit",
    "UC Capitals": "University of Canberra Capitals",
    "Canberra": "University of Canberra Capitals",
    "Geelong": "Geelong Venom",
    "Perth": "Perth Lynx",
    "Southside Flyers": "Southside Melbourne Flyers",
    "Southside": "Southside Melbourne Flyers",
    "Sydney": "Sydney Flames",
    "Townsville": "Townsville Fire",
    "Miela Goodchild": "Miela Sowah",
    "Xu Han": "Han Xu"
  };
  const index = globalThis.WNBL_SITE_INDEX || [];
  const hrefs = new Map(index.filter(x => x.type === "Player" || x.type === "Team").map(x => [x.title, x.href]));
  for (const [alias, canonical] of Object.entries(aliases)) if (hrefs.has(canonical)) hrefs.set(alias, hrefs.get(canonical));
  const eligible = /player|team|opponent|home|away|assister|scorer|creator|shooter|defender/i;
  const excluded = "a,script,style,noscript,option,select,button,input,textarea";
  const escapePattern = value => value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const names = [...hrefs.keys()].sort((a,b) => b.length-a.length);
  const namePattern = new RegExp(`(^|[^\\p{L}\\p{N}])(${names.map(escapePattern).join("|")})(?=$|[^\\p{L}\\p{N}])`, "gu");
  let working = false;
  function linkCell(cell) {
    if (cell.querySelector("a")) return;
    const value = cell.textContent.trim().replace(/\s*↗$/, "");
    const href = hrefs.get(value);
    if (!href) return;
    const a = document.createElement("a");
    a.href = href; a.textContent = value + " ↗"; a.className = "profileReference";
    cell.textContent = ""; cell.appendChild(a);
  }
  function linkTextNode(node) {
    if (!node.nodeValue?.trim() || node.parentElement?.closest(excluded)) return;
    const text = node.nodeValue;
    namePattern.lastIndex = 0;
    let match, cursor = 0, changed = false;
    const fragment = document.createDocumentFragment();
    while ((match = namePattern.exec(text))) {
      const prefixLength = match[1].length, name = match[2], start = match.index + prefixLength;
      if (start > cursor) fragment.append(text.slice(cursor,start));
      const a = document.createElement("a");
      a.href = hrefs.get(name); a.textContent = name; a.className = "profileReference";
      fragment.append(a); cursor = start + name.length; changed = true;
    }
    if (!changed) return;
    if (cursor < text.length) fragment.append(text.slice(cursor));
    node.replaceWith(fragment);
  }
  function linkVisibleText() {
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    const nodes = [];
    while (walker.nextNode()) nodes.push(walker.currentNode);
    nodes.forEach(linkTextNode);
  }
  function apply() {
    if (working) return;
    working = true;
    document.querySelectorAll("table").forEach(table => {
      const headers = [...table.querySelectorAll("thead th")].map(x => x.textContent.trim());
      table.querySelectorAll("tbody tr").forEach(row => [...row.cells].forEach((cell, i) => {
        if (eligible.test(headers[i] || "")) linkCell(cell);
      }));
    });
    document.querySelectorAll(".club h1,.sectionTitle h2,.teamCard b").forEach(linkCell);
    document.querySelectorAll("svg text").forEach(node => {
      if (node.closest("a")) return;
      const href = hrefs.get(node.textContent.trim());
      if (!href) return;
      node.style.cursor = "pointer";
      node.setAttribute("role","link");
      node.setAttribute("tabindex","0");
      node.onclick = () => location.href = href;
      node.onkeydown = event => { if (event.key === "Enter" || event.key === " ") location.href = href; };
    });
    linkVisibleText();
    working = false;
  }
  new MutationObserver(apply).observe(document.body, {childList:true, subtree:true});
  apply();
})();
