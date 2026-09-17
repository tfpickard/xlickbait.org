CREATE TYPE "headline_kind" AS ENUM('fresh', 'vintage');--> statement-breakpoint
CREATE TYPE "headline_status" AS ENUM('published', 'hidden');--> statement-breakpoint
CREATE TABLE "generator_runs" (
	"id" bigint PRIMARY KEY GENERATED ALWAYS AS IDENTITY (sequence name "generator_runs_id_seq" INCREMENT BY 1 MINVALUE 1 MAXVALUE 9223372036854775807 START WITH 1 CACHE 1),
	"started_at" timestamp with time zone DEFAULT now() NOT NULL,
	"finished_at" timestamp with time zone,
	"fresh_count" integer DEFAULT 0 NOT NULL,
	"vintage_count" integer DEFAULT 0 NOT NULL,
	"rejected_count" integer DEFAULT 0 NOT NULL,
	"error" text
);
--> statement-breakpoint
CREATE TABLE "headlines" (
	"id" bigint PRIMARY KEY GENERATED ALWAYS AS IDENTITY (sequence name "headlines_id_seq" INCREMENT BY 1 MINVALUE 1 MAXVALUE 9223372036854775807 START WITH 1 CACHE 1),
	"arxiv_id" text NOT NULL,
	"headline" text NOT NULL,
	"dek" text NOT NULL,
	"anchor" text NOT NULL,
	"actual_point" text NOT NULL,
	"kind" "headline_kind" NOT NULL,
	"model" text NOT NULL,
	"status" "headline_status" DEFAULT 'published'::"headline_status" NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"publish_at" timestamp with time zone DEFAULT now() NOT NULL
);
--> statement-breakpoint
CREATE TABLE "papers" (
	"arxiv_id" text PRIMARY KEY,
	"title" text NOT NULL,
	"abstract" text NOT NULL,
	"authors" text[] NOT NULL,
	"primary_category" text NOT NULL,
	"categories" text[] NOT NULL,
	"published_at" timestamp with time zone NOT NULL,
	"abs_url" text NOT NULL
);
--> statement-breakpoint
CREATE UNIQUE INDEX "headlines_one_published_per_paper" ON "headlines" ("arxiv_id") WHERE "status" = 'published';--> statement-breakpoint
CREATE INDEX "headlines_status_publish_at_id_idx" ON "headlines" ("status","publish_at" DESC NULLS LAST,"id" DESC NULLS LAST);--> statement-breakpoint
CREATE INDEX "headlines_kind_status_publish_at_idx" ON "headlines" ("kind","status","publish_at" DESC NULLS LAST);--> statement-breakpoint
CREATE INDEX "papers_primary_category_idx" ON "papers" ("primary_category");--> statement-breakpoint
CREATE INDEX "papers_categories_gin_idx" ON "papers" USING gin ("categories");--> statement-breakpoint
ALTER TABLE "headlines" ADD CONSTRAINT "headlines_arxiv_id_papers_arxiv_id_fkey" FOREIGN KEY ("arxiv_id") REFERENCES "papers"("arxiv_id") ON DELETE CASCADE;