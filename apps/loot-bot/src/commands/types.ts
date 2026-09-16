import type { SlashCommandBuilder, SlashCommandOptionsOnlyBuilder } from "discord.js";
import type { Logger } from "pino";
import type { Config } from "../config.js";

export type CommandContext = Readonly<{
  config: Config;
  logger: Logger;
}>;

/**
 * This bot's own, transport-agnostic stand-in for discord.js's Gateway-
 * delivered interaction classes (ADR 0045). Every command file was already
 * written against exactly this narrow surface - confirmed by grepping every
 * `interaction.*` call site before the rewrite - so these types intentionally
 * mirror discord.js's own method names/shapes and hierarchy (a plain
 * "repliable interaction" base every kind shares, plus kind-specific extras)
 * rather than inventing new ones: a real behavior change here would be a red
 * flag, not a feature. The actual objects satisfying these types are built
 * by `../interaction-adapter.ts` from a raw, signature-verified HTTP
 * interaction payload instead of a live Gateway `Client`.
 */

export type SentMessage = Readonly<{ id: string }>;

/** Anything a reply/editReply/followUp/update call can be built from -
 * covers both a plain string and the embed/component shape every
 * `format-*.ts` module already returns (discord.js builder instances, which
 * `discord-rest.ts` serializes via their own `.toJSON()`). */
export type MessagePayload =
  | string
  | Readonly<{
      content?: string;
      embeds?: readonly unknown[];
      components?: readonly unknown[];
    }>;

export type ReplyPayload =
  | string
  | Readonly<{
      content?: string;
      embeds?: readonly unknown[];
      components?: readonly unknown[];
      ephemeral?: boolean;
    }>;

export type OptionsReader = Readonly<{
  getString(name: string, required: true): string;
  getString(name: string, required?: boolean): string | null;
  getInteger(name: string, required: true): number;
  getInteger(name: string, required?: boolean): number | null;
  getFocused(full: true): Readonly<{ name: string; value: string }>;
  getFocused(): string;
}>;

export type InteractionGuards = Readonly<{
  isChatInputCommand(): this is ChatInputCommandInteraction;
  isAutocomplete(): this is AutocompleteInteraction;
  isStringSelectMenu(): this is StringSelectMenuInteraction;
  isButton(): this is ButtonInteraction;
  isModalSubmit(): this is ModalSubmitInteraction;
}>;

type BaseInteraction = InteractionGuards &
  Readonly<{
    user: Readonly<{ id: string }>;
    guildId: string | null;
  }>;

/** Every kind that can answer Discord's original webhook POST at all -
 * mirrors discord.js's own `InteractionResponses` mixin, which every
 * repliable interaction class (chat-input, component, modal-submit) gets
 * uniformly. `commands/index.ts`'s shared error-handling catch block relies
 * on this common surface across the whole dispatch union. */
type RepliableInteraction = BaseInteraction &
  Readonly<{
    deferred: boolean;
    replied: boolean;
    reply(opts: ReplyPayload): Promise<void>;
    followUp(opts: ReplyPayload): Promise<SentMessage>;
  }>;

export type ChatInputCommandInteraction = RepliableInteraction &
  Readonly<{
    commandName: string;
    channelId: string;
    options: OptionsReader;
    deferReply(opts?: Readonly<{ ephemeral?: boolean }>): Promise<void>;
    editReply(opts: MessagePayload): Promise<SentMessage>;
  }>;

export type AutocompleteInteraction = BaseInteraction &
  Readonly<{
    commandName: string;
    options: OptionsReader;
    responded: boolean;
    respond(choices: readonly Readonly<{ name: string; value: string }>[]): Promise<void>;
  }>;

/** A builder-shaped modal - only `.toJSON()` is ever called on it
 * (`format-drop.ts`'s `buildQuantityModal` already returns a real
 * discord.js `ModalBuilder`, unchanged by this rewrite). */
export type ModalLike = Readonly<{ toJSON(): unknown }>;

export type StringSelectMenuInteraction = RepliableInteraction &
  Readonly<{
    customId: string;
    values: readonly string[];
    showModal(modal: ModalLike): Promise<void>;
    update(opts: MessagePayload): Promise<void>;
    deferUpdate(): Promise<void>;
  }>;

export type ButtonInteraction = RepliableInteraction &
  Readonly<{
    customId: string;
    deferUpdate(): Promise<void>;
    editReply(opts: MessagePayload): Promise<SentMessage>;
  }>;

export type ModalSubmitInteraction = RepliableInteraction &
  Readonly<{
    customId: string;
    fields: Readonly<{ getTextInputValue(customId: string): string }>;
    isFromMessage(): this is ModalMessageModalSubmitInteraction;
  }>;

export type ModalMessageModalSubmitInteraction = ModalSubmitInteraction &
  Readonly<{
    update(opts: MessagePayload): Promise<void>;
    deferUpdate(): Promise<void>;
  }>;

export type AnyInteraction =
  | ChatInputCommandInteraction
  | AutocompleteInteraction
  | StringSelectMenuInteraction
  | ButtonInteraction
  | ModalSubmitInteraction;

export type Command = Readonly<{
  // A bare SlashCommandBuilder (no options chained, e.g. ping.ts) narrows
  // to SlashCommandOptionsOnlyBuilder the moment .addStringOption(...) etc.
  // is called (discord.js's own type-level way of forbidding mixing plain
  // options with subcommands) - accepting either is what lets both shapes
  // satisfy this one field.
  definition: SlashCommandBuilder | SlashCommandOptionsOnlyBuilder;
  execute: (interaction: ChatInputCommandInteraction, ctx: CommandContext) => Promise<void>;
  /** Optional - only commands with an autocompleted option (ADR 0043's
   * `/give`) need one. Must itself call `interaction.respond([...])`
   * (this bot's own interaction model gives autocomplete no other way to
   * reply) within Discord's ~3s window - never let it throw uncaught (see
   * commands/index.ts's dispatcher, which treats a thrown autocomplete
   * handler as "respond with no choices" rather than a failed
   * interaction). */
  autocomplete?: (interaction: AutocompleteInteraction, ctx: CommandContext) => Promise<void>;

  /**
   * Optional - only commands with their own persistent, interactive
   * message need these (ADR 0044's `/drop`). Every `customId` this bot
   * ever creates is namespaced `"<this command's own definition.name>:
   * <action>:<...ids>"`; commands/index.ts's dispatcher extracts the part
   * before the first `:` and routes to whichever of these three is
   * relevant, on this same command - one dispatch convention, not a
   * parallel routing table per interaction kind.
   */
  onSelectMenu?: (interaction: StringSelectMenuInteraction, ctx: CommandContext) => Promise<void>;
  onButton?: (interaction: ButtonInteraction, ctx: CommandContext) => Promise<void>;
  onModalSubmit?: (interaction: ModalSubmitInteraction, ctx: CommandContext) => Promise<void>;
}>;
