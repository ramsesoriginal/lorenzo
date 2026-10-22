import { randomUUID } from 'node:crypto';
import AxeBuilder from '@axe-core/playwright';
import { type Browser, expect, type Page, test } from '@playwright/test';
import { apiAs, ok, refreshTokenFor } from './support/api.ts';
import { REFRESH_TOKEN_KEY, SITE_URL } from './support/env.ts';

async function signedIn(
  browser: Browser,
  subject: string,
  look: { theme?: 'light' | 'dark'; viewport?: { width: number; height: number } } = {},
) {
  const token = await refreshTokenFor(subject);
  const localStorage = [{ name: REFRESH_TOKEN_KEY, value: token }];
  if (look.theme) localStorage.push({ name: 'lorenzo:sessions:theme', value: look.theme });
  const context = await browser.newContext({
    ...(look.viewport ? { viewport: look.viewport } : {}),
    storageState: { cookies: [], origins: [{ origin: SITE_URL, localStorage }] },
  });
  return context.newPage();
}

// What a reference row says about who can read it: its badge, inside the row of that entry.
const relationship = (page: Page, audience: 'Private' | 'Shared') =>
  page
    .getByRole('listitem')
    .filter({ hasText: 'Guild ownership' })
    .getByText(audience, { exact: true });
