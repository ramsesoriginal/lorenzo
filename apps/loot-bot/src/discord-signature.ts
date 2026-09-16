import { verifyKey } from "discord-interactions";

/**
 * Verifies Discord's Ed25519 signature on an inbound interactions-webhook
 * request (ADR 0045) - must run against the *raw* request body, before any
 * JSON parsing, per Discord's own documented interactions-endpoint
 * contract. `http-server.ts`'s `/interactions` route reads the body itself
 * for exactly this reason (every other route on this server never needs
 * one).
 */
export async function verifyDiscordSignature(
  rawBody: string,
  signature: string | string[] | undefined,
  timestamp: string | string[] | undefined,
  publicKey: string,
): Promise<boolean> {
  if (typeof signature !== "string" || typeof timestamp !== "string") return false;
  return verifyKey(rawBody, signature, timestamp, publicKey);
}
