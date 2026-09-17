CREATE TABLE "loot_bot"."loot_claim" (
	"loot_drop_id" uuid NOT NULL,
	"item_entity_id" text NOT NULL,
	"discord_user_id" text NOT NULL,
	"character_entity_id" text NOT NULL,
	"quantity" integer,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "loot_claim_loot_drop_id_item_entity_id_discord_user_id_pk" PRIMARY KEY("loot_drop_id","item_entity_id","discord_user_id")
);
--> statement-breakpoint
CREATE TABLE "loot_bot"."loot_drop" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"container_entity_id" text NOT NULL,
	"discord_channel_id" text NOT NULL,
	"discord_message_id" text,
	"created_by_discord_user_id" text NOT NULL,
	"status" text DEFAULT 'open' NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL
);
--> statement-breakpoint
ALTER TABLE "loot_bot"."loot_claim" ADD CONSTRAINT "loot_claim_loot_drop_id_loot_drop_id_fk" FOREIGN KEY ("loot_drop_id") REFERENCES "loot_bot"."loot_drop"("id") ON DELETE cascade ON UPDATE no action;