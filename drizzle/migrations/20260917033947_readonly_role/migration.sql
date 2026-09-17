-- Read-only role for the web application.
--
-- This is the outermost of four layers keeping the site read-only, and the only
-- one that does not live in the repository. The narrowed TypeScript handle, the
-- ESLint rule and the source scan are all bypassed by a compromised build or a
-- dependency postinstall script; a Postgres role without INSERT/UPDATE/DELETE
-- is not.
--
-- The role is created NOLOGIN on purpose: a migration in version control must
-- not carry a password. Grant it one out of band, then point Netlify's
-- DATABASE_URL at it:
--
--   ALTER ROLE xlickbait_read WITH LOGIN PASSWORD '<generated>';
--
-- The generator keeps its own write-capable connection string, which never goes
-- near Netlify.

DO $$
BEGIN
	IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'xlickbait_read') THEN
		CREATE ROLE xlickbait_read NOLOGIN;
	END IF;
END
$$;--> statement-breakpoint
GRANT USAGE ON SCHEMA public TO xlickbait_read;--> statement-breakpoint
GRANT SELECT ON papers, headlines, generator_runs TO xlickbait_read;--> statement-breakpoint
-- Tables created by later migrations are readable too, so a future migration
-- cannot silently produce a table the site is unable to read.
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO xlickbait_read;
