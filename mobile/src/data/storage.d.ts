export function initStorage(): Promise<void>;
export function readCache<T>(key: string, fallback: T): Promise<T>;
export function writeCache(key: string, data: unknown): Promise<void>;
export function readActionRecords<T>(): Promise<T[]>;
export function saveActionRecord(action: { action_id: string }): Promise<void>;
export function deleteActionRecords(ids: string[]): Promise<void>;

