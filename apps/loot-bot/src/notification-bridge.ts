import type { Logger } from "pino";
import type { Config } from "./config.js";
import {
  claimNotificationDelivery,
  getOrCreateNotificationEnrollment,
  listLinkedDiscordUserIds,
  markNotificationSent,
  markNotificationUndelivered,
  pruneNotificationDeliveries,
  releaseNotificationClaim,
} from "./db.js";
import { sendDirectMessage, serializeMessagePayload } from "./discord-rest.js";
import { buildNotificationEmbed } from "./format-notification.js";
import { type NotificationOut, createLorenzoApiClient } from "./lorenzo-client.js";
import { getValidAccessToken } from "./token-provider.js";

/**
 * Bridges each linked user's own unread Lorenzo notifications into Discord
 * DMs (ADR 0095). Run on a schedule by Cloud Scheduler, via
 * `/internal/deliver-notifications` - this bot scales to zero (ADR 0053), so
 * it has no long-lived process to poll from.
 *
 * Everything here happens *as the recipient*: their own stored token reads
 * their own notifications, exactly as every other command acts as whoever
 * ran it (ADR 0050). There is no shared service token that could read
 * anyone's inbox.
 */

/** Per user, per run - so a burst (or a backlog after an outage) arrives as
 * a trickle across runs, not a flood of DMs at once. */
export const MAX_DMS_PER_USER_PER_RUN = 5;

/** Notifications older than this are never delivered, however unread. Bounds
 * what a long outage (or the ledger's own pruning) could ever re-send. */
export const MAX_NOTIFICATION_AGE_MS = 7 * 24 * 60 * 60 * 1000;

/** Finished ledger rows are dropped after this - deliberately much longer
 * than {@link MAX_NOTIFICATION_AGE_MS}, so a row is never pruned while its
 * notification could still be picked up again. */
const PRUNE_AFTER_MS = 30 * 24 * 60 * 60 * 1000;

const CONCURRENT_USERS = 4;

export type DeliveryReport = Readonly<{
  /** Linked users looked at. */
  users: number;
  /** Users skipped for having no usable token (unlinked mid-run, or their
   * refresh token has died - they'll be asked to `/link` again the usual way). */
  skippedUsers: number;
  delivered: number;
  /** Discord refused the DM (closed DMs); queued for the banner. */
  undelivered: number;
  /** Transient failures - released, so the next run retries them. */
  failed: number;
}>;

type Counts = { delivered: number; undelivered: number; failed: number };

/**
 * Which of a user's unread notifications this run should send, oldest first.
 * Pure, and the heart of the "no surprises" rules:
 *
 * - **This bot's tenant, or platform-wide.** `GET /me/notifications` spans
 *   every tenant the user is in; a bot serves exactly one (ADR 0050), so
 *   another tenant's notifications aren't its to send. A null `tenant_id` is
 *   platform scope - addressed to the user, not to any tenant.
 * - **Only what's new since enrollment**, so switching this on never DMs
 *   someone their existing inbox.
 * - **Only recent**, and **only unread** (belt and braces: the API was
 *   already asked for unread only).
 * - **At most {@link MAX_DMS_PER_USER_PER_RUN}**; the rest wait for the next run.
 */
export function selectDeliverable(
  notifications: readonly NotificationOut[],
  options: Readonly<{ tenantId: string; enrolledAt: Date; now: Date }>,
): readonly NotificationOut[] {
  const oldestAllowed = options.now.getTime() - MAX_NOTIFICATION_AGE_MS;
  return notifications
    .filter((n) => n.read_at === null)
    .filter((n) => n.tenant_id === null || n.tenant_id === options.tenantId)
    .filter((n) => {
      const created = new Date(n.created_at).getTime();
      return created > options.enrolledAt.getTime() && created >= oldestAllowed;
    })
    .sort((a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime())
    .slice(0, MAX_DMS_PER_USER_PER_RUN);
}

export async function deliverNotifications(
  config: Config,
  logger: Logger,
  now: Date = new Date(),
): Promise<DeliveryReport> {
  const userIds = await listLinkedDiscordUserIds();
  const totals: Counts = { delivered: 0, undelivered: 0, failed: 0 };
  let skippedUsers = 0;

  await forEachWithConcurrency(userIds, CONCURRENT_USERS, async (discordUserId) => {
    try {
      const counts = await deliverForUser(config, logger, discordUserId, now);
      if (counts === "skipped") {
        skippedUsers += 1;
        return;
      }
      totals.delivered += counts.delivered;
      totals.undelivered += counts.undelivered;
      totals.failed += counts.failed;
    } catch (error) {
      // One user's problem (their token refresh, a DB blip) must never stop
      // everyone else's notifications.
      logger.error({ err: error, discordUserId }, "notification delivery failed for a user");
      totals.failed += 1;
    }
  });

  try {
    await pruneNotificationDeliveries(new Date(now.getTime() - PRUNE_AFTER_MS));
  } catch (error) {
    logger.warn({ err: error }, "couldn't prune old notification delivery rows");
  }

  return { users: userIds.length, skippedUsers, ...totals };
}

async function deliverForUser(
  config: Config,
  logger: Logger,
  discordUserId: string,
  now: Date,
): Promise<Counts | "skipped"> {
  const accessToken = await getValidAccessToken(discordUserId);
  if (!accessToken) return "skipped";

  const enrolledAt = await getOrCreateNotificationEnrollment(discordUserId);
  const client = createLorenzoApiClient(config.lorenzoApiBaseUrl);
  const unread = await client.listMyUnreadNotifications(accessToken);

  const counts: Counts = { delivered: 0, undelivered: 0, failed: 0 };
  for (const notification of selectDeliverable(unread, {
    tenantId: config.lorenzoTenantId,
    enrolledAt,
    now,
  })) {
    // Claim before sending, so overlapping runs can never both DM it.
    if (!(await claimNotificationDelivery(discordUserId, notification.id))) continue;

    try {
      const result = await sendDirectMessage(
        config.discordBotToken,
        discordUserId,
        serializeMessagePayload({ embeds: [buildNotificationEmbed(notification)] }),
      );
      if (result.kind === "sent") {
        await markNotificationSent(discordUserId, notification.id);
        counts.delivered += 1;
      } else {
        await markNotificationUndelivered(discordUserId, notification.id, {
          title: notification.title,
          body: notification.body,
        });
        counts.undelivered += 1;
      }
    } catch (error) {
      // Transient: give the claim back so the next run tries again, and stop
      // for this user - if Discord is rate-limiting, more sends now would
      // only make it worse.
      logger.warn({ err: error, discordUserId }, "couldn't DM a notification; will retry");
      await releaseNotificationClaim(discordUserId, notification.id);
      counts.failed += 1;
      break;
    }
  }
  return counts;
}

async function forEachWithConcurrency<T>(
  items: readonly T[],
  limit: number,
  work: (item: T) => Promise<void>,
): Promise<void> {
  let next = 0;
  const workers = Array.from({ length: Math.min(limit, items.length) }, async () => {
    while (next < items.length) {
      const item = items[next++] as T;
      await work(item);
    }
  });
  await Promise.all(workers);
}
