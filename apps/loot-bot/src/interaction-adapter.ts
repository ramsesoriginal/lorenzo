import type {
  AnyInteraction,
  AutocompleteInteraction,
  ButtonInteraction,
  ChatInputCommandInteraction,
  InteractionGuards,
  ModalMessageModalSubmitInteraction,
  ModalSubmitInteraction,
  OptionsReader,
  ReplyPayload,
  StringSelectMenuInteraction,
} from "./commands/types.js";
import {
  editOriginalInteractionResponse,
  ephemeralFlags,
  sendInteractionFollowUp,
  serializeMessagePayload,
} from "./discord-rest.js";

// Discord's InteractionType enum - only the subset this bot ever receives.
const InteractionType = {
  Ping: 1,
  ApplicationCommand: 2,
  MessageComponent: 3,
  ApplicationCommandAutocomplete: 4,
  ModalSubmit: 5,
} as const;

// Discord's ComponentType enum - only the subset this bot ever sends.
const ComponentType = { Button: 2, StringSelect: 3 } as const;

// Discord's InteractionResponseType enum.
const ResponseType = {
  Pong: 1,
  ChannelMessageWithSource: 4,
  DeferredChannelMessageWithSource: 5,
  DeferredUpdateMessage: 6,
  UpdateMessage: 7,
  ApplicationCommandAutocompleteResult: 8,
  Modal: 9,
} as const;

type RawOption = Readonly<{
  name: string;
  value?: string | number;
  focused?: boolean;
}>;

type RawComponent = Readonly<{
  custom_id?: string;
  value?: string;
  components?: readonly RawComponent[];
}>;

export type RawInteractionPayload = Readonly<{
  id: string;
  application_id: string;
  type: number;
  token: string;
  guild_id?: string;
  channel_id?: string;
  member?: Readonly<{ user?: Readonly<{ id: string }> }>;
  user?: Readonly<{ id: string }>;
  message?: Readonly<{ id: string }>;
  data?: Readonly<{
    name?: string;
    custom_id?: string;
    component_type?: number;
    values?: readonly string[];
    options?: readonly RawOption[];
    components?: readonly RawComponent[];
  }>;
}>;

export type ResponseBody = Readonly<{ type: number; data?: unknown }>;

/** The seam between "a command calls `deferReply()`/`reply()`/etc." and
 * "something answers Discord's original webhook POST" (ADR 0053). Exactly
 * one call to `send` per interaction ever matters - a later call is a bug
 * elsewhere and is silently ignored rather than crashing mid-request, the
 * same "don't let one broken path take down the whole response" spirit as
 * `commands/index.ts`'s own dispatcher catch block. */
function createFirstResponseGate(): Readonly<{
  send: (body: ResponseBody) => void;
  promise: Promise<ResponseBody>;
}> {
  let sent = false;
  let resolve!: (body: ResponseBody) => void;
  const promise = new Promise<ResponseBody>((r) => {
    resolve = r;
  });
  return {
    send(body) {
      if (sent) return;
      sent = true;
      resolve(body);
    },
    promise,
  };
}

function getInvokingUserId(payload: RawInteractionPayload): string {
  const id = payload.member?.user?.id ?? payload.user?.id;
  if (!id) throw new Error("interaction payload has no invoking user");
  return id;
}

function makeOptionsReader(options: readonly RawOption[] | undefined): OptionsReader {
  const opts = options ?? [];
  const find = (name: string) => opts.find((o) => o.name === name);
  return {
    getString(name: string, required?: boolean) {
      const value = find(name)?.value;
      if (typeof value === "string") return value;
      if (required) throw new Error(`missing required string option: ${name}`);
      return null as never;
    },
    getInteger(name: string, required?: boolean) {
      const value = find(name)?.value;
      if (typeof value === "number") return value;
      if (required) throw new Error(`missing required integer option: ${name}`);
      return null as never;
    },
    getFocused(full?: boolean) {
      const focused = opts.find((o) => o.focused);
      if (!focused) throw new Error("no focused autocomplete option");
      return (
        full
          ? { name: focused.name, value: String(focused.value ?? "") }
          : String(focused.value ?? "")
      ) as never;
    },
  };
}

function flattenComponents(components: readonly RawComponent[] | undefined): RawComponent[] {
  const out: RawComponent[] = [];
  for (const component of components ?? []) {
    if (component.custom_id !== undefined) out.push(component);
    if (component.components) out.push(...flattenComponents(component.components));
  }
  return out;
}

function replyFlags(opts: ReplyPayload): number | undefined {
  return ephemeralFlags(typeof opts === "string" ? undefined : opts.ephemeral);
}

type Kind = "chat-input" | "autocomplete" | "select-menu" | "button" | "modal-submit";

