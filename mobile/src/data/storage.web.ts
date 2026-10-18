const cacheKey = (key: string) => `leagueops:${key}`;
const ACTIONS_KEY = 'leagueops:actions';
export async function initStorage() { return; }
export async function readCache<T>(key: string, fallback: T): Promise<T> {
  const data = localStorage.getItem(cacheKey(key));
  return data ? JSON.parse(data) as T : fallback;
}
export async function writeCache(key: string, data: unknown) { localStorage.setItem(cacheKey(key), JSON.stringify(data)); }
export async function readActionRecords<T>(): Promise<T[]> { return JSON.parse(localStorage.getItem(ACTIONS_KEY) ?? '[]') as T[]; }
export async function saveActionRecord(action: { action_id: string }) {
  const actions = await readActionRecords<{ action_id: string }>();
  localStorage.setItem(ACTIONS_KEY, JSON.stringify([...actions.filter(item => item.action_id !== action.action_id), action]));
}
export async function deleteActionRecords(ids: string[]) {
  const actions = await readActionRecords<{ action_id: string }>();
  localStorage.setItem(ACTIONS_KEY, JSON.stringify(actions.filter(item => !ids.includes(item.action_id))));
}

