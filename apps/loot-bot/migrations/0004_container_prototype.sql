CREATE TABLE "loot_bot"."container_prototype" (
	"tenant_id" text PRIMARY KEY NOT NULL,
	"prototype_entity_id" text NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL
);