/** The five `isX()` type guards every interaction kind shares (mirroring
 * discord.js's own base `Interaction` class) - written once, as real type
 * predicates, and spread into each `buildXInteraction` below rather than
 * repeated five times with a different literal `true`. */
function interactionGuards(kind: Kind): InteractionGuards {
  return {
    isChatInputCommand(): this is ChatInputCommandInteraction {
      return kind === "chat-input";
    },
    isAutocomplete(): this is AutocompleteInteraction {
      return kind === "autocomplete";
    },
    isStringSelectMenu(): this is StringSelectMenuInteraction {
      return kind === "select-menu";
    },
    isButton(): this is ButtonInteraction {
      return kind === "button";
    },
    isModalSubmit(): this is ModalSubmitInteraction {
      return kind === "modal-submit";
    },
  };
}

function buildChatInputInteraction(
  payload: RawInteractionPayload,
  gate: ReturnType<typeof createFirstResponseGate>,
): ChatInputCommandInteraction {
  let deferred = false;
  let replied = false;
  return {
    ...interactionGuards("chat-input"),
    user: { id: getInvokingUserId(payload) },
    guildId: payload.guild_id ?? null,
    channelId: payload.channel_id ?? "",
    commandName: payload.data?.name ?? "",
    options: makeOptionsReader(payload.data?.options),
    get deferred() {
      return deferred;
    },
    get replied() {
      return replied;
    },
    async deferReply(opts) {
      deferred = true;
      gate.send({
        type: ResponseType.DeferredChannelMessageWithSource,
        data: { flags: ephemeralFlags(opts?.ephemeral) },
      });
    },
    async reply(opts) {
      replied = true;
      gate.send({
        type: ResponseType.ChannelMessageWithSource,
        data: serializeMessagePayload(opts, replyFlags(opts)),
      });
    },
    async editReply(opts) {
      await gate.promise;
      return editOriginalInteractionResponse(
        payload.application_id,
        payload.token,
        serializeMessagePayload(opts),
      );
    },
    async followUp(opts) {
      await gate.promise;
      return sendInteractionFollowUp(
        payload.application_id,
        payload.token,
        serializeMessagePayload(opts, replyFlags(opts)),
      );
    },
  };
}

function buildAutocompleteInteraction(
  payload: RawInteractionPayload,
  gate: ReturnType<typeof createFirstResponseGate>,
): AutocompleteInteraction {
  let responded = false;
  return {
    ...interactionGuards("autocomplete"),
    user: { id: getInvokingUserId(payload) },
    guildId: payload.guild_id ?? null,
    channelId: payload.channel_id ?? "",
    commandName: payload.data?.name ?? "",
    options: makeOptionsReader(payload.data?.options),
    get responded() {
      return responded;
    },
    async respond(choices) {
      responded = true;
      gate.send({
        type: ResponseType.ApplicationCommandAutocompleteResult,
        data: { choices },
      });
    },
  };
}

function buildSelectMenuInteraction(
  payload: RawInteractionPayload,
  gate: ReturnType<typeof createFirstResponseGate>,
): StringSelectMenuInteraction {
  let deferred = false;
  let replied = false;
  return {
    ...interactionGuards("select-menu"),
    user: { id: getInvokingUserId(payload) },
    guildId: payload.guild_id ?? null,
    channelId: payload.channel_id ?? "",
    customId: payload.data?.custom_id ?? "",
    values: payload.data?.values ?? [],
    get deferred() {
      return deferred;
    },
    get replied() {
      return replied;
    },
    async showModal(modal) {
      gate.send({ type: ResponseType.Modal, data: modal.toJSON() });
    },
    async update(opts) {
      replied = true;
      gate.send({ type: ResponseType.UpdateMessage, data: serializeMessagePayload(opts) });
    },
    async deferUpdate() {
      deferred = true;
      gate.send({ type: ResponseType.DeferredUpdateMessage });
    },
    async editReply(opts) {
      await gate.promise;
      return editOriginalInteractionResponse(
        payload.application_id,
        payload.token,
        serializeMessagePayload(opts),
      );
    },
    async reply(opts) {
      replied = true;
      gate.send({
        type: ResponseType.ChannelMessageWithSource,
        data: serializeMessagePayload(opts, replyFlags(opts)),
      });
    },
    async followUp(opts) {
      await gate.promise;
      return sendInteractionFollowUp(
        payload.application_id,
        payload.token,
        serializeMessagePayload(opts, replyFlags(opts)),
      );
    },
  };
}

