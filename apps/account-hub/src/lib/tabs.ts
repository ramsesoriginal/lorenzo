// A tabbed view: a `role="tablist"` of `role="tab"` buttons (the brand's `.tabs` and `.tab`), and a
// `role="tabpanel"` for each, one shown at a time. They sit side by side, directly in the element
// this is bound to, and pair up in order.
//
// A tab is there only while its panel has something in it: a child that is not `hidden`. So a view
// whose panels are filled or emptied later (by whichever tenant is open, say) has the tabs it
// needs, and with a single one left shows its panel without the strip.
//
// The pattern's keyboard: Left and Right (wrapping), Home and End move between the tabs, and only
// the selected tab is in the Tab order, so Tab carries on into its panel.

// Each view on a page gets its own ids.
let views = 0;

export type BoundTabs = {
  // Shows the tabs whose panels have something in them, and the selected one's panel. Call it when
  // what the panels hold has changed.
  refresh(): void;
  // Goes back to the first tab, for a new set of panels.
  reset(): void;
};

function hasContent(panel: HTMLElement): boolean {
  return [...panel.children].some((child) => !child.hasAttribute('hidden'));
}

// `root` holds the tablist and the panels. The first tab is selected.
export function bindTabs(root: HTMLElement): BoundTabs {
  const children = [...root.children];
  const tablist = children.find((child) => child.getAttribute('role') === 'tablist');
  const panels = children.filter(
    (child): child is HTMLElement =>
      child instanceof HTMLElement && child.getAttribute('role') === 'tabpanel',
  );
  const tabs = [...(tablist?.children ?? [])].filter(
    (child): child is HTMLElement =>
      child instanceof HTMLElement && child.getAttribute('role') === 'tab',
  );

  if (!(tablist instanceof HTMLElement) || tabs.length === 0 || tabs.length !== panels.length) {
    throw new Error('A tabbed view needs a tablist, and as many tab panels as tabs.');
  }

  views += 1;

  // Narrowed here, which a function declared below does not see in `tablist`.
  const strip: HTMLElement = tablist;

  tabs.forEach((tab, index) => {
    const panel = panels[index];

    if (!panel) return;

    tab.id = `tabs-${views}-tab-${index}`;
    panel.id = `tabs-${views}-panel-${index}`;
    tab.setAttribute('aria-controls', panel.id);
    panel.setAttribute('aria-labelledby', tab.id);
  });

  // What the person chose, kept while its panel is empty (a page loading again), and what is shown:
  // the chosen tab if there is one, else the first there is.
  let wanted = 0;
  let selected = 0;

  function open(): boolean[] {
    return panels.map(hasContent);
  }

  function refresh(): void {
    const available = open();

    // The chosen tab is not there (yet): the first one there is takes its place, for now.
    selected = available[wanted] ? wanted : Math.max(available.indexOf(true), 0);

    tabs.forEach((tab, index) => {
      const on = index === selected;

      tab.hidden = !available[index];
      tab.setAttribute('aria-selected', String(on));
      tab.tabIndex = on ? 0 : -1;

      const panel = panels[index];

      if (panel) panel.hidden = !(available[index] && on);
    });

    // One tab is nothing to choose between.
    strip.hidden = available.filter(Boolean).length < 2;
  }

  tabs.forEach((tab, index) => {
    tab.addEventListener('click', () => {
      wanted = index;
      refresh();
    });
    tab.addEventListener('keydown', (event) => {
      // Only among the tabs that are there.
      const there = open().flatMap((on, at) => (on ? [at] : []));
      const position = there.indexOf(index);
      const target =
        event.key === 'ArrowRight'
          ? there[(position + 1) % there.length]
          : event.key === 'ArrowLeft'
            ? there[(position + there.length - 1) % there.length]
            : event.key === 'Home'
              ? there[0]
              : event.key === 'End'
                ? there[there.length - 1]
                : undefined;

      if (target === undefined) return;

      event.preventDefault();
      wanted = target;
      refresh();
      tabs[target]?.focus();
    });
  });

  refresh();

  return {
    refresh,
    reset() {
      wanted = 0;
      refresh();
    },
  };
}
