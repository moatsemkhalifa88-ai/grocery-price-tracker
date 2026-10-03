import "server-only";
import { Pool, types } from "pg";

// numeric → JS number (prices fit comfortably in a double); date stays a string
types.setTypeParser(1700, (v) => (v === null ? null : parseFloat(v)));
types.setTypeParser(20, (v) => (v === null ? null : parseInt(v, 10)));
types.setTypeParser(1082, (v) => v);

declare global {
  // eslint-disable-next-line no-var
  var __pgPool: Pool | undefined;
}

function makePool(): Pool {
  const url = process.env.DATABASE_URL_READONLY;
  if (!url) throw new Error("DATABASE_URL_READONLY is not set (see web/.env.example)");
  const isLocal = /localhost|127\.0\.0\.1/.test(url);
  // TLS is configured here, not in the URL: strip libpq-only params (sslmode,
  // channel_binding) that node-postgres would otherwise warn about.
  const u = new URL(url);
  u.searchParams.delete("sslmode");
  u.searchParams.delete("channel_binding");
  return new Pool({
    connectionString: u.toString(),
    max: 3,
    idleTimeoutMillis: 10_000,
    ssl: isLocal ? undefined : true, // verify the server certificate (Neon has a valid one)
  });
}

export async function query<T>(sql: string, params: unknown[] = []): Promise<T[]> {
  globalThis.__pgPool ??= makePool();
  const res = await globalThis.__pgPool.query(sql, params);
  return res.rows as T[];
}