async function world() {
  const subject = `session-gm-${randomUUID()}`;
  const gm = await apiAs(subject, ['tenant_creator']);
  const me = await ok(gm.GET('/me'));
  const tenant = await ok(
    gm.POST('/tenants', { body: { name: `Session library ${randomUUID()}` } }),
  );
  const path = { tenant_id: tenant.id };
  const campaign = await ok(
    gm.POST('/tenants/{tenant_id}/campaigns', {
      params: { path },
      body: {
        name: 'Harbour campaign',
        game_system: 'Homebrew',
        slug: `harbour-${randomUUID()}`,
        description: '',
        secret: false,
      },
    }),
  );
  await ok(
    gm.PUT('/tenants/{tenant_id}/campaigns/{campaign_id}/gms/{user_id}', {
      params: { path: { ...path, campaign_id: campaign.id, user_id: me.id } },
    }),
  );
  const playerSubject = `session-player-${randomUUID()}`;
  const player = await apiAs(playerSubject);
  const playerMe = await ok(player.GET('/me'));
  const seat = await ok(
    gm.POST('/tenants/{tenant_id}/campaigns/{campaign_id}/players', {
      params: { path: { ...path, campaign_id: campaign.id } },
      body: { user_id: playerMe.id },
    }),
  );
  return { subject, gm, tenant, me, campaign, player, playerSubject, seat, path };
}
test('GM prepares a session, player keeps a restricted note, and Scene reuse keeps notes separate', async ({
  browser,
}, testInfo) => {
  const w = await world();
  const gm = await signedIn(browser, w.subject);
  const player = await signedIn(browser, w.playerSubject);
  try {
    await gm.goto('/');
    await expect
      .poll(() =>
        gm
          .getByRole('img', { name: 'Lorenzo', exact: true })
          .first()
          .evaluate((img) => (img as HTMLImageElement).naturalWidth),
      )
      .toBeGreaterThan(0);
    await gm.getByLabel('Session title', { exact: true }).fill('At the wreck');
    await gm.getByLabel('Link name (optional)').fill('wreck-session');
    await gm.getByRole('button', { name: 'Create Session', exact: true }).click();
    await expect(gm.getByRole('heading', { name: 'At the wreck', exact: true })).toBeVisible();
    const sid = (await ok(w.gm.GET('/me/sessions')))[0].id;
    const path = { ...w.path, session_id: sid };
    let result = await w.gm.GET('/tenants/{tenant_id}/sessions/{session_id}', { params: { path } });
    await ok(
      w.gm.PUT('/tenants/{tenant_id}/sessions/{session_id}/roster', {
        params: { path, header: { 'if-match': result.response.headers.get('etag') ?? '' } },
        body: { gm_user_ids: [w.me.id], players: [{ player_id: w.seat.id, character_ids: [] }] },
      }),
    );
    await gm.reload();
    await gm.getByLabel('New Scene title').fill('Exploring the wreck');
    await gm.getByLabel('Make the reusable Scene visible in this library').check();
    await gm.getByLabel('Share this Scene appearance with Session participants').check();
    await gm.getByRole('button', { name: 'Add Scene', exact: true }).click();
    await expect(
      gm.getByRole('heading', { name: 'Exploring the wreck', exact: true }),
    ).toBeVisible();
    await player.setViewportSize({ width: 390, height: 844 });
    await player.goto(`/session/?tenant=${w.tenant.id}&id=wreck-session`);
    await expect(player.getByRole('heading', { name: 'At the wreck', exact: true })).toBeVisible();
    await expect(player.getByRole('button', { name: 'Save roster' })).toHaveCount(0);
    await player.getByRole('button', { name: 'Add note', exact: true }).first().click();
    await player.getByLabel('Note title', { exact: true }).fill('My recollection');
    await player
      .getByRole('textbox', { name: 'Note', exact: true })
      .fill('I think the guide recognised the ship.');
    await player.getByRole('button', { name: 'Save note', exact: true }).click();
    await expect(
      player.getByRole('heading', { name: 'My recollection', exact: true }),
    ).toBeVisible();
    await player.screenshot({ path: testInfo.outputPath('session-phone.png'), fullPage: true });
    await gm.reload();
    await expect(gm.getByRole('heading', { name: 'My recollection', exact: true })).toBeVisible();
    await expect(gm.getByText('I think the guide recognised the ship.')).toBeVisible();
    result = await w.gm.GET('/tenants/{tenant_id}/sessions/{session_id}', { params: { path } });
    const original = await ok(Promise.resolve(result));
    const appearanceId = original.scenes[0].id;
    await ok(
      w.gm.POST('/tenants/{tenant_id}/sessions/{session_id}/scenes', {
        params: { path, header: { 'if-match': result.response.headers.get('etag') ?? '' } },
        body: { scene_entity_id: original.scenes[0].scene_entity_id, is_shared: true },
      }),
    );
    await player.reload();
    await expect(
      player.getByRole('heading', { name: 'Exploring the wreck', exact: true }),
    ).toHaveCount(2);
    await expect(player.getByRole('heading', { name: 'My recollection', exact: true })).toHaveCount(
      1,
    );
    const clean = await ok(
      w.player.GET('/tenants/{tenant_id}/entities/{entity_id}', {
        params: { path: { ...w.path, entity_id: appearanceId } },
      }),
    );
    expect(clean.information).toHaveLength(0);
  } finally {
    await gm.context().close();
    await player.context().close();
    await w.gm.DELETE('/tenants/{tenant_id}', { params: { path: w.path } });
  }
});
test('signed-out view and explicit theme work on a phone', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/');
  await expect(page.getByRole('button', { name: 'Log in', exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Dark theme', exact: true }).click();
  await page.reload();
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark');
});

test('a concurrent session edit keeps the draft until the GM reviews the saved revision', async ({
  browser,
}) => {
  const w = await world();
  const page = await signedIn(browser, w.subject);
  try {
    const session = await ok(
      w.gm.POST('/tenants/{tenant_id}/sessions', {
        params: { path: w.path },
        body: { name: 'Original preparation', campaign_id: w.campaign.id },
      }),
    );
    const path = { ...w.path, session_id: session.id };
    await page.goto(`/session/?tenant=${w.tenant.id}&id=${session.id}`);
    await page.getByText('Session details', { exact: true }).click();
    await page.getByLabel('Session title', { exact: true }).fill('My draft');
    const current = await w.gm.GET('/tenants/{tenant_id}/sessions/{session_id}', {
      params: { path },
    });
    await ok(
      w.gm.PATCH('/tenants/{tenant_id}/sessions/{session_id}', {
        params: { path, header: { 'if-match': current.response.headers.get('etag') ?? '' } },
        body: { name: 'Other saved edit' },
      }),
    );
    await page.getByRole('button', { name: 'Save Session details', exact: true }).click();
    await expect(page.getByText(/Your draft is still here/)).toBeVisible();
    await expect(page.getByLabel('Session title', { exact: true })).toHaveValue('My draft');
    await page.getByRole('button', { name: 'Review saved Session', exact: true }).click();
    await expect(page.getByText(/Saved Session: Other saved edit/)).toBeVisible();
    await expect(page.getByLabel('Session title', { exact: true })).toHaveValue('My draft');
    await page.getByRole('button', { name: 'Save Session details', exact: true }).click();
    await expect(page.getByRole('heading', { name: 'My draft', exact: true })).toBeVisible();
  } finally {
    await page.context().close();
    await w.gm.DELETE('/tenants/{tenant_id}', { params: { path: w.path } });
  }
});

test('reusable Scene context stays separate from session notes and sharing is explicit', async ({
  browser,
}) => {
  const w = await world();
  const page = await signedIn(browser, w.subject);
  try {
    const fact = await ok(
      w.gm.POST('/tenants/{tenant_id}/entities', {
        params: { path: w.path },
        body: { name: 'Guild ownership', kinds: ['fact'], parents: [], visibility: 'library' },
      }),
    );
    await page.goto(`/scenes/?tenant=${w.tenant.id}`);
    await page.getByLabel('Scene title', { exact: true }).fill('At the lighthouse');
    await page.getByLabel('Link name (optional)').fill('lighthouse-scene');
    await page.getByRole('button', { name: 'Create Scene', exact: true }).click();
    await expect(
      page.getByRole('heading', { name: 'At the lighthouse', exact: true }),
    ).toBeVisible();
    await expect(page).toHaveURL(/slug=lighthouse-scene/);
    await page.getByLabel('Reference to add').selectOption({ label: 'Guild ownership · Fact' });
    await page.getByRole('button', { name: 'Add reference', exact: true }).click();
    await expect(relationship(page, 'Private')).toBeVisible();
    await page.getByRole('button', { name: 'Share relationship', exact: true }).click();
    await expect(relationship(page, 'Shared')).toBeVisible();
    await page.getByText('Scene details', { exact: true }).click();
    await page.getByLabel('Visible in this library').check();
    await page.getByRole('button', { name: 'Save Scene', exact: true }).click();
    const scene = (
      await ok(
        w.gm.GET('/tenants/{tenant_id}/entities/resolve', {
          params: { path: w.path, query: { slug: ['lighthouse-scene'] } },
        }),
      )
    )[0];
    const refs = await ok(
      w.player.GET('/tenants/{tenant_id}/{source_kind}/{source_id}/references', {
        params: { path: { ...w.path, source_kind: 'scenes', source_id: scene.entity_id } },
      }),
    );
    expect(refs.map((r) => r.id)).toEqual([fact.id]);
    await page.getByRole('button', { name: 'Remove reference', exact: true }).click();
    await expect(relationship(page, 'Shared')).toHaveCount(0);
  } finally {
    await page.context().close();
    await w.gm.DELETE('/tenants/{tenant_id}', { params: { path: w.path } });
  }
});

test('GM reviews a played-order proposal and records repeated Event presentation independently', async ({
  browser,
}) => {
  const w = await world();
  const page = await signedIn(browser, w.subject);
  try {
    const session = await ok(
      w.gm.POST('/tenants/{tenant_id}/sessions', {
        params: { path: w.path },
        body: { name: 'Flashback session', campaign_id: w.campaign.id },
      }),
    );
    const scene = await ok(
      w.gm.POST('/tenants/{tenant_id}/scenes', {
        params: { path: w.path },
        body: { name: 'The memory', is_public: true },
      }),
    );
    const path = { ...w.path, session_id: session.id };
    const initial = await w.gm.GET('/tenants/{tenant_id}/sessions/{session_id}', {
      params: { path },
    });
    await ok(
      w.gm.POST('/tenants/{tenant_id}/sessions/{session_id}/scenes', {
        params: { path, header: { 'if-match': initial.response.headers.get('etag') ?? '' } },
        body: { scene_entity_id: scene.id, is_shared: true },
      }),
    );
    await ok(
      w.gm.POST('/tenants/{tenant_id}/entities', {
        params: { path: w.path },
        body: { name: 'The earlier launch', kinds: ['event'], parents: [], visibility: 'library' },
      }),
    );
    await page.goto(`/session/?tenant=${w.tenant.id}&id=${session.id}`);
    await page.getByText('Review and record played Scenes', { exact: true }).click();
    await page
      .getByRole('button', { name: 'Propose played order from preparation', exact: true })
      .click();
    await expect(
      page.getByText('Proposal only. Review the Scene statuses and order, then save explicitly.', {
        exact: true,
      }),
    ).toBeVisible();
    let read = await ok(
      w.gm.GET('/tenants/{tenant_id}/sessions/{session_id}/play', { params: { path } }),
    );
    expect(read.played_appearance_ids).toEqual([]);
    await page.getByRole('button', { name: 'Save played Scenes', exact: true }).click();
    await expect(
      page.getByRole('heading', { name: 'The memory · played', exact: true }),
    ).toBeVisible();
    await page.getByRole('button', { name: 'Record Event presentation', exact: true }).click();
    await expect(page.getByRole('button', { name: 'Share presentation', exact: true })).toHaveCount(
      1,
    );
    await page.getByRole('button', { name: 'Record Event presentation', exact: true }).click();
    await expect(page.getByRole('button', { name: 'Share presentation', exact: true })).toHaveCount(
      2,
    );
    read = await ok(
      w.gm.GET('/tenants/{tenant_id}/sessions/{session_id}/play', { params: { path } }),
    );
    expect(read.presentations).toHaveLength(2);
    expect(read.presentations[0].id).not.toBe(read.presentations[1].id);
    await page.getByText('Edit order of Sessions I manage', { exact: true }).click();
    await page.getByRole('button', { name: 'Place Session at end', exact: true }).click();
    await page.getByRole('button', { name: 'Save Session order', exact: true }).click();
    await expect(
      page.getByText('Unplaced Sessions available to you: none', { exact: true }),
    ).toBeVisible();
    const ordered = await ok(
      w.gm.GET('/tenants/{tenant_id}/campaigns/{campaign_id}/session-sequence', {
        params: { path: { ...w.path, campaign_id: w.campaign.id } },
      }),
    );
    expect(ordered.ordered.map((s) => s.id)).toEqual([session.id]);
  } finally {
    await page.context().close();
    await w.gm.DELETE('/tenants/{tenant_id}', { params: { path: w.path } });
  }
});

test('a flashback proposal needs explicit review and correction before it becomes lived evidence', async ({
  browser,
}) => {
  const w = await world();
  const page = await signedIn(browser, w.subject);
  try {
    const session = await ok(
      w.gm.POST('/tenants/{tenant_id}/sessions', {
        params: { path: w.path },
        body: { name: 'Flashback and life', campaign_id: w.campaign.id },
      }),
    );
    const path = { ...w.path, session_id: session.id };
    const scene = await ok(
      w.gm.POST('/tenants/{tenant_id}/scenes', {
        params: { path: w.path },
        body: { name: 'Looking back', is_public: true },
      }),
    );
    let current = await w.gm.GET('/tenants/{tenant_id}/sessions/{session_id}', {
      params: { path },
    });
    const outline = await ok(
      w.gm.POST('/tenants/{tenant_id}/sessions/{session_id}/scenes', {
        params: { path, header: { 'if-match': current.response.headers.get('etag') ?? '' } },
        body: { scene_entity_id: scene.id, is_shared: true },
      }),
    );
    const appearance = outline.scenes[0].id;
    const events = [];
    for (const name of ['The launch', 'The wreck'])
      events.push(
        await ok(
          w.gm.POST('/tenants/{tenant_id}/entities', {
            params: { path: w.path },
            body: { name, kinds: ['event'], parents: [], visibility: 'library' },
          }),
        ),
      );
    const being = await ok(
      w.gm.POST('/tenants/{tenant_id}/entities', {
        params: { path: w.path },
        body: { name: 'Mara', kinds: ['being'], parents: [] },
      }),
    );
    for (const event of events) {
      const eventPath = { ...w.path, event_id: event.id };
      const result = await w.gm.GET('/tenants/{tenant_id}/events/{event_id}/participants', {
        params: { path: eventPath },
      });
      await ok(
        w.gm.PUT('/tenants/{tenant_id}/events/{event_id}/participants/{being_id}', {
          params: {
            path: { ...eventPath, being_id: being.id },
            header: { 'if-match': result.response.headers.get('etag') ?? '' },
          },
        }),
      );
    }
    const relationPath = { ...w.path, event_id: events[0].id };
    const relation = await w.gm.GET('/tenants/{tenant_id}/events/{event_id}/relationships', {
      params: { path: relationPath },
    });
    await ok(
      w.gm.PUT('/tenants/{tenant_id}/events/{event_id}/relationships/{other_event_id}', {
        params: {
          path: { ...relationPath, other_event_id: events[1].id },
          header: { 'if-match': relation.response.headers.get('etag') ?? '' },
        },
        body: { kind: 'causes', direction: 'outgoing' },
      }),
    );
    for (const event of [...events].reverse()) {
      current = await w.gm.GET('/tenants/{tenant_id}/sessions/{session_id}', { params: { path } });
      await ok(
        w.gm.POST(
          '/tenants/{tenant_id}/sessions/{session_id}/scenes/{appearance_id}/presentations',
          {
            params: {
              path: { ...path, appearance_id: appearance },
              header: { 'if-match': current.response.headers.get('etag') ?? '' },
            },
            body: { event_id: event.id, is_shared: false },
          },
        ),
      );
    }
    current = await w.gm.GET('/tenants/{tenant_id}/sessions/{session_id}', { params: { path } });
    await ok(
      w.gm.PUT('/tenants/{tenant_id}/sessions/{session_id}/play', {
        params: { path, header: { 'if-match': current.response.headers.get('etag') ?? '' } },
        body: { played_appearance_ids: [appearance] },
      }),
    );
    await page.goto(`/lived/?tenant=${w.tenant.id}&being=${being.id}&session=${session.id}`);
    await expect(
      page.getByRole('heading', { name: 'Mara · personal lived order', exact: true }),
    ).toBeVisible();
    await page
      .getByRole('button', { name: 'Propose from played participations', exact: true })
      .click();
    const livedPath = { ...w.path, being_id: being.id };
    expect(
      (
        await ok(
          w.gm.GET('/tenants/{tenant_id}/beings/{being_id}/lived-order', {
            params: { path: livedPath },
          }),
        )
      ).assertions,
    ).toEqual([]);
    await page.getByRole('button', { name: 'Save reviewed lived proposal', exact: true }).click();
    await expect(page.getByRole('alert')).toContainText('conflicts with recorded Event order');
    await page.getByRole('button', { name: 'Experienced later in proposal', exact: true }).click();
    await page.getByRole('button', { name: 'Save reviewed lived proposal', exact: true }).click();
    await expect(page.getByText('The launch → The wreck', { exact: true })).toBeVisible();
    const lived = await ok(
      w.gm.GET('/tenants/{tenant_id}/beings/{being_id}/lived-order', {
        params: { path: livedPath },
      }),
    );
    expect(lived.assertions[0].evidence).toBe('lived');
    expect(lived.assertions[0].is_shared).toBe(false);
    const play = await ok(
      w.gm.GET('/tenants/{tenant_id}/sessions/{session_id}/play', { params: { path } }),
    );
    expect(play.presentations.map((p) => p.event_id)).toEqual([events[1].id, events[0].id]);
  } finally {
    await page.context().close();
    await w.gm.DELETE('/tenants/{tenant_id}', { params: { path: w.path } });
  }
});

test('a save draws again only what it changed: drafts and open panels elsewhere stay', async ({
  browser,
}) => {
  test.setTimeout(90_000);
  const w = await world();
  const page = await signedIn(browser, w.subject);
  let release = () => {};
  try {
    const session = await ok(
      w.gm.POST('/tenants/{tenant_id}/sessions', {
        params: { path: w.path },
        body: { name: 'Saved session', campaign_id: w.campaign.id },
      }),
    );
    await page.goto(`/session/?tenant=${w.tenant.id}&id=${session.id}`);
    await expect(page.getByRole('heading', { name: 'Saved session', exact: true })).toBeVisible();

    // A draft in the roster panel (a player ticked, not saved) and a note being written.
    await page.getByText('GMs and players', { exact: true }).click();
    const players = page.getByRole('group', { name: 'Players and their Characters' });
    await players.getByRole('checkbox').first().check();
    await page.getByRole('button', { name: 'Add note', exact: true }).first().click();
    await page.getByLabel('Note title', { exact: true }).fill('Unsaved thought');

    // Save the Session's details, with the read of the Session after it held back.
    await page.getByText('Session details', { exact: true }).click();
    await page.getByLabel('Session title', { exact: true }).fill('New complete view');
    const hold = new Promise<void>((resolve) => {
      release = resolve;
    });
    let arrived = () => {};
    const reached = new Promise<void>((resolve) => {
      arrived = resolve;
    });
    await page.route(`**/sessions/${session.id}`, async (route) => {
      if (route.request().method() !== 'GET') return route.continue();
      arrived();
      await hold;
      return route.continue();
    });
    await page.getByRole('button', { name: 'Save Session details', exact: true }).click();
    await reached;
    // The old page stays until what replaces it has been read.
    await expect(page.getByRole('heading', { name: 'Saved session', exact: true })).toBeVisible();
    await expect(page.getByRole('heading', { name: 'New complete view', exact: true })).toHaveCount(
      0,
    );
    release();
    await expect(
      page.getByRole('heading', { name: 'New complete view', exact: true }),
    ).toBeVisible();

    // The other panels were left as they were: the draft note, the ticked player, the open panels.
    await expect(page.getByLabel('Note title', { exact: true })).toHaveValue('Unsaved thought');
    await expect(players.getByRole('checkbox').first()).toBeChecked();
    await expect(page.getByLabel('Session title', { exact: true })).toHaveValue(
      'New complete view',
    );
    await expect(page.getByRole('heading', { name: 'Recorded play', exact: true })).toBeVisible();
  } finally {
    release();
    await page.context().close();
    await w.gm.DELETE('/tenants/{tenant_id}', { params: { path: w.path } });
  }
});

// ADR 0322: every page meets the brand's rules for accessibility and for a phone. A Session with
// a shared Scene, a reference and a recorded participation gives each page something to draw.
async function seedPages(w: Awaited<ReturnType<typeof world>>) {
  const session = await ok(
    w.gm.POST('/tenants/{tenant_id}/sessions', {
      params: { path: w.path },
      body: { name: 'The harbour at night', campaign_id: w.campaign.id },
    }),
  );
  const path = { ...w.path, session_id: session.id };
  const scene = await ok(
    w.gm.POST('/tenants/{tenant_id}/scenes', {
      params: { path: w.path },
      body: { name: 'The drowned stair', is_public: true },
    }),
  );
  const initial = await w.gm.GET('/tenants/{tenant_id}/sessions/{session_id}', {
    params: { path },
  });
  await ok(
    w.gm.POST('/tenants/{tenant_id}/sessions/{session_id}/scenes', {
      params: { path, header: { 'if-match': initial.response.headers.get('etag') ?? '' } },
      body: { scene_entity_id: scene.id, is_shared: true },
    }),
  );
  const fact = await ok(
    w.gm.POST('/tenants/{tenant_id}/entities', {
      params: { path: w.path },
      body: { name: 'Guild ownership', kinds: ['fact'], parents: [], visibility: 'library' },
    }),
  );
  const refPath = {
    ...w.path,
    source_kind: 'scenes' as const,
    source_id: scene.id,
    kind: 'facts' as const,
    target_id: fact.id,
  };
  const refs = await w.gm.GET('/tenants/{tenant_id}/{source_kind}/{source_id}/references', {
    params: { path: refPath },
  });
  await ok(
    w.gm.PUT('/tenants/{tenant_id}/{source_kind}/{source_id}/references/{kind}/{target_id}', {
      params: { path: refPath, header: { 'if-match': refs.response.headers.get('etag') ?? '' } },
      body: { is_shared: false },
    }),
  );
  const event = await ok(
    w.gm.POST('/tenants/{tenant_id}/entities', {
      params: { path: w.path },
      body: { name: 'The launch', kinds: ['event'], parents: [], visibility: 'library' },
    }),
  );
  const being = await ok(
    w.gm.POST('/tenants/{tenant_id}/entities', {
      params: { path: w.path },
      body: { name: 'Mara', kinds: ['being'], parents: [] },
    }),
  );
  const eventPath = { ...w.path, event_id: event.id };
  const participants = await w.gm.GET('/tenants/{tenant_id}/events/{event_id}/participants', {
    params: { path: eventPath },
  });
  await ok(
    w.gm.PUT('/tenants/{tenant_id}/events/{event_id}/participants/{being_id}', {
      params: {
        path: { ...eventPath, being_id: being.id },
        header: { 'if-match': participants.response.headers.get('etag') ?? '' },
      },
    }),
  );
  const t = w.tenant.id;
  return [
    ['My Sessions', '/'],
    ['a Session', `/session/?tenant=${t}&id=${session.id}`],
    ['the Scenes', `/scenes/?tenant=${t}`],
    ['a Scene', `/scene/?tenant=${t}&id=${scene.id}`],
    ['lived order', `/lived/?tenant=${t}&being=${being.id}&session=${session.id}`],
  ] as const;
}

async function expectBrandRules(page: Page, where: string, phone: boolean) {
  await expect(page.locator('[data-page] h1')).toBeVisible();
  await expect(page.locator('[data-loading], [aria-busy="true"]')).toHaveCount(0);
  // What is behind a panel is part of the page.
  await page.evaluate(() => {
    for (const d of document.querySelectorAll('details')) d.open = true;
  });
  // Panels read what they hold when they are opened.
  await expect(page.locator('[data-loading], [aria-busy="true"]')).toHaveCount(0);
  const serious = (await new AxeBuilder({ page }).analyze()).violations
    .filter((v) => v.impact === 'serious' || v.impact === 'critical')
    // Known and outside this app: packages/lorenzoscript-editor's "1." toolbar button is named
    // "Numbered list", which does not contain its visible text. Everything else still counts.
    .filter(
      (v) =>
        !(
          v.id === 'label-content-name-mismatch' &&
          v.nodes.every((n) => n.target.join(' ').includes('Numbered list'))
        ),
    );
  // Soft, so one run names everything that is wrong on every page.
  const named = (n: (typeof serious)[number]['nodes'][number]) =>
    `${n.target.join(' ')} (${n.any[0]?.message ?? ''})`;
  expect
    .soft(
      serious.map((v) => `${v.id}: ${v.nodes.map(named).join(' | ')}`),
      `${where}: axe`,
    )
    .toEqual([]);
  expect
    .soft(
      await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth),
      `${where}: the page scrolls sideways`,
    )
    .toBe(true);
  if (!phone) return;
  const small = await page.evaluate(() => {
    const pressed =
      'header nav a, header button, header select, header summary, main button, main a.btn, main select, main summary, main input, main textarea';
    const found: string[] = [];
    for (const node of document.querySelectorAll(pressed)) {
      const shown = node.getBoundingClientRect();
      if (!shown.width || !shown.height || getComputedStyle(node).visibility === 'hidden') continue;
      // A checkbox is pressed through its label.
      const box =
        node instanceof HTMLInputElement && ['checkbox', 'radio'].includes(node.type)
          ? (node.closest('label') ?? node)
          : node;
      const height = box.getBoundingClientRect().height;
      if (height < 43.5)
        found.push(
          `${node.tagName.toLowerCase()}.${node.className} "${(node.textContent ?? '').trim().slice(0, 30)}" ${Math.round(height)}px`,
        );
    }
    return found;
  });
  expect.soft(small, `${where}: pressed controls under 44px`).toEqual([]);
}

for (const look of [
  { name: 'desktop light', theme: 'light', phone: false, viewport: { width: 1280, height: 1000 } },
  { name: 'desktop dark', theme: 'dark', phone: false, viewport: { width: 1280, height: 1000 } },
  { name: 'phone light', theme: 'light', phone: true, viewport: { width: 390, height: 844 } },
  { name: 'phone dark', theme: 'dark', phone: true, viewport: { width: 390, height: 844 } },
] as const) {
  test(`every page follows the brand rules: ${look.name}`, async ({ browser }, testInfo) => {
    test.setTimeout(120_000);
    const w = await world();
    const page = await signedIn(browser, w.subject, look);
    try {
      for (const [name, url] of await seedPages(w)) {
        await page.goto(url);
        if (name === 'a Session') {
          // The note form is the shared editor; it is part of this page too.
          await page.getByRole('button', { name: 'Add note', exact: true }).first().click();
          await expect(page.getByLabel('Note title', { exact: true })).toBeVisible();
        }
        await expectBrandRules(page, `${name}, ${look.name}`, look.phone);
        await page.screenshot({
          path: testInfo.outputPath(
            `${name.replaceAll(' ', '-')}-${look.name.replace(' ', '-')}.png`,
          ),
          fullPage: true,
        });
      }
    } finally {
      await page.context().close();
      await w.gm.DELETE('/tenants/{tenant_id}', { params: { path: w.path } });
    }
  });
}

test('the period picker chooses game time and a start, and writes nothing until Save', async ({
  browser,
}) => {
  test.setTimeout(90_000);
  const w = await world();
  const page = await signedIn(browser, w.subject);
  const writes: string[] = [];
  page.on('request', (request) => {
    if (request.method() !== 'GET' && /\/periods|\/dates|\/sessions\/[^/]+$/.test(request.url())) {
      writes.push(
        `${request.method()} ${new URL(request.url()).pathname.split('/').slice(3).join('/')}`,
      );
    }
  });
  try {
    await ok(
      w.gm.POST('/tenants/{tenant_id}/calendars', {
        params: { path: w.path },
        body: {
          name: 'Reckoning',
          is_public: false,
          definition: {
            format: 'lorenzo.calendar/1',
            segments: [
              { key: 'first', name: 'First', days: 27, kind: 'month', in_week: true },
              { key: 'festival', name: 'Festival', days: 2, kind: 'festival', in_week: false },
            ],
            week: {
              length: 7,
              reset: 'never',
              reference: { year: 0, segment: 'first', day: 1 },
              weekday: 0,
            },
            moons: [],
          },
        },
      }),
    );
    const session = await ok(
      w.gm.POST('/tenants/{tenant_id}/sessions', {
        params: { path: w.path },
        body: { name: 'The harbour at night', campaign_id: w.campaign.id },
      }),
    );
    await page.goto(`/session/?tenant=${w.tenant.id}&id=${session.id}`);

    // Game time covered: a range of days, chosen as days.
    await page.getByText('Choose periods', { exact: true }).click();
    const picker = page.locator('.period-picker');
    await expect(picker.getByRole('spinbutton', { name: 'Year' })).toHaveValue('0');
    await picker.getByRole('button', { name: 'Choose a range of days' }).click();
    await picker.getByRole('button', { name: '16 First 0', exact: true }).click();
    await picker.getByRole('button', { name: '18 First 0', exact: true }).click();
    await expect(picker).toContainText('3 days in First 0');
    await picker.scrollIntoViewIfNeeded();
    await picker.screenshot({ path: test.info().outputPath('period-picker.png') });
    await expectBrandRules(page, 'a Session with the period picker open', false);
    expect(writes).toEqual([]);

    await page.getByRole('button', { name: 'Save game time', exact: true }).click();
    await expect(page.getByRole('heading', { name: 'Game time covered' })).toBeVisible();
    const savedDates = () =>
      ok(
        w.gm.GET('/tenants/{tenant_id}/entities/{entity_id}/dates', {
          params: { path: { ...w.path, entity_id: session.id } },
        }),
      );
    await expect
      .poll(async () => (await savedDates()).map((period) => period.day).sort())
      .toEqual([16, 17, 18]);
    expect(writes.some((write) => write.endsWith('/periods/batch'))).toBe(true);
    const saved = await savedDates();
    // The page draws itself again after a save: the saved game time is listed (the chips of the
    // picker are another list), and the panel that was open stays open.
    await expect(page.locator('ul.row li').filter({ hasText: '17 First 0' })).toBeVisible();
    await expect(page.locator('.period-picker')).toHaveCount(1);

    // The starting period: one choice, and a day that already exists is marked saved.
    // Every panel was opened for the accessibility check and stayed open through the redraw; one
    // that is not open is opened now.
    const detailsPanel = page
      .locator('details.panel')
      .filter({ hasText: 'Session details' })
      .first();
    if (!(await detailsPanel.evaluate((d) => (d as HTMLDetailsElement).open))) {
      await page.getByText('Session details', { exact: true }).click();
    }
    await expect(detailsPanel).toHaveAttribute('open', '', { timeout: 5000 });
    const start = page.getByRole('group', { name: 'In-world starting period' });
    await expect(start).toBeVisible({ timeout: 5000 });
    await start.getByRole('button', { name: 'Choose', exact: true }).click({ timeout: 5000 });
    await expect(start.locator('.period-picker')).toBeVisible({ timeout: 5000 });
    await start
      .getByRole('button', { name: '17 First 0, saved', exact: true })
      .click({ timeout: 5000 });
    await page.getByRole('button', { name: 'Save Session details', exact: true }).click();
    await expect
      .poll(
        async () =>
          (
            await ok(
              w.gm.GET('/tenants/{tenant_id}/sessions/{session_id}', {
                params: { path: { ...w.path, session_id: session.id } },
              }),
            )
          ).start_period_id,
      )
      .toBe(saved.find((period) => period.day === 17)?.entity_id);
  } finally {
    await page.context().close();
    await w.gm.DELETE('/tenants/{tenant_id}', { params: { path: w.path } });
  }
});

test('resting on a Session link reads that Session ahead, and opening it asks again for nothing', async ({
  browser,
}) => {
  const w = await world();
  const page = await signedIn(browser, w.subject);
  try {
    const session = await ok(
      w.gm.POST('/tenants/{tenant_id}/sessions', {
        params: { path: w.path },
        body: { name: 'The harbour at night', campaign_id: w.campaign.id },
      }),
    );
    const reads: string[] = [];
    page.on('request', (request) => {
      if (request.method() === 'GET' && request.url().endsWith(`/sessions/${session.id}`)) {
        reads.push(request.url());
      }
    });
    await page.goto('/');
    const open = page.getByRole('link', { name: 'The harbour at night', exact: true });
    await expect(open).toBeVisible();
    const ahead = page.waitForResponse((response) =>
      response.url().endsWith(`/sessions/${session.id}`),
    );
    await open.hover();
    await (await ahead).finished();
    expect(reads).toHaveLength(1);
    await open.click();
    await expect(
      page.getByRole('heading', { name: 'The harbour at night', level: 1 }),
    ).toBeVisible();
    // The page found it held (the reads are held for a few seconds under the viewer's scope).
    expect(reads).toHaveLength(1);
  } finally {
    await page.context().close();
    await w.gm.DELETE('/tenants/{tenant_id}', { params: { path: w.path } });
  }
});

test('moving and sharing a Scene draw only the cards that changed, and removing one draws the outline', async ({
  browser,
}) => {
  test.setTimeout(90_000);
  const w = await world();
  const page = await signedIn(browser, w.subject);
  try {
    const session = await ok(
      w.gm.POST('/tenants/{tenant_id}/sessions', {
        params: { path: w.path },
        body: { name: 'The harbour at night', campaign_id: w.campaign.id },
      }),
    );
    const path = { ...w.path, session_id: session.id };
    for (const name of ['Scene A', 'Scene B', 'Scene C']) {
      const scene = await ok(
        w.gm.POST('/tenants/{tenant_id}/scenes', {
          params: { path: w.path },
          body: { name, is_public: true },
        }),
      );
      const current = await w.gm.GET('/tenants/{tenant_id}/sessions/{session_id}', {
        params: { path },
      });
      await ok(
        w.gm.POST('/tenants/{tenant_id}/sessions/{session_id}/scenes', {
          params: { path, header: { 'if-match': current.response.headers.get('etag') ?? '' } },
          body: { scene_entity_id: scene.id, is_shared: true },
        }),
      );
    }
    await page.goto(`/session/?tenant=${w.tenant.id}&id=${session.id}`);
    const cards = page.locator('[data-region^="scene:"]');
    await expect(cards).toHaveCount(3);
    await expect(cards.locator('h3')).toHaveText(['Scene A', 'Scene B', 'Scene C']);

    // A note being written in the third card.
    await cards.nth(2).getByRole('button', { name: 'Add note', exact: true }).click();
    await cards.nth(2).getByLabel('Note title', { exact: true }).fill('Draft in the third');

    // Moving the first Scene down draws the two that changed place; the third is untouched.
    await cards.nth(0).getByRole('button', { name: 'Move down', exact: true }).click();
    await expect(cards.locator('h3')).toHaveText(['Scene B', 'Scene A', 'Scene C']);
    await expect(cards.nth(0).locator('.chip').first()).toHaveText('1');
    await expect(cards.nth(1).locator('.chip').first()).toHaveText('2');
    await expect(cards.nth(2).getByLabel('Note title', { exact: true })).toHaveValue(
      'Draft in the third',
    );

    // Sharing changes only the card it is on.
    await cards.nth(1).getByRole('button', { name: 'Make preparation private' }).click();
    await expect(cards.nth(1)).toContainText('GM preparation');
    await expect(cards.nth(0)).toContainText('Shared with Session participants');
    await expect(cards.nth(2).getByLabel('Note title', { exact: true })).toHaveValue(
      'Draft in the third',
    );

    // Removing one draws the outline again, and the others are numbered again.
    page.once('dialog', (dialog) => void dialog.accept());
    await cards.nth(0).getByRole('button', { name: 'Remove Scene appearance' }).click();
    await expect(cards).toHaveCount(2);
    await expect(cards.locator('h3')).toHaveText(['Scene A', 'Scene C']);
    await expect(page.getByRole('heading', { name: 'Scenes', exact: true })).toBeVisible();
  } finally {
    await page.context().close();
    await w.gm.DELETE('/tenants/{tenant_id}', { params: { path: w.path } });
  }
});
