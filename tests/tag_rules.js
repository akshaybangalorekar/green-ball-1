// Run: node tests/tag_rules.js   — checks the tag logic and that no card contradicts itself.
const fs = require("fs");
const src = fs.readFileSync(process.argv[2] || "index.html", "utf8")
  .match(/<script>([\s\S]*)<\/script>/)[1];

const store = {}, made = {};
const el = (id) => made[id] || (made[id] = { id, innerHTML: "", textContent: "", value: "",
  classList: { add(){}, remove(){}, contains: () => false }, setAttribute(){}, querySelectorAll: () => [],
  dataset: {}, style: {}, focus(){}, addEventListener(){}, nextElementSibling: null, children: [] });
global.document = { documentElement: { dataset: {} }, querySelector: (s) => el(s.replace("#", "")),
  querySelectorAll: () => [], addEventListener(){}, body: { style: {} }, createElement: () => ({ style: {}, appendChild(){}, setAttribute(){} }) };
global.window = { matchMedia: () => ({ matches: false }), addEventListener(){}, scrollTo(){}, location: { hash: "" } };
global.navigator = { onLine: true, serviceWorker: { register: () => Promise.resolve() } };
global.localStorage = { getItem: (k) => store[k] || null, setItem: (k, v) => store[k] = v, removeItem: (k) => delete store[k] };
global.sessionStorage = { getItem: () => null, setItem(){} };
global.Notification = function(){}; global.Notification.permission = "default";
global.history = { replaceState(){} }; global.location = { hash: "" };

const api = new Function(src + "; return { liveEvents, setLIVE:(v)=>{LIVE=v;} };")();

const cases = [
  ["UTR matchplay",      { name: "TERM 4 Junior UTR Matchplay", date: "2026-11-28", src: "utr", ball: "yellow" }, "Start here"],
  ["JDS",                { name: "2026 JDS CBC Green Ball Gardiner", date: "2026-12-05", src: "ta", ball: "green" }, "Start here"],
  ["JC",                 { name: "2026 OC JC East Coburg", date: "2026-11-28", src: "ta", ball: "yellow" }, "Start here"],
  ["J125",               { name: "2027 J125 Metro East GWSH", date: "2027-03-05", src: "ta", ball: "yellow" }, "Target"],
  ["J250",               { name: "2027 J250 GBS125 Waverley", date: "2027-03-06", src: "ta", ball: "yellow" }, "Target"],
  ["J500",               { name: "2027 J500 Junior Slam", date: "2027-05-01", src: "ta", ball: "yellow" }, "Target"],
  ["J1000",              { name: "2027 J1000 National", date: "2027-05-03", src: "ta", ball: "yellow" }, "Target"],
  ["orange hot shots",   { name: "Vida Essendon Orange Hot Shots Match Play #10", date: "2026-11-29", src: "ta", ball: "green" }, "Easy"],
  ["unknown level",      { name: "Some Open Event", date: "2027-04-01", src: "ta", ball: "yellow" }, "Open"],
  ["band fits",          { name: "Test In", date: "2027-04-01", src: "ta", utrMin: 1.0, utrMax: 3.0 }, "Start here"],
  ["band +0.6",          { name: "Test Up", date: "2027-04-01", src: "ta", utrMin: 2.2, utrMax: 3.5 }, "Target"],
  ["band +2.0",          { name: "Test Far", date: "2027-04-01", src: "ta", utrMin: 3.6, utrMax: 5.0 }, "Later"],
  ["band below him",     { name: "Test Low", date: "2027-04-01", src: "ta", utrMin: 0.2, utrMax: 0.9 }, "Easy"],
];

api.setLIVE(cases.map((c) => c[1]));
const got = api.liveEvents();
let fails = 0;
cases.forEach(([label, , want], i) => {
  const ok = got[i].p === want;
  if (!ok) { fails++; console.log("FAIL", label, "expected", want, "got", got[i].p); }
});
console.log(fails ? `${fails} failure(s)` : `all ${cases.length} tag cases pass`);
process.exit(fails ? 1 : 0);
