CREATE TABLE "loot_bot"."changes_seen" (
	"discord_user_id" text PRIMARY KEY NOT NULL,
	"seen_at" timestamp with time zone DEFAULT now() NOT NULL
);
--> statement-breakpoint
CREATE TABLE "loot_bot"."character_event" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"event_id" uuid NOT NULL,
	"character_entity_id" text NOT NULL,
	"kind" text NOT NULL,
	"summary" text NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL
);
--> statement-breakpoint
CREATE INDEX "character_event_character_created_idx" ON "loot_bot"."character_event" USING btree ("character_entity_id","created_at");