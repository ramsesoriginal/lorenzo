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

describe("getMyItemInstances", () => {
  it("flattens every controlled character's owned items into one list", async () => {
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
              characters: [
                { entity_id: "char-1", name: "Frodo", is_pc: true },
                { entity_id: "char-2", name: "Sam", is_pc: true },
              ],
            },
          ],
        }),
      ),
      http.get(`${BASE_URL}/tenants/${TENANT_ID}/item-instances/owned-by/char-1`, () =>
        HttpResponse.json({
          groups: [
            {
              container: null,
              item_instances: [{ entity_id: "item-1", title: "Torch", quantity: 5 }],
            },
          ],
        }),
      ),
      http.get(`${BASE_URL}/tenants/${TENANT_ID}/item-instances/owned-by/char-2`, () =>
        HttpResponse.json({
          groups: [
            {
              container: null,
              item_instances: [{ entity_id: "item-2", title: "Rope", quantity: null }],
            },
          ],
        }),
      ),
    );

    const client = createLorenzoApiClient(BASE_URL);
    const items = await client.getMyItemInstances(TENANT_ID, "test-token");

    expect(items).toEqual([
      { entityId: "item-1", title: "Torch", quantity: 5 },
      { entityId: "item-2", title: "Rope", quantity: null },
    ]);
  });
});

