import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { afterAll, afterEach, beforeAll, describe, expect, it } from "vitest";
import { createLorenzoApiClient } from "../src/lorenzo-client.js";

const BASE_URL = "http://lorenzo-api.test";
const TENANT_ID = "3fa85f64-5717-4562-b3fc-2c963f66afa6";
const CHARACTER_ID = "11111111-1111-1111-1111-111111111111";

const server = setupServer();

beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

describe("getItemInstancesByContainer", () => {
  it("passes container_id and recursive=false, returning the page's items", async () => {
    let receivedUrl: URL | undefined;
    server.use(
      http.get(`${BASE_URL}/tenants/${TENANT_ID}/item-instances`, ({ request }) => {
        receivedUrl = new URL(request.url);
        return HttpResponse.json({
          items: [
            { entity_id: "item-1", title: "Torch", quantity: 5, owner_entity_id: null },
            { entity_id: "item-2", title: "Sword", quantity: null, owner_entity_id: null },
          ],
          total: 2,
          page: 1,
          size: 50,
          pages: 1,
        });
      }),
    );

    const client = createLorenzoApiClient(BASE_URL);
    const items = await client.getItemInstancesByContainer(TENANT_ID, "container-1", "test-token");

    expect(receivedUrl?.searchParams.get("container_id")).toBe("container-1");
    expect(receivedUrl?.searchParams.get("recursive")).toBe("false");
    expect(items).toHaveLength(2);
    expect(items[0]?.title).toBe("Torch");
  });
});

describe("getItemInstancesOwnedBy", () => {
  it("sends a bearer token and returns the parsed response", async () => {
    let receivedAuth: string | null = null;
    server.use(
      http.get(
        `${BASE_URL}/tenants/${TENANT_ID}/item-instances/owned-by/${CHARACTER_ID}`,
        ({ request }) => {
          receivedAuth = request.headers.get("authorization");
          return HttpResponse.json({
            groups: [
              {
                container: { id: "22222222-2222-2222-2222-222222222222", name: "Backpack" },
                item_instances: [],
              },
            ],
          });
        },
      ),
    );

    const client = createLorenzoApiClient(BASE_URL);
    const result = await client.getItemInstancesOwnedBy(TENANT_ID, CHARACTER_ID, "test-token");

    expect(receivedAuth).toBe("Bearer test-token");
    expect(result.groups).toHaveLength(1);
    expect(result.groups[0]?.container?.name).toBe("Backpack");
  });

  it("throws a LorenzoApiError carrying the problem detail on a 404", async () => {
    server.use(
      http.get(`${BASE_URL}/tenants/${TENANT_ID}/item-instances/owned-by/${CHARACTER_ID}`, () =>
        HttpResponse.json(
          {
            type: "item-instance-not-found",
            title: "Item instance not found",
            detail: "No item instance owned by that character",
          },
          { status: 404, headers: { "content-type": "application/problem+json" } },
        ),
      ),
    );

    const client = createLorenzoApiClient(BASE_URL);
    await expect(
      client.getItemInstancesOwnedBy(TENANT_ID, CHARACTER_ID, "test-token"),
    ).rejects.toMatchObject({
      status: 404,
      problemType: "item-instance-not-found",
      message: "No item instance owned by that character",
    });
  });
});

describe("getControlledCharacters", () => {
  it("returns only characters belonging to the requested tenant", async () => {
    server.use(
      http.get(`${BASE_URL}/me`, () =>
        HttpResponse.json({
          id: "user-1",
          authgear_subject_id: "sub-1",
          memberships: [],
          campaign_gm_grants: [],
          players: [
            {
              id: "player-1",
              tenant_id: TENANT_ID,
              campaign_id: "campaign-1",
              characters: [{ entity_id: CHARACTER_ID, name: "Frodo", is_pc: true }],
            },
            {
              id: "player-2",
              tenant_id: "some-other-tenant",
              campaign_id: "campaign-2",
              characters: [{ entity_id: "other-character", name: "Sam", is_pc: true }],
            },
          ],
        }),
      ),
    );

    const client = createLorenzoApiClient(BASE_URL);
    const characters = await client.getControlledCharacters(TENANT_ID, "test-token");

    expect(characters).toEqual([{ entityId: CHARACTER_ID, name: "Frodo" }]);
  });

  it("returns an empty list when the caller has no players in this tenant", async () => {
    server.use(
      http.get(`${BASE_URL}/me`, () =>
        HttpResponse.json({
          id: "user-1",
          authgear_subject_id: "sub-1",
          memberships: [],
          campaign_gm_grants: [],
          players: [],
        }),
      ),
    );

    const client = createLorenzoApiClient(BASE_URL);
    const characters = await client.getControlledCharacters(TENANT_ID, "test-token");

    expect(characters).toEqual([]);
  });
});

