import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import vm from "node:vm";

const root = new URL("../", import.meta.url);

test("attached model recommends fouling down two with eight seconds", async () => {
  const html = await readFile(new URL("wnbl-hackulator.html", root), "utf8");
  const model = [...html.matchAll(/<script(?: [^>]*)?>([\s\S]*?)<\/script>/g)]
    .map((match) => match[1])
    .find((script) => script.includes("function trailingFoulModel"));
  assert.ok(model, "replacement decision model should be embedded");

  const start = model.indexOf("const state =");
  const end = model.indexOf("/* ============================================================\n   RENDER: mode tabs");
  const context = {};
  vm.createContext(context);
  vm.runInContext(`${model.slice(start, end)}\n    globalThis.result = {
      guard: trailingDefendModel(2, 8, {holdTime:17,pScore:.44,w3:.45,p2:.46,p3:.31,otWin:.5,ft:.4}),
      foul: trailingFoulModel(2, 8, {foulCost:6,p2:.46,p3:.31,otWin:.5,ft:.4})
    };`, context);

  assert.ok(context.result.foul.winProb > context.result.guard.winProb);
  assert.equal(context.result.guard.remaining, -9);
  assert.equal(context.result.foul.remaining, 2);
  assert.ok((context.result.foul.winProb-context.result.guard.winProb)*100 > 5);
});

test("replacement retains both late-game decision modes", async () => {
  const html = await readFile(new URL("wnbl-hackulator.html", root), "utf8");
  for (const text of [
    "Late Game: Foul or Guard?",
    "Leading: foul or guard",
    "Trailing: get the ball back",
    "function upThreeModel",
    "function trailingDefendModel",
    "function trailingFoulModel",
  ]) assert.ok(html.includes(text), text);
  assert.ok(html.includes('src="site-shell.js"'));
  assert.ok(html.includes('visual-refresh-live.css'));
});
