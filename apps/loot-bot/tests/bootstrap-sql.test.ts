import { describe, expect, it } from "vitest";
import {
  InvalidDatabaseUrlError,
  LOOT_BOT_SCHEMA,
  buildBootstrapSql,
  parseRoleCredentials,
} from "../src/bootstrap-sql.js";

describe("parseRoleCredentials", () => {
  it("extracts the role and password from a connection string", () => {
    expect(parseRoleCredentials("postgres://loot_bot:hunter2@localhost:55432/lorenzo")).toEqual({
      role: "loot_bot",
      password: "hunter2",
    });
  });

  it("URL-decodes a percent-encoded username/password", () => {
    expect(parseRoleCredentials("postgres://loot%40bot:p%40ss@localhost:55432/lorenzo")).toEqual({
      role: "loot@bot",
      password: "p@ss",
    });
  });

  it("throws InvalidDatabaseUrlError when there's no username", () => {
    expect(() => parseRoleCredentials("postgres://:hunter2@localhost:55432/lorenzo")).toThrow(
      InvalidDatabaseUrlError,
    );
  });

  it("throws InvalidDatabaseUrlError when there's no password", () => {
    expect(() => parseRoleCredentials("postgres://loot_bot@localhost:55432/lorenzo")).toThrow(
      InvalidDatabaseUrlError,
    );
  });

  it("throws InvalidDatabaseUrlError for a non-URL string", () => {
    expect(() => parseRoleCredentials("not a url")).toThrow(InvalidDatabaseUrlError);
  });
});

describe("buildBootstrapSql", () => {
  it("embeds the role and password into the CREATE ROLE DO block", () => {
    const sql = buildBootstrapSql("loot_bot", "hunter2");
    expect(sql).toContain("SELECT 1 FROM pg_roles WHERE rolname = 'loot_bot'");
    expect(sql).toContain("'loot_bot', 'hunter2'");
    expect(sql).toContain("'CREATE ROLE %I LOGIN PASSWORD %L '");
    expect(sql).toContain("'NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE NOREPLICATION'");
  });

  it("creates and authorizes the loot_bot schema for the given role", () => {
    const sql = buildBootstrapSql("loot_bot", "hunter2");
    expect(sql).toContain('CREATE SCHEMA IF NOT EXISTS "loot_bot" AUTHORIZATION "loot_bot"');
  });

  it("grants exactly USAGE/CREATE on the schema and SELECT/INSERT/UPDATE/DELETE on its tables", () => {
    const sql = buildBootstrapSql("loot_bot", "hunter2");
    expect(sql).toContain('GRANT USAGE, CREATE ON SCHEMA "loot_bot" TO "loot_bot"');
    expect(sql).toContain(
      'GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA "loot_bot" TO "loot_bot"',
    );
    expect(sql).toContain(
      'ALTER DEFAULT PRIVILEGES IN SCHEMA "loot_bot"\n    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO "loot_bot"',
    );
    // Never grants anything on `public` - this role has no business there
    // (ADR 0029's whole point is isolating it away from apps/api's tables).
    expect(sql).not.toMatch(/schema public/i);
  });

  it("sets the role's default search_path to the loot_bot schema", () => {
    const sql = buildBootstrapSql("loot_bot", "hunter2");
    expect(sql).toContain('ALTER ROLE "loot_bot" SET search_path = "loot_bot"');
  });

  it("safely escapes a role/password containing quotes", () => {
    const sql = buildBootstrapSql('weird"role', "O'Brien");
    // Postgres identifier escaping doubles embedded double-quotes.
    expect(sql).toContain('"weird""role"');
    // Postgres string-literal escaping doubles embedded single-quotes.
    expect(sql).toContain("'O''Brien'");
  });

  it("always targets the fixed loot_bot schema regardless of role name", () => {
    const sql = buildBootstrapSql("some_other_role", "pw");
    expect(sql).toContain(`"${LOOT_BOT_SCHEMA}"`);
  });
});