describe("getMyPlayers", () => {
  it("keeps campaignId, unlike getControlledCharacters", async () => {
    server.use(
      http.get(`${BASE_URL}/me`, () =>
        HttpResponse.json({
          id: "user-1",
          authgear_subject_id: "sub-1",
          memberships: [],
          campaign_gm_grants: [],
          players: [
            {
              id: "player-1",
              tenant_id: TENANT_ID,
              campaign_id: "campaign-1",
              characters: [{ entity_id: CHARACTER_ID, name: "Frodo", is_pc: true }],
            },
          ],
        }),
      ),
    );

    const client = createLorenzoApiClient(BASE_URL);
    const players = await client.getMyPlayers(TENANT_ID, "test-token");

    expect(players).toEqual([
      { campaignId: "campaign-1", characters: [{ entityId: CHARACTER_ID, name: "Frodo" }] },
    ]);
  });
});

describe("isCampaignGm", () => {
  it("is true when /me has at least one campaign_gm_grants entry", async () => {
    server.use(
      http.get(`${BASE_URL}/me`, () =>
        HttpResponse.json({
          id: "user-1",
          authgear_subject_id: "sub-1",
          memberships: [],
          players: [],
          campaign_gm_grants: [
            {
              id: "campaign-1",
              slug: "ashen-crown",
              name: "The Ashen Crown",
              game_system: "5e",
              secret: false,
            },
          ],
        }),
      ),
    );

    const client = createLorenzoApiClient(BASE_URL);
    await expect(client.isCampaignGm("test-token")).resolves.toBe(true);
  });

  it("is false when campaign_gm_grants is empty", async () => {
    server.use(
      http.get(`${BASE_URL}/me`, () =>
        HttpResponse.json({
          id: "user-1",
          authgear_subject_id: "sub-1",
          memberships: [],
          players: [],
          campaign_gm_grants: [],
        }),
      ),
    );

    const client = createLorenzoApiClient(BASE_URL);
    await expect(client.isCampaignGm("test-token")).resolves.toBe(false);
  });
});

describe("getItemInstance", () => {
  it("fetches one instance by id", async () => {
    server.use(
      http.get(`${BASE_URL}/tenants/${TENANT_ID}/item-instances/item-1`, () =>
        HttpResponse.json({
          entity_id: "item-1",
          title: "Torch",
          quantity: 5,
          owner_entity_id: CHARACTER_ID,
        }),
      ),
    );

    const client = createLorenzoApiClient(BASE_URL);
    const { data } = await client.getItemInstance(TENANT_ID, "item-1", "test-token");

    expect(data.title).toBe("Torch");
    expect(data.quantity).toBe(5);
  });

  it("captures the ETag response header", async () => {
    server.use(
      http.get(`${BASE_URL}/tenants/${TENANT_ID}/item-instances/item-1`, () =>
        HttpResponse.json(
          { entity_id: "item-1", title: "Torch", quantity: 5, owner_entity_id: null },
          { headers: { ETag: 'W/"2026-01-01T00:00:00Z"' } },
        ),
      ),
    );

    const client = createLorenzoApiClient(BASE_URL);
    const { etag } = await client.getItemInstance(TENANT_ID, "item-1", "test-token");

    expect(etag).toBe('W/"2026-01-01T00:00:00Z"');
  });

  it("returns a null etag when the server doesn't send one", async () => {
    server.use(
      http.get(`${BASE_URL}/tenants/${TENANT_ID}/item-instances/item-1`, () =>
        HttpResponse.json({
          entity_id: "item-1",
          title: "Torch",
          quantity: 5,
          owner_entity_id: null,
        }),
      ),
    );

    const client = createLorenzoApiClient(BASE_URL);
    const { etag } = await client.getItemInstance(TENANT_ID, "item-1", "test-token");

    expect(etag).toBeNull();
  });
});

