// The 300-row editable grid: light-DOM custom elements on the signal helper (RFC 0039 §9).
import type { Model } from "./model";
import { effect } from "./signal";
import type { Runner } from "./runner";
import { type Field, STAT_KEYS } from "./types";

const LABEL = {
  synced: "Synced",
  waiting: "Waiting to sync",
  "saved-on-device": "Saved on this device",
  conflict: "Conflict",
  attention: "Needs attention",
} as const;

export class BenchRow extends HTMLElement {
  renders = 0;
  model!: Model;
  runner!: Runner;
  entryId = "";
  private inputs = new Map<Field, HTMLInputElement>();
  private stateEl!: HTMLElement;
  private conflictEl!: HTMLElement;
  private stop: (() => void) | null = null;

  connectedCallback() {
    if (this.stop) return;
    this.setAttribute("role", "row");
    this.dataset.id = this.entryId;
    for (const f of ["name", ...STAT_KEYS] as Field[]) {
      const i = document.createElement("input");
      i.dataset.field = f;
      i.setAttribute("aria-label", `${f} of ${this.entryId.slice(0, 8)}`);
      i.addEventListener("input", () => this.model.edit(this.entryId, f, i.value));
      this.inputs.set(f, i);
      this.append(i);
    }
    this.stateEl = document.createElement("span");
    this.stateEl.className = "state";
    this.conflictEl = document.createElement("span");
    this.conflictEl.className = "conflict";
    this.append(this.stateEl, this.conflictEl);
    const view = this.model.rows.get(this.entryId)!;
    this.stop = effect(() => {
      const v = view();
      this.renders++;
      this.dataset.renders = String(this.renders);
      this.dataset.state = v.state;
      // never write into an input the user is typing in, and only write what differs:
      // that is what keeps focus, caret and selection through every other change
      const set = (f: Field, value: string) => {
        const el = this.inputs.get(f)!;
        if (el.value !== value && document.activeElement !== el) el.value = value;
      };
      set("name", v.name);
      for (const k of STAT_KEYS) set(k, v.stats[k] === null ? "" : String(v.stats[k]));
      const text = `${LABEL[v.state]}${v.pending ? ` (${v.pending})` : ""}`;
      if (this.stateEl.textContent !== text) this.stateEl.textContent = text;
      if (v.conflict) {
        const { cmdId, field, base, mine, theirs } = v.conflict;
        this.conflictEl.replaceChildren();
        const t = document.createElement("span");
        t.textContent = `${field}: base ${base ?? "-"} / mine ${mine ?? "-"} / theirs ${theirs ?? "-"} `;
        const keep = document.createElement("button");
        keep.textContent = "Keep mine";
        keep.dataset.action = "keep-mine";
        keep.onclick = () => void this.runner.resolve(cmdId, "mine");
        const use = document.createElement("button");
        use.textContent = "Use theirs";
        use.dataset.action = "use-theirs";
        use.onclick = () => void this.runner.resolve(cmdId, "theirs");
        this.conflictEl.append(t, keep, use);
      } else if (this.conflictEl.firstChild) this.conflictEl.replaceChildren();
    });
  }
  disconnectedCallback() {
    this.stop?.();
    this.stop = null;
  }
}
customElements.define("bench-row", BenchRow);

export class BenchGrid extends HTMLElement {
  model!: Model;
  runner!: Runner;
  private known = new Set<string>();

  render() {
    this.setAttribute("role", "grid");
    const frag = document.createDocumentFragment();
    for (const id of this.model.order) frag.append(this.makeRow(id));
    this.replaceChildren(frag);
  }
  makeRow(id: string) {
    const row = document.createElement("bench-row") as BenchRow;
    row.model = this.model;
    row.runner = this.runner;
    row.entryId = id;
    this.known.add(id);
    return row;
  }
  /** Rows created later (an offline create) are added at the top; existing rows are untouched. */
  sync() {
    for (const id of this.model.order) {
      if (!this.known.has(id)) this.prepend(this.makeRow(id));
    }
  }
}
customElements.define("bench-grid", BenchGrid);
