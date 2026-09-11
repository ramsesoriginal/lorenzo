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
          players: [
            {
              tenant_id: TENANT_ID,
              campaign_id: "campaign-1",
              characters: [{ entity_id: CHARACTER_ID, name: "Frodo" }],
            },
            {
              tenant_id: "some-other-tenant",
              campaign_id: "campaign-2",
              characters: [{ entity_id: "other-character", name: "Sam" }],
            },
          ],
        }),
      ),
    );

    const client = createLorenzoApiClient(BASE_URL);
    const characters = await client.getControlledCharacters(TENANT_ID, "test-token");

    expect(characters).toEqual([{ entityId: CHARACTER_ID, name: "Frodo" }]);
  });

  it("fails loudly if GET /me doesn't (yet) carry players[] - today's real shape", async () => {
    server.use(
      http.get(`${BASE_URL}/me`, () =>
        HttpResponse.json({ id: "user-1", authgear_subject_id: "sub-1", memberships: [] }),
      ),
    );

    const client = createLorenzoApiClient(BASE_URL);
    await expect(client.getControlledCharacters(TENANT_ID, "test-token")).rejects.toThrow(
      /does not \(yet\) match/,
    );
  });
});