describe("splitItemInstance", () => {
  it("posts the requested quantity and returns the new instance", async () => {
    let receivedBody: unknown;
    server.use(
      http.post(
        `${BASE_URL}/tenants/${TENANT_ID}/item-instances/item-1/split`,
        async ({ request }) => {
          receivedBody = await request.json();
          return HttpResponse.json(
            { entity_id: "item-2", title: "Torch", quantity: 3, owner_entity_id: CHARACTER_ID },
            { status: 201 },
          );
        },
      ),
    );

    const client = createLorenzoApiClient(BASE_URL);
    const { data } = await client.splitItemInstance(TENANT_ID, "item-1", 3, "test-token");

    expect(receivedBody).toEqual({ quantity: 3 });
    expect(data.entity_id).toBe("item-2");
    expect(data.quantity).toBe(3);
  });

  it("sends the given etag as If-Match", async () => {
    let receivedIfMatch: string | null = null;
    server.use(
      http.post(`${BASE_URL}/tenants/${TENANT_ID}/item-instances/item-1/split`, ({ request }) => {
        receivedIfMatch = request.headers.get("if-match");
        return HttpResponse.json(
          { entity_id: "item-2", title: "Torch", quantity: 3, owner_entity_id: CHARACTER_ID },
          { status: 201 },
        );
      }),
    );

    const client = createLorenzoApiClient(BASE_URL);
    await client.splitItemInstance(TENANT_ID, "item-1", 3, "test-token", 'W/"stale"');

    expect(receivedIfMatch).toBe('W/"stale"');
  });

  it("throws a 412 LorenzoApiError when If-Match is stale", async () => {
    server.use(
      http.post(`${BASE_URL}/tenants/${TENANT_ID}/item-instances/item-1/split`, () =>
        HttpResponse.json(
          { type: "precondition-failed", title: "Precondition Failed", detail: "stale etag" },
          { status: 412, headers: { "content-type": "application/problem+json" } },
        ),
      ),
    );

    const client = createLorenzoApiClient(BASE_URL);
    await expect(
      client.splitItemInstance(TENANT_ID, "item-1", 3, "test-token", 'W/"stale"'),
    ).rejects.toMatchObject({ status: 412 });
  });
});

describe("setItemInstanceOwner", () => {
  it("puts the new owner and returns the updated instance", async () => {
    let receivedBody: unknown;
    server.use(
      http.put(
        `${BASE_URL}/tenants/${TENANT_ID}/item-instances/item-1/owner`,
        async ({ request }) => {
          receivedBody = await request.json();
          return HttpResponse.json({
            entity_id: "item-1",
            title: "Torch",
            owner_entity_id: "char-2",
          });
        },
      ),
    );

    const client = createLorenzoApiClient(BASE_URL);
    const result = await client.setItemInstanceOwner(TENANT_ID, "item-1", "char-2", "test-token");

    expect(receivedBody).toEqual({ owner_character_id: "char-2" });
    expect(result.owner_entity_id).toBe("char-2");
  });

  it("sends the given etag as If-Match", async () => {
    let receivedIfMatch: string | null = null;
    server.use(
      http.put(`${BASE_URL}/tenants/${TENANT_ID}/item-instances/item-1/owner`, ({ request }) => {
        receivedIfMatch = request.headers.get("if-match");
        return HttpResponse.json({
          entity_id: "item-1",
          title: "Torch",
          owner_entity_id: "char-2",
        });
      }),
    );

    const client = createLorenzoApiClient(BASE_URL);
    await client.setItemInstanceOwner(TENANT_ID, "item-1", "char-2", "test-token", 'W/"fresh"');

    expect(receivedIfMatch).toBe('W/"fresh"');
  });

  it("omits If-Match entirely when no etag is given", async () => {
    let receivedIfMatch: string | null = null;
    server.use(
      http.put(`${BASE_URL}/tenants/${TENANT_ID}/item-instances/item-1/owner`, ({ request }) => {
        receivedIfMatch = request.headers.get("if-match");
        return HttpResponse.json({
          entity_id: "item-1",
          title: "Torch",
          owner_entity_id: "char-2",
        });
      }),
    );

    const client = createLorenzoApiClient(BASE_URL);
    await client.setItemInstanceOwner(TENANT_ID, "item-1", "char-2", "test-token");

    expect(receivedIfMatch).toBeNull();
  });
});

describe("getCampaignPlayers", () => {
  it("flattens every player's characters into one list", async () => {
    server.use(
      http.get(`${BASE_URL}/tenants/${TENANT_ID}/campaigns/campaign-1/players`, () =>
        HttpResponse.json({
          items: [
            {
              id: "p1",
              user_id: "u1",
              characters: [{ entity_id: "c1", name: "Frodo", is_pc: true }],
            },
            {
              id: "p2",
              user_id: "u2",
              characters: [{ entity_id: "c2", name: "Sam", is_pc: true }],
            },
          ],
          total: 2,
          page: 1,
          size: 50,
          pages: 1,
        }),
      ),
    );

    const client = createLorenzoApiClient(BASE_URL);
    const characters = await client.getCampaignPlayers(TENANT_ID, "campaign-1", "test-token");

    expect(characters).toEqual([
      { entityId: "c1", name: "Frodo" },
      { entityId: "c2", name: "Sam" },
    ]);
  });
});

describe("getCharacterName", () => {
  it("returns just the name", async () => {
    server.use(
      http.get(`${BASE_URL}/tenants/${TENANT_ID}/characters/${CHARACTER_ID}`, () =>
        HttpResponse.json({
          entity_id: CHARACTER_ID,
          name: "Frodo",
          is_pc: true,
          owner_player_id: null,
          players: [],
          created_by: null,
          updated_by: null,
        }),
      ),
    );

    const client = createLorenzoApiClient(BASE_URL);
    const name = await client.getCharacterName(TENANT_ID, CHARACTER_ID, "test-token");

    expect(name).toBe("Frodo");
  });
});
