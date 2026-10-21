import { randomUUID } from 'node:crypto';
import { type Browser, expect, test } from '@playwright/test';
import { apiAs, ok, refreshTokenFor } from './support/api.ts';
import { REFRESH_TOKEN_KEY, SITE_URL } from './support/env.ts';

async function signedIn(browser: Browser, subject: string) {
  const token = await refreshTokenFor(subject);
  const context = await browser.newContext({
    storageState: {
      cookies: [],
      origins: [{ origin: SITE_URL, localStorage: [{ name: REFRESH_TOKEN_KEY, value: token }] }],
    },
  });
  return context.newPage();
}
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
    await gm.getByRole('button', { name: 'Create session', exact: true }).click();
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
    await gm.getByLabel('New scene title').fill('Exploring the wreck');
    await gm.getByLabel('Make the reusable scene visible in this library').check();
    await gm.getByLabel('Share this scene appearance with session participants').check();
    await gm.getByRole('button', { name: 'Add scene', exact: true }).click();
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
    await page.getByRole('button', { name: 'Save session details', exact: true }).click();
    await expect(page.getByText(/Your draft is still here/)).toBeVisible();
    await expect(page.getByLabel('Session title', { exact: true })).toHaveValue('My draft');
    await page.getByRole('button', { name: 'Review saved session', exact: true }).click();
    await expect(page.getByText(/Saved session: Other saved edit/)).toBeVisible();
    await expect(page.getByLabel('Session title', { exact: true })).toHaveValue('My draft');
    await page.getByRole('button', { name: 'Save session details', exact: true }).click();
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
    await page.getByRole('button', { name: 'Create scene', exact: true }).click();
    await expect(
      page.getByRole('heading', { name: 'At the lighthouse', exact: true }),
    ).toBeVisible();
    await expect(page).toHaveURL(/slug=lighthouse-scene/);
    await page.getByLabel('Reference to add').selectOption({ label: 'Guild ownership · facts' });
    await page.getByRole('button', { name: 'Add reference', exact: true }).click();
    await expect(
      page.getByText('Guild ownership · facts · Private relationship', { exact: true }),
    ).toBeVisible();
    await page.getByRole('button', { name: 'Share relationship', exact: true }).click();
    await expect(
      page.getByText('Guild ownership · facts · Shared relationship', { exact: true }),
    ).toBeVisible();
    await page.getByText('Scene details', { exact: true }).click();
    await page.getByLabel('Visible in this library').check();
    await page.getByRole('button', { name: 'Save scene', exact: true }).click();
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
    await expect(
      page.getByText('Guild ownership · facts · Shared relationship', { exact: true }),
    ).toHaveCount(0);
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
    await page.getByText('Review and record played scenes', { exact: true }).click();
    await page
      .getByRole('button', { name: 'Propose played order from preparation', exact: true })
      .click();
    await expect(
      page.getByText('Proposal only. Review the scene statuses and order, then save explicitly.', {
        exact: true,
      }),
    ).toBeVisible();
    let read = await ok(
      w.gm.GET('/tenants/{tenant_id}/sessions/{session_id}/play', { params: { path } }),
    );
    expect(read.played_appearance_ids).toEqual([]);
    await page.getByRole('button', { name: 'Save played scenes', exact: true }).click();
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
    await page.getByText('Edit order of sessions I manage', { exact: true }).click();
    await page.getByRole('button', { name: 'Place session at end', exact: true }).click();
    await page.getByRole('button', { name: 'Save session order', exact: true }).click();
    await expect(
      page.getByText('Unplaced sessions available to you: none', { exact: true }),
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

test('a refresh replaces the whole Session view only after its permitted context is ready', async ({
  browser,
}) => {
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
    await page.getByText('Session details', { exact: true }).click();
    await page.getByLabel('Session title', { exact: true }).fill('New complete view');
    const hold = new Promise<void>((resolve) => {
      release = resolve;
    });
    let arrived = () => {};
    const reached = new Promise<void>((resolve) => {
      arrived = resolve;
    });
    await page.route(`**/sessions/${session.id}/references`, async (route) => {
      arrived();
      await hold;
      await route.continue();
    });
    await page.getByRole('button', { name: 'Save session details', exact: true }).click();
    await reached;
    await expect(page.getByRole('heading', { name: 'Saved session', exact: true })).toBeVisible();
    await expect(page.getByRole('heading', { name: 'New complete view', exact: true })).toHaveCount(
      0,
    );
    release();
    await expect(
      page.getByRole('heading', { name: 'New complete view', exact: true }),
    ).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Recorded play', exact: true })).toBeVisible();
  } finally {
    release();
    await page.context().close();
    await w.gm.DELETE('/tenants/{tenant_id}', { params: { path: w.path } });
  }
});
