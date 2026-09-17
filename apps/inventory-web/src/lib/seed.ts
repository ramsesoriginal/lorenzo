// Debug-only tool: seeds one demo character with a small nested-container
// inventory, so the board (Slice 4+) has real data to render against
// without needing the GM tooling this app defers to a later phase. Not
// linked from anywhere but /debug - see docs/domain/client-views.md.
import { apiFetch, apiPost } from './api';

interface Me {
  id: string;
  players: { id: string; tenant_id: string; campaign_id: string }[];
}

async function ensurePlayerId(tenantId: string, log: (message: string) => void): Promise<string> {
  const me = await apiFetch<Me>('/me');
  const existing = me.players.find((p) => p.tenant_id === tenantId);
  if (existing) {
    log(`Reusing your existing player membership (${existing.id}).`);
    return existing.id;
  }

  const campaigns = await apiFetch<{ items: { id: string }[] }>(`/tenants/${tenantId}/campaigns`);
  let campaignId = campaigns.items[0]?.id;
  if (campaignId) {
    log(`Reusing existing campaign ${campaignId}.`);
  } else {
    log('No campaign in this tenant yet - creating one.');
    const campaign = await apiPost<{ id: string }>(`/tenants/${tenantId}/campaigns`, {
      name: 'Debug Campaign',
      game_system: 'debug',
      slug: `debug-campaign-${Date.now()}`,
      description: 'Created by the inventory-web seed tool.',
    });
    campaignId = campaign.id;
  }

  log(`Joining campaign ${campaignId} as a player.`);
  const player = await apiPost<{ id: string }>(
    `/tenants/${tenantId}/campaigns/${campaignId}/players`,
    {
      user_id: me.id,
    },
  );
  return player.id;
}

async function createItem(tenantId: string, name: string): Promise<string> {
  const item = await apiPost<{ entity_id: string }>(`/tenants/${tenantId}/items`, { name });
  return item.entity_id;
}

async function createInstance(
  tenantId: string,
  prototypeId: string,
  ownerCharacterId: string,
  containerEntityId: string | null,
  name?: string,
): Promise<string> {
  const instance = await apiPost<{ entity_id: string }>(`/tenants/${tenantId}/item-instances`, {
    prototype_id: prototypeId,
    owner_character_id: ownerCharacterId,
    container_entity_id: containerEntityId,
    name,
  });
  return instance.entity_id;
}

// Quantity isn't settable at creation (ADR 0041/0044) - a stack of N is
// built by creating N separate qty-1 instances and merging N-1 of them
// into the first.
async function createStack(
  tenantId: string,
  prototypeId: string,
  ownerCharacterId: string,
  containerEntityId: string,
  quantity: number,
): Promise<string> {
  const first = await createInstance(tenantId, prototypeId, ownerCharacterId, containerEntityId);
  for (let i = 1; i < quantity; i++) {
    const extra = await createInstance(tenantId, prototypeId, ownerCharacterId, containerEntityId);
    await apiPost(`/tenants/${tenantId}/item-instances/${extra}/merge`, { into_entity_id: first });
  }
  return first;
}

export async function seedDemoCharacter(
  tenantId: string,
  log: (message: string) => void,
): Promise<void> {
  log('Resolving your player membership…');
  const playerId = await ensurePlayerId(tenantId, log);

  log('Creating character "Siul min Pal-Vàz"…');
  const character = await apiPost<{ entity_id: string }>(`/tenants/${tenantId}/characters`, {
    name: 'Siul min Pal-Vàz',
    owner_player_id: playerId,
  });
  const characterId = character.entity_id;

  log('Creating the item catalog…');
  const [
    equippedProto,
    beltPouchProto,
    slingBagProto,
    treasureChestProto,
    goldCoinProto,
    bookProto,
    sapphireProto,
  ] = await Promise.all(
    ['Equipped', 'Belt Pouch', 'Sling Bag', 'Treasure Chest', 'Gold Coin', 'Book', 'Sapphire'].map(
      (name) => createItem(tenantId, name),
    ),
  );

  log('Creating "equipped" and "treasure chest"…');
  const equippedId = await createInstance(tenantId, equippedProto, characterId, null, 'equipped');
  const treasureChestId = await createInstance(
    tenantId,
    treasureChestProto,
    characterId,
    null,
    'treasure chest',
  );

  log('Creating "belt pouch" and "sling bag" inside "equipped"…');
  const beltPouchId = await createInstance(
    tenantId,
    beltPouchProto,
    characterId,
    equippedId,
    'belt pouch',
  );
  const slingBagId = await createInstance(
    tenantId,
    slingBagProto,
    characterId,
    equippedId,
    'sling bag',
  );

  log('Filling the containers…');
  await createStack(tenantId, goldCoinProto, characterId, beltPouchId, 5);
  await createInstance(tenantId, bookProto, characterId, slingBagId, 'a book');
  await createInstance(tenantId, sapphireProto, characterId, treasureChestId, 'a sapphire');
  await createStack(tenantId, goldCoinProto, characterId, treasureChestId, 10);

  log('Done.');
}
