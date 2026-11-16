// The palette command contract (palette-command.schema.json): the sample entries follow it, and the
// icons they name are in the atlas. A small checker, so the test needs no dependency.
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const brand = join(dirname(fileURLToPath(import.meta.url)), "..");
const schema = JSON.parse(readFileSync(join(brand, "palette-command.schema.json"), "utf8"));
const sample = JSON.parse(readFileSync(join(brand, "tests/palette-commands.sample.json"), "utf8"));
const atlas = new Set([...readFileSync(join(brand, "icons.svg"), "utf8").matchAll(/id="(icon-[a-z0-9-]+)"/g)].map((m) => m[1]));

function check(cmd) {
  const errors = [];
  for (const k of schema.required) if (!(k in cmd)) errors.push(`${cmd.id ?? "?"}: missing ${k}`);
  for (const [k, v] of Object.entries(cmd)) {
    const def = schema.properties[k];
    if (!def) { errors.push(`${cmd.id}: unknown ${k}`); continue; }
    if (def.type === "string" && typeof v !== "string") errors.push(`${cmd.id}: ${k} is not a string`);
    if (def.type === "string" && def.pattern && !new RegExp(def.pattern).test(v)) errors.push(`${cmd.id}: ${k} "${v}" does not match`);
    if (def.minLength && v.length < def.minLength) errors.push(`${cmd.id}: ${k} is empty`);
    if (def.enum && !def.enum.includes(v)) errors.push(`${cmd.id}: ${k} "${v}" is not one of ${def.enum.join(", ")}`);
    if (k === "icon" && !atlas.has(v)) errors.push(`${cmd.id}: ${v} is not in icons.svg`);
  }
  return errors;
}

test("the sample commands follow the contract", () => {
  assert.deepEqual(sample.flatMap(check), []);
  assert.equal(new Set(sample.map((c) => c.id)).size, sample.length, "ids are unique");
});

test("the checker rejects a bad command", () => {
  assert.ok(check({ id: "Bad Id", name: "", group: "Nowhere", icon: "icon-nope", keys: "ctrl+k", extra: 1 }).length >= 5);
});
