import * as SQLite from 'expo-sqlite';

const DB_NAME = 'leagueops.db';
let dbPromise: Promise<SQLite.SQLiteDatabase> | undefined;
const database = () => (dbPromise ??= SQLite.openDatabaseAsync(DB_NAME));

export async function initStorage() {
  const db = await database();
  await db.execAsync('CREATE TABLE IF NOT EXISTS cache (key TEXT PRIMARY KEY, data TEXT NOT NULL); CREATE TABLE IF NOT EXISTS actions (id TEXT PRIMARY KEY, data TEXT NOT NULL);');
}
export async function readCache<T>(key: string, fallback: T): Promise<T> {
  const row = await (await database()).getFirstAsync<{ data: string }>('SELECT data FROM cache WHERE key = ?', key);
  return row ? JSON.parse(row.data) as T : fallback;
}
export async function writeCache(key: string, data: unknown) {
  await (await database()).runAsync('INSERT OR REPLACE INTO cache (key, data) VALUES (?, ?)', key, JSON.stringify(data));
}
export async function readActionRecords<T>(): Promise<T[]> {
  const rows = await (await database()).getAllAsync<{ data: string }>('SELECT data FROM actions ORDER BY id');
  return rows.map(row => JSON.parse(row.data) as T);
}
export async function saveActionRecord(action: { action_id: string }) {
  await (await database()).runAsync('INSERT OR REPLACE INTO actions (id, data) VALUES (?, ?)', action.action_id, JSON.stringify(action));
}
export async function deleteActionRecords(ids: string[]) {
  const db = await database();
  await Promise.all(ids.map(id => db.runAsync('DELETE FROM actions WHERE id = ?', id)));
}

