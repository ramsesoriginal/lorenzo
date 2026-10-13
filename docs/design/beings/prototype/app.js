/*
 * The being sheet prototype. Vanilla JS on purpose: it is a reference for layout and behaviour,
 * not code to ship (the real app is Astro + small TypeScript, ADR 0270). Edits change an
 * in-memory copy, nothing is stored, and there is no server.
 */
(function () {
  "use strict";

  const BRAND = "../../../../apps/brand/";
  const clone = () => JSON.parse(JSON.stringify(window.BEINGS));
  const beings = clone();
  const state = {
    adjust: null, // "g-s" of the tile whose adjuster is open
    flash: null, // { key, delta } for the last change
    history: [], // undo stack

    id: beings[0].id,
    mode: "read",
    view: "sheet",
    viewer: "gm",
    noteForm: false,
    savedAt: null,
  };
  const root = document.getElementById("app");

  /* ---------- helpers ---------- */
  const esc = (s) =>
    String(s).replace(
      /[&<>"']/g,
      (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c],
    );
  const ic = (name) =>
    `<svg class="icon" aria-hidden="true"><use href="#icon-${name}"></use></svg>`;
  const cur = () => beings.find((b) => b.id === state.id);
  const hasPlayer = (b) => b.players.length > 0;

  function viewer() {
    const b = cur();
    if (state.viewer === "player" && hasPlayer(b)) return "player";
    if (state.viewer === "gm") return "gm";
    return "other";
  }
  const canEdit = () => viewer() !== "other";
  const mode = () =>
    state.mode === "edit" && !canEdit() ? "read" : state.mode;

  function toast(msg) {
    let t = document.querySelector(".toast");
    if (!t) {
      t = document.createElement("div");
      t.className = "toast";
      t.setAttribute("role", "status");
      document.body.append(t);
    }
    t.textContent = msg;
    clearTimeout(toast.t);
    toast.t = setTimeout(() => t.remove(), 2600);
  }
  /* One small live region, so a screen reader hears "Hit points 24" and not the whole page. */
  function announce(msg) {
    const el = document.getElementById("live");
    if (!el) return;
    el.textContent = "";
    setTimeout(() => (el.textContent = msg), 30);
  }
  function saved() {
    state.savedAt = Date.now();
    const el = document.getElementById("save-status");
    if (el) el.textContent = "Saved just now";
  }

  /* ---------- audience ---------- */
  const AUDIENCE = {
    gm: {
      icon: "private",
      label: "GM only",
      line: "The campaign's GMs and the library's owners and organizers.",
    },
    everyone: {
      icon: null,
      label: "Everyone",
      line: "Anyone with access to the library.",
    },
    some: {
      icon: "kind-groups",
      label: "Some characters",
      line: "The GMs and the characters you choose.",
    },
    player: {
      icon: "kind-being",
      label: "Player note",
      line: "The GMs and this being's players.",
    },
  };
  function audienceBadge(n) {
    const a = AUDIENCE[n.audience];
    if (!a.icon) return ""; // public needs no badge (identity.md section 6.6)
    const extra =
      n.audience === "some" && n.to ? `: ${esc(n.to.join(", "))}` : "";
    return `<span class="badge-visibility">${ic(a.icon)}${a.label}${extra}</span>`;
  }
  function visibleNotes(b) {
    const v = viewer();
    return b.notes.filter((n) => {
      if (v === "gm") return true;
      if (n.audience === "everyone") return true;
      if (v === "player")
        return n.audience === "player" || n.audience === "some";
      return false;
    });
  }
  function audienceChoices() {
    const v = viewer();
    if (v === "gm") return ["gm", "everyone", "some", "player"];
    if (v === "player") return ["player", "everyone"];
    return [];
  }

  /* ---------- stats ---------- */
  function isNum(s) {
    return s.type === "int" || s.type === "decimal";
  }
  function derived(s) {
    return Boolean(s.from || s.formula);
  }
  const sign = (n) => (n > 0 ? "+" : n < 0 ? "−" : "±") + Math.abs(n);
  function provenance(s) {
    if (s.formula) {
      return `<details class="why"><summary>${ic("formula")}Calculated</summary>
        <div class="why-panel"><p>${esc(s.formula.text)}</p><dl>${s.formula.parts
          .map(([k, v]) => `<dt>${esc(k)}</dt><dd>${esc(v)}</dd>`)
          .join(
            "",
          )}<dt><strong>Total</strong></dt><dd><strong>${esc(s.value)}</strong></dd></dl></div></details>`;
    }
    if (s.from)
      return `<span class="stat-prov">${ic("inherited-from")}From ${esc(s.from)}</span>`;
    return "";
  }
  const canAdjust = (s) => mode() === "play" && s.adjustable && canEdit();

  /* The value: a field in Edit, a button that opens the adjuster in Play, plain text otherwise. */
  function valueEl(s, gi, si, id) {
    const m = mode();
    const unit = s.unit ? `<span class="unit">${esc(s.unit)}</span>` : "";
    if (m === "edit" && !s.formula) {
      return `<input class="text-input" id="${id}" data-edit="stat" data-g="${gi}" data-s="${si}" aria-label="${esc(s.label)}" value="${esc(s.value)}" ${isNum(s) ? 'inputmode="numeric"' : ""}>`;
    }
    if (canAdjust(s)) {
      return `<button type="button" class="stat-value stat-value-btn" data-act="adj-open" data-g="${gi}" data-s="${si}" data-focus="val-${gi}-${si}" aria-haspopup="dialog" aria-expanded="${state.adjust === gi + "-" + si}" aria-label="Change ${esc(s.label)}, now ${esc(s.value)}">${esc(s.value)}${unit}</button>`;
    }
    return `<span class="stat-value">${esc(s.value)}${unit}</span>`;
  }
  function stepper(s, gi, si) {
    if (!canAdjust(s)) return "";
    return `<span class="stat-stepper"><button type="button" class="icon-btn" data-act="step" data-g="${gi}" data-s="${si}" data-d="-1" data-focus="m${gi}-${si}" aria-label="Lower ${esc(s.label)} by 1">−</button><button type="button" class="icon-btn" data-act="step" data-g="${gi}" data-s="${si}" data-d="1" data-focus="p${gi}-${si}" aria-label="Raise ${esc(s.label)} by 1">+</button></span>`;
  }
  /* Take away, add, or set: the amount is what the table says ("seven damage"). */
  function adjustPanel(s, gi, si) {
    if (state.adjust !== gi + "-" + si) return "";
    return `<div class="adjust" role="dialog" aria-label="Change ${esc(s.label)}">
      <label class="field-label" for="adj-amt">Amount</label>
      <input class="text-input" id="adj-amt" type="number" inputmode="numeric" min="0" value="1" data-focus="adj-amt">
      <div class="adjust-actions">
        <button type="button" class="btn btn-secondary" data-act="adj-sub" data-g="${gi}" data-s="${si}">Take away</button>
        <button type="button" class="btn btn-secondary" data-act="adj-add" data-g="${gi}" data-s="${si}">Add</button>
        <button type="button" class="btn btn-secondary" data-act="adj-set" data-g="${gi}" data-s="${si}">Set to</button>
      </div>
      <button type="button" class="btn btn-quiet" data-act="adj-close">Close</button></div>`;
  }
  function tile(s, gi, si) {
    const useInherited =
      mode() === "edit" && s.from
        ? `<button type="button" class="btn btn-quiet" data-act="inherit" data-g="${gi}" data-s="${si}">Use inherited</button>`
        : "";
    /* Always four children, so the label, value, caption and foot rows line up across a row of tiles (subgrid). */
    return `<div class="stat-tile ${derived(s) ? "is-derived" : ""}" data-key="${gi}-${si}">
      <span class="stat-label">${esc(s.label)}</span>
      ${valueEl(s, gi, si, `stat-${gi}-${si}`)}
      <span class="stat-sub">${s.sub ? esc(s.sub) : ""}</span>
      <div class="stat-foot">${provenance(s)}${useInherited}${stepper(s, gi, si)}${adjustPanel(s, gi, si)}</div>
    </div>`;
  }
  function groupBlock(g, gi) {
    const nums = g.stats.map((s, si) => [s, si]).filter(([s]) => isNum(s));
    const rest = g.stats.map((s, si) => [s, si]).filter(([s]) => !isNum(s));
    const m = mode();
    return `<div class="stat-group">
      <h3>${esc(g.name)} <span class="caption">${g.stats.length} ${g.stats.length === 1 ? "stat" : "stats"}</span></h3>
      ${nums.length ? `<div class="stat-grid">${nums.map(([s, si]) => tile(s, gi, si)).join("")}</div>` : ""}
      ${
        rest.length
          ? `<dl class="stat-rows">${rest
              .map(
                ([s, si]) =>
                  `<dt>${esc(s.label)}</dt><dd>${
                    m === "edit"
                      ? `<input class="text-input" id="stat-${gi}-${si}" data-edit="stat" data-g="${gi}" data-s="${si}" aria-label="${esc(s.label)}" value="${esc(s.value)}">`
                      : esc(s.value)
                  }</dd>`,
              )
              .join("")}</dl>`
          : ""
      }
    </div>`;
  }
  const legend = `<details class="legend"><summary>Key</summary><div class="legend-panel">
      <p><span class="swatch"></span> Set on this being.</p>
      <p><span class="swatch is-derived"></span> Inherited from a prototype, or calculated.</p></div></details>`;
  function statsSection(b) {
    const m = mode();
    const edit = m === "edit";
    const add = edit
      ? `<button type="button" class="btn btn-secondary" data-act="todo" data-msg="The stat picker lists the library's stat definitions.">${ic("add")}Add a stat</button>`
      : "";
    if (!b.groups.length) {
      return `<section class="sheet-section" id="stats"><header><h2>Stats</h2><span class="grow"></span>${add}</header>
        <div class="empty"><p>${esc(b.name)} has no stats. That is fine: a being without numbers is still a being.</p></div></section>`;
    }
    return `<section class="sheet-section" id="stats"><header><h2>Stats</h2>${legend}<span class="grow"></span>${add}</header>
      <div class="stat-band">${b.groups.map(groupBlock).join("")}</div></section>`;
  }

  /* ---------- tags ---------- */
  function tagsRow(b) {
    const m = mode();
    const interactive = m === "play" || m === "edit";
    const items = b.tags
      .map((t, i) => {
        const stateWord =
          t.state === "inherited"
            ? `From ${t.from}`
            : t.state === "on"
              ? "On"
              : "Off";
        if (!interactive || !canEdit()) {
          if (t.state === "off") return "";
          return `<span class="tag-toggle" data-state="${t.state}" title="${t.state === "inherited" ? "From " + esc(t.from) : ""}">${esc(t.label)}</span>`;
        }
        return `<button type="button" class="tag-toggle" data-act="tag" data-i="${i}" data-focus="tag${i}" data-state="${t.state}" aria-pressed="${t.state !== "off"}">${esc(t.label)}${m === "edit" ? ` <span class="state">${stateWord}</span>` : ""}</button>`;
      })
      .join("");
    const add =
      m === "edit"
        ? `<form class="inline-form" data-form="tag"><label class="visually-hidden" for="new-tag">New tag</label><input class="text-input" style="width:11rem" id="new-tag" placeholder="Add a tag"><button class="btn btn-secondary" type="submit">${ic("add")}Add</button></form>`
        : "";
    if (!items.trim() && !add) return "";
    return `<div class="tag-row" aria-label="Tags">${items}${add}</div>`;
  }

  /* ---------- description ---------- */
  function aboutSection(b, collapsed) {
    const m = mode();
    if (m === "edit") {
      return `<section class="sheet-section about" id="about"><header><h2>About</h2><span class="caption">LorenzoScript. Links by name: <code>[[Thistlemere]]</code></span></header>
        <div class="stack-tight"><label class="visually-hidden" for="desc">Description</label>
        <textarea class="text-input" id="desc" data-edit="desc">${esc(b.descriptionSource)}</textarea>
        <p class="caption">The prototype does not re-render this text; the real editor shows a live preview beside it.</p>
        <div class="ls-content">${b.description}</div></div></section>`;
    }
    const body = b.description.trim()
      ? `<div class="ls-content">${b.description}</div>`
      : `<p class="status-text">Nothing has been written about ${esc(b.name)} yet.</p>`;
    if (collapsed) {
      return `<section class="sheet-section about" id="about"><details><summary><strong>About ${esc(b.name.split(" ")[0])}</strong> <span class="caption">Read the description</span></summary><div style="margin-top:var(--space-3)">${body}</div></details></section>`;
    }
    return `<section class="sheet-section about" id="about"><header><h2>About</h2></header>${body}</section>`;
  }

  /* ---------- notes ---------- */
  function noteCard(n, i, b) {
    const m = mode();
    const actions =
      m === "edit"
        ? `<div class="note-actions">
            <button type="button" class="icon-btn" aria-label="Move note up" data-act="note-up" data-i="${i}">${ic("up")}</button>
            <button type="button" class="icon-btn" aria-label="Move note down" data-act="note-down" data-i="${i}">${ic("down")}</button>
            <button type="button" class="icon-btn" aria-label="Edit note" data-act="todo" data-msg="The note opens its form in place, as in ADR 0271.">${ic("edit")}</button>
            <button type="button" class="icon-btn" aria-label="Delete note" data-act="note-del" data-i="${i}">${ic("delete")}</button></div>`
        : "";
    return `<article class="note"><header><h3>${esc(n.label)}</h3>${audienceBadge(n)}${actions}</header>
      <div class="ls-content">${n.body}</div><p class="caption">${esc(n.author)}</p></article>`;
  }
  function noteForm() {
    const choices = audienceChoices();
    return `<form class="note stack-tight" data-form="note" aria-label="New note">
      <div class="field"><label class="field-label" for="note-label">Label</label><input class="text-input" id="note-label" placeholder="Note" ></div>
      <div class="field"><label class="field-label" for="note-body">Text (LorenzoScript)</label><textarea class="text-input" id="note-body" style="min-height:6rem"></textarea></div>
      <fieldset><legend>Who can read it</legend><div class="audience-options">${choices
        .map(
          (c, i) =>
            `<label><input type="radio" name="aud" value="${c}" ${i === 0 ? "checked" : ""}> <span>${AUDIENCE[c].label}</span><span class="caption">${AUDIENCE[c].line}</span></label>`,
        )
        .join("")}</div></fieldset>
      <div class="row"><button class="btn btn-primary" type="submit">Add note</button><button class="btn btn-secondary" type="button" data-act="note-cancel">Cancel</button></div></form>`;
  }
  function notesSection(b) {
    const notes = visibleNotes(b);
    const choices = audienceChoices();
    const addBtn =
      choices.length && !state.noteForm
        ? `<button type="button" class="btn btn-secondary" data-act="note-new" data-focus="note-new">${ic("add")}Add a note</button>`
        : "";
    const hidden = viewer() !== "gm" && b.notes.length > notes.length;
    return `<section class="sheet-section" id="notes"><header><h2>Notes</h2><span class="caption">${notes.length} you can read</span>${addBtn}</header>
      <div class="stack-tight">${
        notes.length
          ? notes.map((n) => noteCard(n, b.notes.indexOf(n), b)).join("")
          : `<div class="empty"><p>Nothing has been shared with you about ${esc(b.name)} yet.</p></div>`
      }${state.noteForm ? noteForm() : ""}</div></section>`;
  }

  /* ---------- inventory ---------- */
  function inventorySection(b) {
    const cap = b.capacity
      ? `<div class="inv-load"><span>${esc(b.capacity.label)}</span><div class="bar" role="meter" aria-valuemin="0" aria-valuemax="${b.capacity.of}" aria-valuenow="${b.capacity.value}" aria-label="${esc(b.capacity.label)}"><span style="width:${Math.min(100, (b.capacity.value / b.capacity.of) * 100)}%"></span></div><span class="stat-sub" style="font-variant-numeric:tabular-nums">${b.capacity.value} of ${b.capacity.of} ${b.capacity.unit}</span></div>`
      : "";
    const list = b.items.length
      ? `<ul class="inv-list">${b.items
          .map(
            (it) =>
              `<li><span>${esc(it.name)}${it.qty > 1 ? ` <span class="num">×${it.qty}</span>` : ""}</span><span class="where">${esc(it.where)}</span><span class="num">${it.weight ? it.weight + " lb" : ""}</span></li>`,
          )
          .join("")}</ul>`
      : `<div class="empty"><p>${esc(b.name)} owns nothing yet.</p></div>`;
    return `<section class="sheet-section" id="inventory"><header><h2>Inventory</h2><span class="caption">${b.items.length} ${b.items.length === 1 ? "thing" : "things"}</span>
      <a class="btn btn-secondary" href="#" data-act="todo" data-msg="Opens the board in Lorenzo Inventory.">${ic("inventory")}Open the board</a></header>${cap}${list}</section>`;
  }

  /* ---------- rail ---------- */
  function railPeople(b) {
    const v = viewer();
    const people = b.players.length
      ? b.players
          .map(
            (p) =>
              `<div class="person"><strong>${esc(p.name)}${v === "player" && p.owner ? " (you)" : ""}</strong><span class="caption">${p.owner ? "Plays" : "Shares"} · ${esc(p.campaign)}</span></div>`,
          )
          .join("")
      : `<p class="status-text">No one plays ${esc(b.name.split(" ")[0])}. ${v === "gm" ? "The GM runs this being." : ""}</p>`;
    const hand =
      mode() === "edit" && v === "gm"
        ? `<form class="stack-tight" data-form="hand" style="margin-top:var(--space-2)">
            <div class="field"><label class="field-label" for="h-camp">Campaign</label><select class="text-input" id="h-camp"><option>${esc(b.library)}</option></select></div>
            <div class="field"><label class="field-label" for="h-pl">Player</label><select class="text-input" id="h-pl"><option>Dana Okafor</option><option>Tobias Reyes</option><option>Mara Quill</option></select></div>
            <button class="btn btn-secondary" type="submit">${ic("handoff")}Hand over</button></form>`
        : "";
    return `<aside class="card rail-card" aria-labelledby="people-h"><h2 id="people-h">Played by</h2>${people}${hand}</aside>`;
  }
  function railDetails(b) {
    return `<aside class="card rail-card" aria-labelledby="det-h"><h2 id="det-h">Details</h2>
      <dl class="key-values"><dt>Link name</dt><dd>${esc(b.slug)}</dd><dt>Kind</dt><dd>${esc(b.kind)}</dd><dt>Library</dt><dd>${esc(b.library)}</dd></dl>
      <button type="button" class="btn btn-secondary" data-act="copy">${ic("copy")}Copy link</button></aside>`;
  }

  /* ---------- header ---------- */
  function header(b) {
    const m = mode();
    const edit = m === "edit";
    const kindIcon = b.kind === "Character" ? "kind-being" : "kind-being-heart";
    const sub = b.players.length
      ? `Played by ${esc(b.players[0].name)}${viewer() === "player" ? " (you)" : ""} · ${esc(b.players[0].campaign)}`
      : `${esc(b.library)} · run by the GM`;
    const modes = [
      ["read", "Read"],
      ["play", "Play"],
      ["edit", "Edit"],
    ];
    const seg = `<div class="segmented" role="radiogroup" aria-label="Mode">${modes
      .map(([k, l]) => {
        const dis = k === "edit" && !canEdit();
        return `<label ${dis ? 'title="You can’t edit this being."' : ""}><input type="radio" name="mode" value="${k}" data-focus="mode-${k}" ${m === k ? "checked" : ""} ${dis ? "disabled" : ""}>${l}</label>`;
      })
      .join("")}</div>`;
    const view = `<div class="segmented quiet" role="radiogroup" aria-label="Layout">${[
      ["sheet", "Sheet"],
      ["datasheet", "Datasheet"],
    ]
      .map(
        ([k, l]) =>
          `<label><input type="radio" name="view" value="${k}" data-focus="view-${k}" ${state.view === k ? "checked" : ""}>${l}</label>`,
      )
      .join("")}</div>`;
    return `<header class="card sheet-head" id="top">
      <div><div class="portrait" data-tone="${b.pictureTone}" role="img" aria-label="No picture yet">${esc(b.initials)}</div>
        ${edit ? `<div class="edit-picture"><button class="btn btn-secondary" type="button" data-act="todo" data-msg="PNG, JPEG, WebP or GIF, up to 2 MB.">${ic("upload")}Replace</button><button class="btn btn-secondary" type="button" data-act="todo" data-msg="The picture is removed.">Remove</button></div>` : ""}</div>
      <div class="sheet-meta">
        ${edit ? `<div class="field"><label class="field-label" for="name">Name</label><input class="text-input" id="name" data-edit="name" value="${esc(b.name)}"></div>` : `<h1 class="sheet-name">${esc(b.name)}</h1>`}
        <div class="sheet-sub"><span class="kind">${ic(kindIcon)}${b.kind}</span><span>${sub}</span>
          ${edit ? "" : `<span class="mono">${esc(b.slug)}</span>`}</div>
        ${edit ? `<div class="field"><label class="field-label" for="slug">Link name</label><input class="text-input mono" id="slug" data-edit="slug" value="${esc(b.slug)}"><span class="caption">Used in links: [[${esc(b.slug)}]]</span></div>` : ""}
        ${tagsRow(b)}
      </div>
      <div class="sheet-tools">${seg}${view}<span class="status-text" id="save-status" role="status">${edit ? "Changes save as you go" : ""}</span></div>
    </header>`;
  }

  /* ---------- datasheet ---------- */
  function dsCell(s, gi, si) {
    const unit = s.unit ? `<span class="unit">${esc(s.unit)}</span>` : "";
    return `<div class="ds-cell ${derived(s) ? "is-derived" : ""}" data-key="${gi}-${si}"><span class="stat-label">${esc(s.label)}</span>${valueEl(s, gi, si, `ds-${gi}-${si}`)}${s.sub ? `<span class="stat-sub">${esc(s.sub)}</span>` : ""}<div class="stat-foot">${provenance(s)}${stepper(s, gi, si)}${adjustPanel(s, gi, si)}</div></div>`;
  }
  function datasheet(b) {
    const keys = [...new Set(b.items.flatMap((i) => Object.keys(i.stats)))];
    const weapons = keys.length > 0;
    const table = b.items.length
      ? `<div class="ds-table-wrap"><table class="ds-table"><thead><tr><th scope="col">${weapons ? "Weapon" : "Item"}</th>${
          weapons
            ? keys.map((k) => `<th scope="col">${k}</th>`).join("")
            : '<th scope="col">Where</th><th scope="col">Qty</th><th scope="col">Weight</th>'
        }</tr></thead><tbody>${b.items
          .map(
            (it) =>
              `<tr><td>${esc(it.name)}</td>${
                weapons
                  ? keys
                      .map((k) => `<td>${esc(it.stats[k] ?? "—")}</td>`)
                      .join("")
                  : `<td>${esc(it.where)}</td><td>${it.qty}</td><td>${it.weight ? it.weight + " lb" : "—"}</td>`
              }</tr>`,
          )
          .join("")}</tbody></table></div>`
      : "";
    const notes = visibleNotes(b);
    return `<article class="card datasheet" aria-label="Datasheet for ${esc(b.name)}">
      ${b.groups
        .map(
          (g, gi) =>
            `<div class="ds-line"><h3>${esc(g.name)}</h3><div class="ds-cells">${g.stats.map((s, si) => dsCell(s, gi, si)).join("")}</div></div>`,
        )
        .join("")}
      ${b.groups.length ? "" : '<div class="ds-block"><p class="status-text">No stats. The datasheet shows what there is.</p></div>'}
      ${table ? `<div class="ds-block"><h3>${weapons ? "Weapons" : "Carried"}</h3>${table}</div>` : ""}
      ${
        notes.length
          ? `<div class="ds-block"><h3>Abilities and notes</h3>${notes
              .map(
                (n) =>
                  `<div class="ds-note"><div><strong>${esc(n.label)}</strong><br>${audienceBadge(n)}</div><div class="ls-content">${n.body}</div></div>`,
              )
              .join("")}</div>`
          : ""
      }
      <div class="ds-block">${aboutSection(b, true).replace('class="sheet-section about"', 'class="about"')}</div>
    </article>`;
  }

  /* ---------- page ---------- */
  function stickyBar(b) {
    const pinned = b.groups.flatMap((g) => g.stats).filter((s) => s.pin);
    const vit = pinned.length
      ? pinned
      : (b.groups[0] ? b.groups[0].stats.filter(isNum) : []).slice(0, 3);
    const m = mode();
    const seg = `<div class="segmented" role="radiogroup" aria-label="Mode">${[
      ["read", "Read"],
      ["play", "Play"],
      ["edit", "Edit"],
    ]
      .map(([k, l]) => {
        const dis = k === "edit" && !canEdit();
        return `<label><input type="radio" name="mode-sticky" value="${k}" data-focus="smode-${k}" ${m === k ? "checked" : ""} ${dis ? "disabled" : ""}>${l}</label>`;
      })
      .join("")}</div>`;
    return `<div class="sticky-bar" id="stickybar" hidden><span class="display sticky-name">${esc(b.name)}</span>
      <span class="sticky-vitals">${vit.map((s) => `<span>${esc(s.label)} <strong>${esc(s.value)}${s.unit ? " " + esc(s.unit) : ""}</strong></span>`).join("")}</span>
      <span class="grow"></span>${state.view === "sheet" ? `<nav class="sticky-nav" aria-label="Sections"><a href="#about">About</a><a href="#notes">Notes</a><a href="#stats">Stats</a><a href="#inventory">Inventory</a></nav>` : ""}${seg}</div>`;
  }

  function render() {
    const keep =
      document.activeElement && document.activeElement.dataset
        ? document.activeElement.dataset.focus
        : null;
    const y = window.scrollY;
    const b = cur();
    const m = mode();
    let body;
    if (state.view === "datasheet") {
      body = `<div class="stack">${datasheet(b)}</div>`;
    } else {
      // Read puts the prose first, Play the numbers first; Edit follows Read so the page does not jump.
      const order =
        m === "play"
          ? [
              statsSection(b),
              inventorySection(b),
              notesSection(b),
              aboutSection(b, true),
            ]
          : [
              aboutSection(b, false),
              notesSection(b),
              statsSection(b),
              inventorySection(b),
            ];
      body = `<div class="sheet-layout"><div class="sheet-main">${order.join("")}</div><div class="sheet-rail">${railPeople(b)}${railDetails(b)}</div></div>`;
    }
    root.innerHTML = `<div class="sheet-page ${state.view === "datasheet" ? "is-datasheet" : ""}">${header(b)}${stickyBar(b)}${body}</div>`;
    applyFlash();
    const lib = document.getElementById("lib-name");
    if (lib) lib.textContent = b.library;
    watchSticky();
    window.scrollTo(0, y);
    if (keep) {
      const el = root.querySelector(`[data-focus="${keep}"]`);
      if (el) el.focus({ preventScroll: true });
    }
    placeAdjuster(); // last, so the amount field keeps the focus when the adjuster has just opened
  }

  let io;
  function watchSticky() {
    if (io) io.disconnect();
    const head = document.getElementById("top");
    const sb = document.getElementById("stickybar");
    if (!head || !sb || !("IntersectionObserver" in window)) return;
    io = new IntersectionObserver(([e]) => {
      sb.hidden = e.isIntersecting;
    });
    io.observe(head);
  }

  /* ---------- changes, undo and what-changed ---------- */
  let undoTimer;
  function showUndo(label) {
    const bar = document.getElementById("undo-bar");
    document.getElementById("undo-text").textContent = label;
    bar.hidden = false;
    clearTimeout(undoTimer);
    undoTimer = setTimeout(() => (bar.hidden = true), 9000);
  }
  /* Every change in play goes through here: apply it, remember how to take it back, say what happened. */
  function change(label, key, delta, doIt, undoIt) {
    doIt();
    state.history.push({ label, undoIt });
    if (state.history.length > 30) state.history.shift();
    state.flash = { key, delta };
    state.adjust = null;
    announce(label);
    showUndo(label);
    saved();
    render();
  }
  function undo() {
    const h = state.history.pop();
    if (!h) return;
    h.undoIt();
    state.flash = null;
    announce("Undone: " + h.label);
    const bar = document.getElementById("undo-bar");
    if (state.history.length) showUndo("Undone: " + h.label);
    else bar.hidden = true;
    saved();
    render();
  }
  /* The changed tile gets a short highlight and the amount; both go away by themselves. */
  function applyFlash() {
    const f = state.flash;
    state.flash = null;
    if (!f) return;
    const el = root.querySelector(`[data-key="${f.key}"]`);
    if (!el) return;
    el.classList.add("is-changed");
    const chip = document.createElement("span");
    chip.className = "stat-delta";
    chip.textContent = f.delta;
    chip.setAttribute("aria-hidden", "true");
    el.append(chip);
    setTimeout(() => {
      el.classList.remove("is-changed");
      chip.remove();
    }, 2600);
  }
  /* Keep the adjuster on screen: flip it to the tile's other edge when it would run off. */
  function placeAdjuster() {
    const a = root.querySelector(".adjust");
    if (!a) return;
    const r = a.getBoundingClientRect();
    if (r.right > window.innerWidth - 8) a.classList.add("to-end");
    a.scrollIntoView({ block: "nearest" });
    document.getElementById("adj-amt")?.focus({ preventScroll: true });
  }
  const closeWhy = () =>
    document
      .querySelectorAll("details.why[open]")
      .forEach((d) => (d.open = false));

  function setValue(b, g, s, next, how) {
    const stat = b.groups[g].stats[s];
    const old = Number(stat.value);
    const nv = Math.max(0, next);
    if (nv === old) return;
    change(
      `${stat.label} ${old} → ${nv}`,
      `${g}-${s}`,
      sign(nv - old),
      () => (stat.value = nv),
      () => (stat.value = old),
    );
  }

  /* ---------- events ---------- */
  document.addEventListener("change", (e) => {
    const t = e.target;
    if (t.name === "mode" || t.name === "mode-sticky") {
      state.mode = t.value;
      state.noteForm = false;
      state.adjust = null;
      announce(t.value[0].toUpperCase() + t.value.slice(1) + " mode");
      // The sticky bar stays where it is; the header may be out of view.
      render();
    } else if (t.name === "view") {
      state.view = t.value;
      render();
    } else if (t.id === "pick-being") {
      state.id = t.value;
      state.noteForm = false;
      state.adjust = null;
      render();
    } else if (t.id === "pick-viewer") {
      state.viewer = t.value;
      state.noteForm = false;
      state.adjust = null;
      render();
    } else if (t.dataset && t.dataset.edit) {
      const b = cur();
      if (t.dataset.edit === "name") b.name = t.value;
      if (t.dataset.edit === "slug") b.slug = t.value;
      if (t.dataset.edit === "desc") b.descriptionSource = t.value;
      if (t.dataset.edit === "stat") {
        const s = b.groups[t.dataset.g].stats[t.dataset.s];
        s.value =
          isNum(s) && t.value.trim() !== "" && !isNaN(Number(t.value))
            ? Number(t.value)
            : t.value;
      }
      saved();
    }
  });

  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      closeWhy();
      if (state.adjust) {
        const [g, s] = state.adjust.split("-");
        state.adjust = null;
        render();
        root.querySelector(`[data-focus="val-${g}-${s}"]`)?.focus();
      }
    }
    const typing = /^(INPUT|TEXTAREA|SELECT)$/.test(
      document.activeElement.tagName,
    );
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "z" && !typing) {
      e.preventDefault();
      undo();
    }
  });

  document.addEventListener("click", (e) => {
    if (!e.target.closest(".why")) closeWhy();
    if (
      state.adjust &&
      !e.target.closest(".adjust") &&
      !e.target.closest('[data-act="adj-open"]')
    ) {
      state.adjust = null;
      render();
    }
    const el = e.target.closest("[data-act]");
    if (!el) return;
    const b = cur();
    const act = el.dataset.act;
    if (el.tagName === "A") e.preventDefault();
    if (act === "step") {
      const stat = b.groups[el.dataset.g].stats[el.dataset.s];
      setValue(
        b,
        el.dataset.g,
        el.dataset.s,
        Number(stat.value) + Number(el.dataset.d),
      );
    } else if (act === "adj-open") {
      const key = el.dataset.g + "-" + el.dataset.s;
      state.adjust = state.adjust === key ? null : key;
      render();
    } else if (act === "adj-close") {
      const [g, s] = state.adjust.split("-");
      state.adjust = null;
      render();
      root.querySelector(`[data-focus="val-${g}-${s}"]`)?.focus();
    } else if (act === "adj-sub" || act === "adj-add" || act === "adj-set") {
      const input = document.getElementById("adj-amt");
      const n = Number(input.value);
      if (input.value.trim() === "" || isNaN(n) || n < 0) {
        announce("Enter an amount, zero or more.");
        input.focus();
        return;
      }
      const stat = b.groups[el.dataset.g].stats[el.dataset.s];
      const old = Number(stat.value);
      const next =
        act === "adj-sub" ? old - n : act === "adj-add" ? old + n : n;
      const g = el.dataset.g;
      const s = el.dataset.s;
      if (Math.max(0, next) === old) {
        state.adjust = null;
        render();
        return;
      }
      setValue(b, g, s, next);
      root.querySelector(`[data-focus="val-${g}-${s}"]`)?.focus();
    } else if (act === "undo") {
      undo();
    } else if (act === "tag") {
      const t = b.tags[el.dataset.i];
      const before = t.state;
      const after =
        mode() === "edit"
          ? { inherited: "on", on: "off", off: t.from ? "inherited" : "on" }[
              before
            ]
          : before === "off"
            ? "on"
            : "off";
      change(
        `${t.label} ${after === "off" ? "off" : after === "on" ? "on" : "inherited"}`,
        "",
        "",
        () => (t.state = after),
        () => (t.state = before),
      );
    } else if (act === "inherit") {
      toast("Cleared. The value now comes from the prototype again.");
    } else if (act === "note-new") {
      state.noteForm = true;
      render();
      document.getElementById("note-label")?.focus();
    } else if (act === "note-cancel") {
      state.noteForm = false;
      render();
    } else if (act === "note-del") {
      b.notes.splice(el.dataset.i, 1);
      saved();
      render();
    } else if (act === "note-up" || act === "note-down") {
      const i = Number(el.dataset.i);
      const j = act === "note-up" ? i - 1 : i + 1;
      if (j >= 0 && j < b.notes.length) {
        [b.notes[i], b.notes[j]] = [b.notes[j], b.notes[i]];
        saved();
        render();
      }
    } else if (act === "copy") {
      toast("Link copied.");
    } else if (act === "reset") {
      beings.splice(0, beings.length, ...clone());
      state.history = [];
      state.adjust = null;
      document.getElementById("undo-bar").hidden = true;
      announce("Example data restored");
      render();
    } else if (act === "todo") {
      toast(el.dataset.msg || "Not in the prototype.");
    }
  });

  document.addEventListener("submit", (e) => {
    const f = e.target.closest("[data-form]");
    if (!f) return;
    e.preventDefault();
    const b = cur();
    if (f.dataset.form === "note") {
      const label =
        document.getElementById("note-label").value.trim() || "Note";
      const body = document.getElementById("note-body").value.trim();
      const aud = f.querySelector("input[name=aud]:checked").value;
      b.notes.push({
        id: Date.now(),
        label,
        audience: aud,
        to: aud === "some" ? ["Tobias Reyes"] : undefined,
        author: viewer() === "gm" ? "GM" : (b.players[0] || {}).name || "You",
        body: `<p>${esc(body || "…")}</p>`,
      });
      state.noteForm = false;
      saved();
      render();
      toast("Note added.");
    } else if (f.dataset.form === "tag") {
      const v = document.getElementById("new-tag").value.trim();
      if (v) {
        b.tags.push({ label: v, state: "on" });
        saved();
        render();
      }
    } else if (f.dataset.form === "hand") {
      const name = document.getElementById("h-pl").value;
      b.players = [{ name, campaign: b.library, owner: true }];
      b.kind = "Character";
      saved();
      render();
      toast(`${b.name} is now ${name}'s.`);
    }
  });

  /* ---------- prototype controls ---------- */
  function controls() {
    document.getElementById("controls").innerHTML = `
      <strong>Prototype</strong>
      <div class="field"><label class="field-label" for="pick-being">Being</label>
        <select class="text-input" id="pick-being">${beings.map((b) => `<option value="${b.id}">${esc(b.name)} · ${b.kind}</option>`).join("")}</select></div>
      <div class="field"><label class="field-label" for="pick-viewer">Viewing as</label>
        <select class="text-input" id="pick-viewer"><option value="gm">The GM</option><option value="player">A player of this being</option><option value="other">Another player</option></select></div>
      <button class="btn btn-secondary" type="button" id="theme">Dark theme</button>
      <button class="btn btn-secondary" type="button" data-act="reset">Restore example data</button>`;
    document.getElementById("theme").addEventListener("click", (e) => {
      const dark = document.documentElement.dataset.theme !== "dark";
      document.documentElement.dataset.theme = dark ? "dark" : "light";
      e.currentTarget.textContent = dark ? "Light theme" : "Dark theme";
    });
  }

  /* ---------- start ---------- */
  const spriteReady = Boolean(document.getElementById("icon-add"));
  (spriteReady ? Promise.resolve(null) : fetch(BRAND + "icons.svg"))
    .then((r) => {
      if (r === null) return null;
      if (!r.ok) throw new Error(r.status);
      return r.text();
    })
    .then((svg) => {
      if (svg === null) return;
      // Parsed, never assigned to innerHTML: the sprite is data, not markup to trust.
      const sprite = new DOMParser().parseFromString(svg, "image/svg+xml").documentElement;
      const d = document.createElement("div");
      d.hidden = true;
      d.append(document.importNode(sprite, true));
      document.body.prepend(d);
    })
    .catch(() => {
      document.getElementById("icons-note").hidden = false;
    })
    .finally(() => {
      controls();
      render();
    });
})();
