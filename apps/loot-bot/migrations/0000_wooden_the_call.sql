-- Hand-edited: drizzle-kit generates a plain `CREATE SCHEMA "loot_bot";`
-- here because db-schema.ts declares a pgSchema("loot_bot"), but this
-- schema's *real* creation - with `AUTHORIZATION <loot_bot role>` and its
-- own grants - happens first, in migrate.ts's own bootstrap step (see
-- bootstrap-sql.ts and ADR 0029). `IF NOT EXISTS` added by hand so this
-- statement is a harmless no-op by the time it runs, rather than a
-- "schema already exists" error, whichever way this migration ends up
-- being invoked.
CREATE SCHEMA IF NOT EXISTS "loot_bot";
--> statement-breakpoint
CREATE TABLE "loot_bot"."linked_account" (
	"discord_user_id" text PRIMARY KEY NOT NULL,
	"authgear_subject_id" text NOT NULL,
	"refresh_token_encrypted" "bytea" NOT NULL,
	"access_token_encrypted" "bytea",
	"access_token_expires_at" timestamp with time zone,
	"key_version" smallint DEFAULT 1 NOT NULL,
	"last_refreshed_at" timestamp with time zone,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "linked_account_authgear_subject_id_unique" UNIQUE("authgear_subject_id")
);
