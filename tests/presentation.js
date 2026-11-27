// Run: node tests/presentation.js index.html  — checks the card never contradicts its data.
const fs = require("fs");
const src = fs.readFileSync(process.argv[2] || "index.html", "utf8").match(/<script>([\s\S]*)<\/script>/)[1];

const store = { "em-gb1-pathway": "1" }, made = {};
const el = (id) => made[id] || (made[id] = { id, innerHTML: "", textContent: "", value: "",
  classList: { add(){}, remove(){}, contains: () => false }, setAttribute(){}, querySelectorAll: () => [],
  dataset: {}, style: {}, focus(){}, addEventListener(){}, nextElementSibling: null, children: [] });
global.document = { documentElement: { dataset: {} }, querySelector: (s) => el(s.replace("#", "")),
  querySelectorAll: () => [], addEventListener(){}, body: { style: {} }, createElement: () => ({ style: {}, appendChild(){}, setAttribute(){} }) };
global.window = { matchMedia: () => ({ matches: false }), addEventListener(){}, scrollTo(){}, location: { hash: "" } };
global.navigator = { onLine: true, serviceWorker: { register: () => Promise.resolve() } };
global.localStorage = { getItem: (k) => store[k] || null, setItem: (k, v) => store[k] = v, removeItem: (k) => delete store[k] };
global.sessionStorage = { getItem: () => null, setItem(){} };
global.Notification = function(){}; global.Notification.promise = "default"; global.Notification.permission = "default";
global.history = { replaceState(){} }; global.location = { hash: "" };

const api = new Function(src + "; return { viewPathway, setLIVE:(v)=>{LIVE=v;} };")();

const EVENTS = [
  { name: "Test Dropped Event", date: "2026-12-10", src: "ta", ball: "yellow", dropped: "no age groups published", p: "Start here" },
  { name: "Test Members Event", date: "2026-12-11", src: "ta", ball: "yellow", note: "members only — check before entering", p: "Start here" },
  { name: "Test Green Ball Event", date: "2026-12-12", src: "ta", ball: "green", p: "Start here" },
  { name: "Test Plain Event", date: "2026-12-13", src: "ta", ball: "yellow", p: "Start here" },
];
api.setLIVE(EVENTS);
const html = api.viewPathway();
const cards = html.split('<div class="ev">').slice(1);

let fails = 0;
const check = (label, ok) => { if (!ok) { fails++; console.log("FAIL", label); } };

check("four cards rendered", cards.length === 4);
cards.forEach((c, i) => {
  const name = EVENTS[i].name;
  const tags = (c.match(/class="evpri [^"]*"/g) || []).length;
  check(`${name}: exactly one tag`, tags === 1);
  if (EVENTS[i].dropped) {
    check(`${name}: dropped shows Not eligible`, /Not eligible/.test(c));
    check(`${name}: dropped has no level tag`, !/Book now|Good target|Worth entering|Comfortable|Need more time/.test(c));
    check(`${name}: dropped has no recommendation`, !/quickest way|gentle first step|Relaxed entry/.test(c));
  }
  if (EVENTS[i].note) {
    check(`${name}: members shows Members only`, /Members only/.test(c));
    check(`${name}: members is not Book now`, !/Book now/.test(c));
  }
  if (EVENTS[i].ball === "green") {
    check(`${name}: green ball carries the caveat`, /counts only if UTR-listed/.test(c));
  }
});
console.log(fails ? `${fails} failure(s)` : `all presentation checks pass`);
process.exit(fails ? 1 : 0);
