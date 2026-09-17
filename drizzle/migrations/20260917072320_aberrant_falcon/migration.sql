CREATE TABLE "headline_images" (
	"headline_id" bigint PRIMARY KEY,
	"mime" text NOT NULL,
	"width" integer NOT NULL,
	"height" integer NOT NULL,
	"byte_size" integer NOT NULL,
	"bytes" bytea NOT NULL,
	"model" text NOT NULL,
	"prompt" text NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL
);
--> statement-breakpoint
ALTER TABLE "headline_images" ADD CONSTRAINT "headline_images_headline_id_headlines_id_fkey" FOREIGN KEY ("headline_id") REFERENCES "headlines"("id") ON DELETE CASCADE;--> statement-breakpoint
-- Granted explicitly rather than left to the ALTER DEFAULT PRIVILEGES in
-- `..._readonly_role`. That statement was written without FOR ROLE, so it only
-- covers tables created by the role that ran it -- true today, and an invisible
-- dependency on who applies the next migration. The failure it would cause is a
-- permission denied at image-serving time on production only, which is a bad
-- place to discover it.
GRANT SELECT ON headline_images TO xlickbait_read;
