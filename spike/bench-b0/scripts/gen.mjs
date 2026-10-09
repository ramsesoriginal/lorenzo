// A SIMULATED repository: the real seed could not be built here (no Docker/Postgres), so this
// generates entries in the shape RFC 0039 W3 describes (kinds, link name, parents, own stat values
// by definition id, tags, information as the caller may read it, flags). Deterministic.
let s = 12345;
const rnd = () => ((s = (s * 1664525 + 1013904223) >>> 0) / 2 ** 32);
const pick = (a) => a[Math.floor(rnd() ** 2 * a.length)]; // skewed towards the front, like prose
const WORDS = ("the of and to a in is that it as with for was on are be at by this from or an have not but which one all their can had were when there use your each other how said them so than then these some her would make like him into time has look two more write go see number way could people my than first water been call who oil now find long down day did get come made may part over new sound take only little work know place year live me back give most very after thing our just name good sentence man think say great where help through much before line right too mean old any same tell boy follow came want show also around form three small set put end does another well large must big even such because turn here why ask went men read need land different home us move try kind hand picture again change off play spell air away animal house point page letter mother answer found study still learn should world high every near add food between own below country plant last school father keep tree never start city earth eye light thought head under story saw left don't few while along might close something seem next hard open example begin life always those both paper together got group often run important until children side feet car mile night walk white sea began grow took river four carry state once book hear stop without second later miss idea enough eat face watch far indian really almost let above girl sometimes mountain cut young talk soon list song being leave family it's weapon armour blade steel iron oak leather gold silver copper damage piercing slashing bludgeoning finesse versatile heavy light reach thrown loading ammunition range martial simple proficiency bonus shield helmet strap pouch rope torch rations pack bedroll").split(" ");
const sentence = () => { const n = 6 + Math.floor(rnd() * 12); const w = Array.from({ length: n }, () => pick(WORDS)); w[0] = w[0][0].toUpperCase() + w[0].slice(1); return `${w.join(" ")}.`; };
let corpus = null; // real sentences, when given: a fairer test of how well real prose compresses
export const useCorpus = (sentences) => { corpus = sentences; };
const text = (chars) => { let t = ""; while (t.length < chars) t += `${corpus ? corpus[Math.floor(rnd() * corpus.length)] : sentence()} `; return t.trim(); };
const uuid = (i, p = "a") => `${p}${String(i).padStart(7, "0")}-0000-4000-8000-${String(i * 7919 % 1e12).padStart(12, "0")}`;

export function simulate(n, { descChars = 350, gmChars = 900, gmShare = 0.2 } = {}) {
  const parents = Array.from({ length: 40 }, (_, i) => uuid(i, "b")); // a taxonomy of ~40 shared prototypes
  const defs = Array.from({ length: 24 }, (_, i) => uuid(i, "c"));
  const entries = [];
  for (let i = 0; i < n; i++) {
    const name = `${pick(WORDS)} ${pick(WORDS)} ${i}`.replace(/^./, (c) => c.toUpperCase());
    const nstats = 2 + Math.floor(rnd() * 8);
    const stats = {};
    for (let k = 0; k < nstats; k++) stats[pick(defs)] = Math.round(rnd() * 1000) / 10;
    const information = [{ id: uuid(i, "d"), type: "description", visibility: "public", order: 0, text: text(descChars * (0.5 + rnd())), updated_at: "2026-10-08T12:00:00.000000Z" }];
    if (rnd() < gmShare) information.push({ id: uuid(i, "e"), type: "note", visibility: "gm", order: 1, text: text(gmChars * (0.5 + rnd())), updated_at: "2026-10-08T12:00:00.000000Z" });
    entries.push({
      id: uuid(i, "f"), kinds: ["item"], name, link_name: name.toLowerCase().replace(/[^a-z0-9]+/g, "-"),
      parents: [pick(parents), ...(rnd() < 0.3 ? [pick(parents)] : [])],
      stats, tags: rnd() < 0.5 ? [uuid(Math.floor(rnd() * 12), "9")] : [], information,
      flags: { in_public_catalog: rnd() < 0.8 }, updated_at: "2026-10-08T12:00:00.000000Z",
    });
  }
  return entries;
}
export const names = (entries) => entries.map(({ id, kinds, name, link_name, parents }) => ({ id, kinds, name, link_name, parents }));
