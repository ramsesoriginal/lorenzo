import type { Logger } from "pino";
import type { Config } from "./config.js";
import type { RouteHandler } from "./http-server.js";
import { type DeliveryReport, deliverNotifications } from "./notification-bridge.js";
import { type SchedulerAuthOptions, verifySchedulerRequest } from "./scheduler-auth.js";

export type NotificationRouteDeps = Readonly<{
  config: Config;
  logger: Logger;
  /** Overridable in tests. */
  run?: (config: Config, logger: Logger) => Promise<DeliveryReport>;
  verify?: typeof verifySchedulerRequest;
  /** Test seam for the signing keys (see `verifySchedulerRequest`). */
  authKeys?: SchedulerAuthOptions["keys"];
}>;

/**
 * `POST /internal/deliver-notifications` - the one endpoint Cloud Scheduler
 * calls on a timer to run the notification-DM bridge (ADR 0095).
 *
 * - **Off unless configured.** With no `NOTIFICATION_SCHEDULER_SERVICE_ACCOUNT`
 *   the route answers 404 like any unknown path, so a deploy that hasn't done
 *   the Cloud Scheduler setup exposes nothing.
 * - **Only the scheduler.** Anything else is a 401 with no detail (the
 *   reason goes to the log only), because this route makes the bot send DMs
 *   and read every linked user's notifications - it can't be open to the
 *   public internet the way `/interactions` (signature-verified) is.
 * - **POST only**, as Cloud Scheduler sends.
 *
 * Replies with the run's own tally as JSON, which lands in Cloud Scheduler's
 * and Cloud Run's logs.
 */
export function createNotificationDeliveryRoute(deps: NotificationRouteDeps): RouteHandler {
  const { config, logger } = deps;
  const run = deps.run ?? deliverNotifications;
  const verify = deps.verify ?? verifySchedulerRequest;

  return async (req, res) => {
    const serviceAccountEmail = config.notificationSchedulerServiceAccount;
    if (!serviceAccountEmail) {
      res.writeHead(404, { "content-type": "text/plain" }).end("Not found");
      return;
    }
    if (req.method !== "POST") {
      res.writeHead(405, { allow: "POST", "content-type": "text/plain" }).end("Method not allowed");
      return;
    }

    const auth = await verify(req.headers.authorization, {
      audience: config.notificationDeliveryUrl,
      serviceAccountEmail,
      ...(deps.authKeys ? { keys: deps.authKeys } : {}),
    });
    if (!auth.ok) {
      logger.warn({ reason: auth.reason }, "rejected a notification-delivery request");
      res.writeHead(401, { "content-type": "text/plain" }).end("Unauthorized");
      return;
    }

    const report = await run(config, logger);
    logger.info({ ...report }, "notification delivery run finished");
    res.writeHead(200, { "content-type": "application/json" }).end(JSON.stringify(report));
  };
}