function buildButtonInteraction(
  payload: RawInteractionPayload,
  gate: ReturnType<typeof createFirstResponseGate>,
): ButtonInteraction {
  let deferred = false;
  let replied = false;
  return {
    ...interactionGuards("button"),
    user: { id: getInvokingUserId(payload) },
    guildId: payload.guild_id ?? null,
    channelId: payload.channel_id ?? "",
    customId: payload.data?.custom_id ?? "",
    get deferred() {
      return deferred;
    },
    get replied() {
      return replied;
    },
    async reply(opts) {
      replied = true;
      gate.send({
        type: ResponseType.ChannelMessageWithSource,
        data: serializeMessagePayload(opts, replyFlags(opts)),
      });
    },
    async update(opts) {
      replied = true;
      gate.send({ type: ResponseType.UpdateMessage, data: serializeMessagePayload(opts) });
    },
    async deferUpdate() {
      deferred = true;
      gate.send({ type: ResponseType.DeferredUpdateMessage });
    },
    async editReply(opts) {
      await gate.promise;
      return editOriginalInteractionResponse(
        payload.application_id,
        payload.token,
        serializeMessagePayload(opts),
      );
    },
    async followUp(opts) {
      await gate.promise;
      return sendInteractionFollowUp(
        payload.application_id,
        payload.token,
        serializeMessagePayload(opts, replyFlags(opts)),
      );
    },
  };
}

function buildModalSubmitInteraction(
  payload: RawInteractionPayload,
  gate: ReturnType<typeof createFirstResponseGate>,
): ModalSubmitInteraction {
  let deferred = false;
  let replied = false;
  const isFromMessage = payload.message !== undefined;
  const fromMessageExtras = isFromMessage
    ? {
        async update(opts: ReplyPayload) {
          replied = true;
          gate.send({ type: ResponseType.UpdateMessage, data: serializeMessagePayload(opts) });
        },
        async deferUpdate() {
          deferred = true;
          gate.send({ type: ResponseType.DeferredUpdateMessage });
        },
      }
    : {};

  return {
    ...interactionGuards("modal-submit"),
    isFromMessage(): this is ModalMessageModalSubmitInteraction {
      return isFromMessage;
    },
    user: { id: getInvokingUserId(payload) },
    guildId: payload.guild_id ?? null,
    channelId: payload.channel_id ?? "",
    customId: payload.data?.custom_id ?? "",
    fields: {
      getTextInputValue(customId: string) {
        const flat = flattenComponents(payload.data?.components);
        const found = flat.find((c) => c.custom_id === customId);
        if (found?.value === undefined) throw new Error(`missing text input value: ${customId}`);
        return found.value;
      },
    },
    get deferred() {
      return deferred;
    },
    get replied() {
      return replied;
    },
    async reply(opts) {
      replied = true;
      gate.send({
        type: ResponseType.ChannelMessageWithSource,
        data: serializeMessagePayload(opts, replyFlags(opts)),
      });
    },
    async followUp(opts) {
      await gate.promise;
      return sendInteractionFollowUp(
        payload.application_id,
        payload.token,
        serializeMessagePayload(opts, replyFlags(opts)),
      );
    },
    ...fromMessageExtras,
  };
}

/**
 * Builds this bot's adapter interaction for a raw, already-signature-
 * verified Discord payload, plus the "first response" promise whichever
 * HTTP handler received the webhook POST must await and answer with
 * (ADR 0053). Returns `undefined` for a `PING` - the caller answers that
 * directly with `{type: 1}` and never reaches command dispatch at all.
 */
export function buildAdapterInteraction(
  payload: RawInteractionPayload,
): { interaction: AnyInteraction; firstResponse: Promise<ResponseBody> } | undefined {
  const gate = createFirstResponseGate();

  switch (payload.type) {
    case InteractionType.ApplicationCommand:
      return { interaction: buildChatInputInteraction(payload, gate), firstResponse: gate.promise };
    case InteractionType.ApplicationCommandAutocomplete:
      return {
        interaction: buildAutocompleteInteraction(payload, gate),
        firstResponse: gate.promise,
      };
    case InteractionType.MessageComponent:
      if (payload.data?.component_type === ComponentType.StringSelect) {
        return {
          interaction: buildSelectMenuInteraction(payload, gate),
          firstResponse: gate.promise,
        };
      }
      if (payload.data?.component_type === ComponentType.Button) {
        return { interaction: buildButtonInteraction(payload, gate), firstResponse: gate.promise };
      }
      return undefined;
    case InteractionType.ModalSubmit:
      return {
        interaction: buildModalSubmitInteraction(payload, gate),
        firstResponse: gate.promise,
      };
    default:
      return undefined;
  }
}

export function isPing(payload: RawInteractionPayload): boolean {
  return payload.type === InteractionType.Ping;
}

export const pongResponse: ResponseBody = { type: ResponseType.Pong };
