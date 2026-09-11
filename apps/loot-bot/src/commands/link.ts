import { SlashCommandBuilder } from "discord.js";
import {
  buildAuthorizationUrl,
  createPkcePair,
  createState,
  getAuthgearConfiguration,
} from "../authgear-client.js";
import { storePendingLink } from "../pending-links.js";
import type { Command } from "./types.js";

/**
 * `/link` - starts the OAuth Authorization Code + PKCE flow (ADR 0029).
 * No separate `/auth/start` HTTP hop: the authorization URL is built
 * straight from discovery and handed to the user directly, who is sent on
 * to Authgear itself; `/auth/callback` (auth-callback-route.ts) picks the
 * flow back up by `state` once Authgear redirects back.
 */
export const linkCommand: Command = {
  definition: new SlashCommandBuilder()
    .setName("link")
    .setDescription("Link your Discord account to your Lorenzo identity."),
  async execute(interaction, ctx) {
    const oidcConfig = await getAuthgearConfiguration(ctx.config);
    const state = createState();
    const pkce = await createPkcePair();

    storePendingLink(state, {
      discordUserId: interaction.user.id,
      codeVerifier: pkce.verifier,
    });

    const authorizationUrl = buildAuthorizationUrl(oidcConfig, ctx.config, {
      state,
      codeChallenge: pkce.challenge,
    });

    await interaction.reply({
      content: `Click below to link your Discord account to your Lorenzo identity:\n${authorizationUrl.toString()}`,
      ephemeral: true,
    });
  },
};
