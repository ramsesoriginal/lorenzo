CREATE TABLE "loot_bot"."pending_undo" (
	"discord_user_id" text PRIMARY KEY NOT NULL,
	"action_type" text NOT NULL,
	"payload" text NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL
);
--> statement-breakpoint
ALTER TABLE "loot_bot"."loot_claim" ADD COLUMN "claim_type" text DEFAULT 'greed' NOT NULL;
--> statement-breakpoint
-- Backfilled to the reserved "" global-default channel (ADR 0068) for any
-- row that already existed - a pre-migration preference was, in effect,
-- already global (there was no per-channel concept yet), so this is the
-- correct value for existing rows, not just a placeholder.
ALTER TABLE "loot_bot"."player_preference" ADD COLUMN "discord_channel_id" text DEFAULT '' NOT NULL;
--> statement-breakpoint
-- drizzle-kit can't auto-derive the old single-column PK's constraint name
-- (see its own generated comment, removed here) - it's Postgres's default
-- naming for an inline `PRIMARY KEY` column, confirmed against
-- migrations/0001_good_eddie_brock.sql's original `CREATE TABLE`.
ALTER TABLE "loot_bot"."player_preference" DROP CONSTRAINT "player_preference_pkey";
--> statement-breakpoint
ALTER TABLE "loot_bot"."player_preference" ADD CONSTRAINT "player_preference_discord_user_id_discord_channel_id_pk" PRIMARY KEY("discord_user_id","discord_channel_id");
