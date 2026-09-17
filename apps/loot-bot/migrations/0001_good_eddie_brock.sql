CREATE TABLE "loot_bot"."player_preference" (
	"discord_user_id" text PRIMARY KEY NOT NULL,
	"current_character_entity_id" text,
	"current_container_entity_id" text,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL
);