describe("getEntity", () => {
  it("fetches the entity's full detail shape", async () => {
    server.use(
      http.get(`${BASE_URL}/tenants/${TENANT_ID}/entities/item-1`, () =>
        HttpResponse.json({
          id: "item-1",
          name: "Ashfang",
          created_at: "2026-01-01T00:00:00Z",
          updated_at: "2026-01-01T00:00:00Z",
          stats: [{ name: "damage", value: 10 }],
          stat_groups: [],
          information: [
            {
              id: "info-1",
              title: "Description",
              type: "description",
              payloads: [{ kind: "description", content: "A flaming sword.", locale: "en-US" }],
            },
          ],
          prototypes: [],
          instances: [],
          parent: null,
          quantity: null,
          children: [],
        }),
      ),
    );

    const client = createLorenzoApiClient(BASE_URL);
    const entity = await client.getEntity(TENANT_ID, "item-1", "test-token");

    expect(entity.name).toBe("Ashfang");
    expect(entity.information[0]?.title).toBe("Description");
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

describe("getGmCampaignIds", () => {
  it("returns the ids of every campaign_gm_grants entry", async () => {
    server.use(
      http.get(`${BASE_URL}/me`, () =>
        HttpResponse.json({
          id: "user-1",
          authgear_subject_id: "sub-1",
          memberships: [],
          players: [],
          campaign_gm_grants: [
            { id: "campaign-1", slug: "a", name: "A", game_system: "5e", secret: false },
            { id: "campaign-2", slug: "b", name: "B", game_system: "5e", secret: false },
          ],
        }),
      ),
    );

    const client = createLorenzoApiClient(BASE_URL);
    await expect(client.getGmCampaignIds("test-token")).resolves.toEqual([
      "campaign-1",
      "campaign-2",
    ]);
  });
});

describe("getMyProfile", () => {
  it("carries every ADR 0060 profile field straight through, alongside membership role, this tenant's characters, and a global gm count", async () => {
    server.use(
      http.get(`${BASE_URL}/me`, () =>
        HttpResponse.json({
          id: "user-1",
          authgear_subject_id: "sub-1",
          email: "frodo@shire.example",
          nickname: "frodo",
          display_name: "Frodo Baggins",
          pronouns: "he/him",
          bio: "Just a hobbit.",
          locales: ["en-US"],
          user_color: "#00FF00",
          picture_url: "https://lorenzo-api.test/users/user-1/picture",
          memberships: [{ tenant_id: TENANT_ID, role: "orga" }],
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
              characters: [{ entity_id: "other-character", name: "Elsewhere", is_pc: true }],
            },
          ],
          campaign_gm_grants: [
            { id: "campaign-3", slug: "a", name: "A", game_system: "5e", secret: false },
          ],
        }),
      ),
    );

    const client = createLorenzoApiClient(BASE_URL);
    const profile = await client.getMyProfile(TENANT_ID, "test-token");

    expect(profile).toEqual({
      email: "frodo@shire.example",
      nickname: "frodo",
      displayName: "Frodo Baggins",
      pronouns: "he/him",
      bio: "Just a hobbit.",
      locales: ["en-US"],
      color: "#00FF00",
      pictureUrl: "https://lorenzo-api.test/users/user-1/picture",
      membershipRole: "orga",
      characters: [{ entityId: CHARACTER_ID, name: "Frodo" }],
      gmCampaignCount: 1,
    });
  });

  it("reports a null membershipRole when the caller has no Membership row in this tenant, and nulls for every unset profile field", async () => {
    server.use(
      http.get(`${BASE_URL}/me`, () =>
        HttpResponse.json({
          id: "user-1",
          authgear_subject_id: "sub-1",
          email: null,
          nickname: null,
          display_name: null,
          pronouns: null,
          bio: null,
          locales: [],
          user_color: null,
          picture_url: "https://lorenzo-api.test/users/user-1/picture",
          memberships: [],
          players: [],
          campaign_gm_grants: [],
        }),
      ),
    );

    const client = createLorenzoApiClient(BASE_URL);
    const profile = await client.getMyProfile(TENANT_ID, "test-token");

    expect(profile).toEqual({
      email: null,
      nickname: null,
      displayName: null,
      pronouns: null,
      bio: null,
      locales: [],
      color: null,
      pictureUrl: "https://lorenzo-api.test/users/user-1/picture",
      membershipRole: null,
      characters: [],
      gmCampaignCount: 0,
    });
  });
});

describe("listItems", () => {
  it("returns the catalog page's items", async () => {
    server.use(
      http.get(`${BASE_URL}/tenants/${TENANT_ID}/items`, () =>
        HttpResponse.json({
          items: [{ entity_id: "item-1", title: "Sword" }],
          total: 1,
          page: 1,
          size: 50,
          pages: 1,
        }),
      ),
    );

    const client = createLorenzoApiClient(BASE_URL);
    const items = await client.listItems(TENANT_ID, "test-token");

    expect(items).toEqual([{ entity_id: "item-1", title: "Sword" }]);
  });
});

describe("createItemInstance", () => {
  it("posts prototype_id and owner_character_id, omitting container when not given", async () => {
    let receivedBody: unknown;
    server.use(
      http.post(`${BASE_URL}/tenants/${TENANT_ID}/item-instances`, async ({ request }) => {
        receivedBody = await request.json();
        return HttpResponse.json(
          { entity_id: "item-1", title: "Sword", owner_entity_id: CHARACTER_ID },
          { status: 201 },
        );
      }),
    );

    const client = createLorenzoApiClient(BASE_URL);
    const result = await client.createItemInstance(
      TENANT_ID,
      "prototype-1",
      CHARACTER_ID,
      undefined,
      "test-token",
    );

    expect(receivedBody).toEqual({ prototype_id: "prototype-1", owner_character_id: CHARACTER_ID });
    expect(result.owner_entity_id).toBe(CHARACTER_ID);
  });

  it("includes container_entity_id when given", async () => {
    let receivedBody: unknown;
    server.use(
      http.post(`${BASE_URL}/tenants/${TENANT_ID}/item-instances`, async ({ request }) => {
        receivedBody = await request.json();
        return HttpResponse.json(
          { entity_id: "item-1", title: "Sword", owner_entity_id: CHARACTER_ID },
          { status: 201 },
        );
      }),
    );

    const client = createLorenzoApiClient(BASE_URL);
    await client.createItemInstance(
      TENANT_ID,
      "prototype-1",
      CHARACTER_ID,
      "container-1",
      "test-token",
    );

    expect(receivedBody).toEqual({
      prototype_id: "prototype-1",
      owner_character_id: CHARACTER_ID,
      container_entity_id: "container-1",
    });
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

  it("includes owner_character_id when given (ADR 0044 split-with-owner)", async () => {
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
    await client.splitItemInstance(TENANT_ID, "item-1", 3, "test-token", undefined, CHARACTER_ID);

    expect(receivedBody).toEqual({ quantity: 3, owner_character_id: CHARACTER_ID });
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

describe("setItemInstanceContainer", () => {
  it("puts the new container and returns the updated instance", async () => {
    let receivedBody: unknown;
    server.use(
      http.put(
        `${BASE_URL}/tenants/${TENANT_ID}/item-instances/item-1/container`,
        async ({ request }) => {
          receivedBody = await request.json();
          return HttpResponse.json({
            entity_id: "item-1",
            title: "Torch",
            container_entity_id: "container-2",
          });
        },
      ),
    );

    const client = createLorenzoApiClient(BASE_URL);
    const result = await client.setItemInstanceContainer(
      TENANT_ID,
      "item-1",
      "container-2",
      "test-token",
    );

    expect(receivedBody).toEqual({ container_entity_id: "container-2" });
    expect(result.container_entity_id).toBe("container-2");
  });

  it("sends the given etag as If-Match", async () => {
    let receivedIfMatch: string | null = null;
    server.use(
      http.put(
        `${BASE_URL}/tenants/${TENANT_ID}/item-instances/item-1/container`,
        ({ request }) => {
          receivedIfMatch = request.headers.get("if-match");
          return HttpResponse.json({ entity_id: "item-1", title: "Torch" });
        },
      ),
    );

    const client = createLorenzoApiClient(BASE_URL);
    await client.setItemInstanceContainer(
      TENANT_ID,
      "item-1",
      "container-2",
      "test-token",
      'W/"fresh"',
    );

    expect(receivedIfMatch).toBe('W/"fresh"');
  });
});

describe("createInformation", () => {
  it("posts the note fields with the API's own locale default", async () => {
    let receivedBody: unknown;
    server.use(
      http.post(
        `${BASE_URL}/tenants/${TENANT_ID}/entities/item-1/information`,
        async ({ request }) => {
          receivedBody = await request.json();
          return HttpResponse.json(
            { id: "info-1", title: "Note", type: "note", payloads: [] },
            { status: 201 },
          );
        },
      ),
    );

    const client = createLorenzoApiClient(BASE_URL);
    const result = await client.createInformation(
      TENANT_ID,
      "item-1",
      { title: "Note", type: "note", isPublic: false, content: "Secretly cursed." },
      "test-token",
    );

    expect(receivedBody).toEqual({
      title: "Note",
      type: "note",
      is_public: false,
      content: "Secretly cursed.",
      locale: "en-US",
    });
    expect(result.id).toBe("info-1");
  });
});

describe("addInformationKnower", () => {
  it("puts the knower and returns the updated information", async () => {
    server.use(
      http.put(`${BASE_URL}/tenants/${TENANT_ID}/information/info-1/knowers/char-1`, () =>
        HttpResponse.json({ id: "info-1", title: "Note", type: "note", payloads: [] }),
      ),
    );

    const client = createLorenzoApiClient(BASE_URL);
    const result = await client.addInformationKnower(TENANT_ID, "info-1", "char-1", "test-token");

    expect(result.id).toBe("info-1");
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

describe("getItemInstanceBySlug", () => {
  it("resolves a slug to its current instance state, with etag", async () => {
    server.use(
      http.get(`${BASE_URL}/tenants/${TENANT_ID}/item-instances/by-slug/the-chest`, () =>
        HttpResponse.json(
          { entity_id: "item-1", title: "The Chest", quantity: null, owner_entity_id: null },
          { headers: { etag: 'W/"abc"' } },
        ),
      ),
    );

    const client = createLorenzoApiClient(BASE_URL);
    const { data, etag } = await client.getItemInstanceBySlug(TENANT_ID, "the-chest", "test-token");

    expect(data.entity_id).toBe("item-1");
    expect(etag).toBe('W/"abc"');
  });

  it("throws a 404 LorenzoApiError when no instance has that slug", async () => {
    server.use(
      http.get(`${BASE_URL}/tenants/${TENANT_ID}/item-instances/by-slug/no-such-slug`, () =>
        HttpResponse.json(
          { type: "not-found", title: "Not Found", detail: "no instance with that slug" },
          { status: 404, headers: { "content-type": "application/problem+json" } },
        ),
      ),
    );

    const client = createLorenzoApiClient(BASE_URL);
    await expect(
      client.getItemInstanceBySlug(TENANT_ID, "no-such-slug", "test-token"),
    ).rejects.toMatchObject({ status: 404 });
  });
});

describe("bulkAssignItemInstances", () => {
  it("posts the array body and returns one result per input entry", async () => {
    let receivedBody: unknown;
    server.use(
      http.post(
        `${BASE_URL}/tenants/${TENANT_ID}/item-instances/bulk-assign`,
        async ({ request }) => {
          receivedBody = await request.json();
          return HttpResponse.json([
            { entity_id: "item-1", status: "ok", item_instance: { entity_id: "item-1" } },
            {
              entity_id: "item-2",
              status: "error",
              problem: { type: "conflict", title: "Precondition Failed", status: 412 },
            },
          ]);
        },
      ),
    );

    const client = createLorenzoApiClient(BASE_URL);
    const results = await client.bulkAssignItemInstances(
      TENANT_ID,
      [
        { entity_id: "item-1", owner_character_id: CHARACTER_ID, if_match: 'W/"a"' },
        { entity_id: "item-2", owner_character_id: CHARACTER_ID, quantity: 2 },
      ],
      "test-token",
    );

    expect(receivedBody).toEqual([
      { entity_id: "item-1", owner_character_id: CHARACTER_ID, if_match: 'W/"a"' },
      { entity_id: "item-2", owner_character_id: CHARACTER_ID, quantity: 2 },
    ]);
    expect(results).toHaveLength(2);
    expect(results[0]).toMatchObject({ status: "ok" });
    expect(results[1]).toMatchObject({ status: "error" });
  });
});

describe("listGroups", () => {
  it("returns the first page of groups, flattened to entityId/name", async () => {
    server.use(
      http.get(`${BASE_URL}/tenants/${TENANT_ID}/groups`, () =>
        HttpResponse.json({
          items: [
            { id: "group-1", name: "The Party" },
            { id: "group-2", name: "Villains" },
          ],
          total: 2,
          page: 1,
          size: 50,
          pages: 1,
        }),
      ),
    );

    const client = createLorenzoApiClient(BASE_URL);
    const groups = await client.listGroups(TENANT_ID, "test-token");

    expect(groups).toEqual([
      { entityId: "group-1", name: "The Party" },
      { entityId: "group-2", name: "Villains" },
    ]);
  });
});

describe("createItemInstance with a name", () => {
  it("sends the name so the instance isn't just called after its prototype", async () => {
    let receivedBody: unknown;
    server.use(
      http.post(`${BASE_URL}/tenants/${TENANT_ID}/item-instances`, async ({ request }) => {
        receivedBody = await request.json();
        return HttpResponse.json({ entity_id: "sack-1", title: "Camp supplies" }, { status: 201 });
      }),
    );

    const client = createLorenzoApiClient(BASE_URL);
    await client.createItemInstance(
      TENANT_ID,
      "prototype-1",
      CHARACTER_ID,
      undefined,
      "test-token",
      "Camp supplies",
    );

    expect(receivedBody).toEqual({
      prototype_id: "prototype-1",
      owner_character_id: CHARACTER_ID,
      name: "Camp supplies",
    });
  });
});

describe("findItemsByName", () => {
  it("filters the catalog server-side with ?q=, as the caller", async () => {
    let query: string | null = null;
    server.use(
      http.get(`${BASE_URL}/tenants/${TENANT_ID}/items`, ({ request }) => {
        query = new URL(request.url).searchParams.get("q");
        expect(request.headers.get("authorization")).toBe("Bearer test-token");
        return HttpResponse.json({ items: [{ entity_id: "item-1", title: "Sack" }] });
      }),
    );

    const client = createLorenzoApiClient(BASE_URL);
    const items = await client.findItemsByName(TENANT_ID, "Sack", "test-token");

    expect(query).toBe("Sack");
    expect(items.map((i) => i.title)).toEqual(["Sack"]);
  });

  it("throws a LorenzoApiError carrying the status - a non-member gets a 404", async () => {
    server.use(
      http.get(`${BASE_URL}/tenants/${TENANT_ID}/items`, () =>
        HttpResponse.json({ title: "Not Found", status: 404 }, { status: 404 }),
      ),
    );

    const client = createLorenzoApiClient(BASE_URL);

    await expect(client.findItemsByName(TENANT_ID, "Sack", "test-token")).rejects.toMatchObject({
      status: 404,
    });
  });
});

describe("createItem", () => {
  it("posts a plain catalog item: a name and no prototypes", async () => {
    let receivedBody: unknown;
    server.use(
      http.post(`${BASE_URL}/tenants/${TENANT_ID}/items`, async ({ request }) => {
        receivedBody = await request.json();
        return HttpResponse.json({ entity_id: "item-9", title: "Sack" }, { status: 201 });
      }),
    );

    const client = createLorenzoApiClient(BASE_URL);
    const item = await client.createItem(TENANT_ID, "Sack", "test-token");

    expect(receivedBody).toEqual({ name: "Sack", prototype_ids: [] });
    expect(item.entity_id).toBe("item-9");
  });
});

describe("bulkMoveItemInstances", () => {
  it("moves exactly the given items, in the explicit-list mode", async () => {
    let receivedBody: unknown;
    server.use(
      http.post(
        `${BASE_URL}/tenants/${TENANT_ID}/item-instances/bulk-move`,
        async ({ request }) => {
          receivedBody = await request.json();
          return HttpResponse.json([
            { entity_id: "a", status: "ok" },
            { entity_id: "b", status: "error", problem: { title: "Nope", detail: "Not yours" } },
          ]);
        },
      ),
    );

    const client = createLorenzoApiClient(BASE_URL);
    const results = await client.bulkMoveItemInstances(
      TENANT_ID,
      "sack-1",
      ["a", "b"],
      "test-token",
    );

    expect(receivedBody).toEqual({
      to_container_entity_id: "sack-1",
      items: [{ entity_id: "a" }, { entity_id: "b" }],
    });
    expect(results.map((r) => r.status)).toEqual(["ok", "error"]);
  });
});

describe("listMyUnreadNotifications", () => {
  it("asks for the caller's own unread notifications, as the caller", async () => {
    let query: URLSearchParams | undefined;
    server.use(
      http.get(`${BASE_URL}/me/notifications`, ({ request }) => {
        query = new URL(request.url).searchParams;
        expect(request.headers.get("authorization")).toBe("Bearer test-token");
        return HttpResponse.json({
          items: [{ id: "n-1", title: "You were awarded a sword", body: "Ashfang", read_at: null }],
          total: 1,
          page: 1,
          size: 50,
          pages: 1,
        });
      }),
    );

    const client = createLorenzoApiClient(BASE_URL);
    const items = await client.listMyUnreadNotifications("test-token");

    expect(query?.get("unread_only")).toBe("true");
    expect(query?.get("size")).toBe("50");
    expect(items.map((n) => n.id)).toEqual(["n-1"]);
  });

  it("throws a LorenzoApiError carrying the status on failure", async () => {
    server.use(
      http.get(`${BASE_URL}/me/notifications`, () =>
        HttpResponse.json({ title: "Unauthorized", status: 401 }, { status: 401 }),
      ),
    );

    const client = createLorenzoApiClient(BASE_URL);

    await expect(client.listMyUnreadNotifications("bad-token")).rejects.toMatchObject({
      status: 401,
    });
  });
});
