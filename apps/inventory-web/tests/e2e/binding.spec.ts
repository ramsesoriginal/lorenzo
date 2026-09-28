// Things bound to their owner, and a GM taking them off anyway (ADR 0129).
import type { Page } from '@playwright/test';
import { ok } from './support/api.ts';
import { expect, test } from './support/fixtures.ts';
import { packed } from './support/scenes.ts';
import type { Person, World } from './support/world.ts';

async function ashfangsBoard(as: (who: Person) => Promise<Page>, world: World, who: Person) {
  const page = await as(who);
  if (who === world.pia) {
    await page.goto(`/board/?tenant=${world.tenantId}&character=${world.pia.character.entity_id}`);
    return page;
  }
  // A GM browses to her character.
  await page.goto(`/board/?tenant=${world.tenantId}`);
  await page.getByRole('tab', { name: 'Browse a being' }).click();
  await page.getByLabel('Search beings').filter({ visible: true }).fill('Ashfang');
  await page.getByRole('option').getByRole('button', { name: 'Ashfang' }).click();
  return page;
}

/** Ashfang wears a cursed Ring, and has a Backpack. */
async function cursed(world: World) {
  await packed(world, world.pia);
  const ring = await world.item('Ring', { binding: 'on_equip' });
  return world.instance(ring, { owner: world.pia, container: world.pia.character.entity_id });
}

const ring = (page: Page) =>
  page.getByRole('region', { name: 'Equipped' }).getByRole('button', { name: 'Ring Bound' });

async function moveRingIntoBackpack(page: Page) {
  await ring(page).click();
  await page.getByRole('button', { name: 'Move to…' }).click();
  await page.getByRole('dialog').getByRole('button', { name: 'Backpack', exact: true }).click();
}

/** Answers every question with `answers` in turn, and keeps what was asked. */
function answering(page: Page, answers: boolean[]): string[] {
  const asked: string[] = [];
  page.on('dialog', (dialog) => {
    asked.push(dialog.message());
    void (answers[asked.length - 1] ? dialog.accept() : dialog.dismiss());
  });
  return asked;
}

test("a bound thing is marked, and a player can't take it off or give it away", async ({
  world,
  as,
}) => {
  await cursed(world);
  const page = await ashfangsBoard(as, world, world.pia);

  await ring(page).click();
  await expect(page.getByText('Bound to its owner')).toBeVisible();
  await expect(page.getByRole('button', { name: 'Give to…' })).toBeDisabled();
  await page.getByRole('button', { name: 'Close' }).click();

  await moveRingIntoBackpack(page);

  await expect(
    page.getByText("Ring is bound to Ashfang (binds on equip), so it can't be taken off Ashfang."),
  ).toBeVisible();
  // Still on her: what's equipped is in no container but its owner (ADR 0123).
  expect(await world.ownedBy(world.pia.character.entity_id)).toContain('(none): Ring');
});

test('a GM takes it off anyway, and lifts the curse', async ({ world, as }) => {
  const ringId = await cursed(world);
  const page = await ashfangsBoard(as, world, world.gm);
  const asked = answering(page, [true, true]);

  await moveRingIntoBackpack(page);

  await expect.poll(() => world.ownedBy(world.pia.character.entity_id)).toContain('Backpack: Ring');
  expect(asked).toEqual([
    "Ring is bound to Ashfang (binds on equip), so it can't be taken off Ashfang. Move anyway?",
    "Lift its binding too, so it won't bind again?",
  ]);
  // Worn again, it doesn't bind.
  const path = { tenant_id: world.tenantId, entity_id: ringId };
  const worn = await ok(
    world.pia.api.PUT('/tenants/{tenant_id}/item-instances/{entity_id}/container', {
      params: { path },
      body: {
        container_entity_id: world.pia.character.entity_id,
        override: false,
        lift_binding: false,
        merge_identical: false,
      },
    }),
  );
  expect(worn.bound).toBe(false);
});

test('a GM gives it away anyway, without lifting it', async ({ world, as }) => {
  await cursed(world);
  const page = await ashfangsBoard(as, world, world.gm);
  const asked = answering(page, [true, false]);

  await ring(page).click();
  await page.getByRole('button', { name: 'Give to…' }).click();
  const picker = page.getByRole('dialog');
  await picker.getByLabel('Search beings').fill('Brisk');
  await picker.getByRole('option').getByRole('button', { name: 'Brisk' }).click();

  await expect(page.getByText('Given to Brisk.')).toBeVisible();
  expect(asked[0]).toBe(
    "Ring is bound to Ashfang (binds on equip), so it can't change hands. Give anyway?",
  );
  expect(await world.carried(world.oskar)).toEqual(['Ashfang: Ring']);
});
