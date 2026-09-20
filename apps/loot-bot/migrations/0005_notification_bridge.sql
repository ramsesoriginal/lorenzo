CREATE TABLE "loot_bot"."notification_delivery" (
	"discord_user_id" text NOT NULL,
	"notification_id" text NOT NULL,
	"state" text NOT NULL,
	"title" text,
	"body" text,
	"claimed_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "notification_delivery_discord_user_id_notification_id_pk" PRIMARY KEY("discord_user_id","notification_id")
);
--> statement-breakpoint
CREATE TABLE "loot_bot"."notification_enrollment" (
	"discord_user_id" text PRIMARY KEY NOT NULL,
	"enrolled_at" timestamp with time zone DEFAULT now() NOT NULL
);
