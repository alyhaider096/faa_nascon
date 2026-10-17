import NetInfo from '@react-native-community/netinfo';
import * as SecureStore from 'expo-secure-store';
import * as SQLite from 'expo-sqlite';
import React, { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react';
import { ACCOUNTS, CLUB, DEMO_PASSWORD, FIXTURES, Fixture, Role, STANDINGS } from '../data/mock';

type Account = (typeof ACCOUNTS)[number];
export type PendingAction = { action_id: string; type: 'score_event' | 'roster_transfer'; queued_at: string; base_version: number; payload: Record<string, unknown>; label: string; status: 'pending' | 'applied' | 'rejected'; resolution?: string };
type BasketItem = { variantId: string; name: string; label: string; unitPriceMinor: number; quantity: number };
type Receipt = { orderId: string; totalMinor: number; items: BasketItem[]; paidAt: string; discountMinor: number; signature?: string; pdfBase64?: string };
type AppState = {
  ready: boolean; account: Account | null; serverUrl: string; demoMode: boolean; online: boolean; syncing: boolean;
  fixtures: Fixture[]; standings: typeof STANDINGS; club: typeof CLUB; queue: PendingAction[];
  cart: BasketItem[]; receipt: Receipt | null;
  login: (email: string, password: string) => Promise<string | null>; logout: () => Promise<void>;
  setServerUrl: (value: string) => Promise<void>; setDemoMode: (value: boolean) => Promise<void>;
  addToCart: (item: BasketItem) => void; clearCart: () => void; checkout: (token: string, discount: string) => Promise<string | null>;
  queueAction: (action: Omit<PendingAction, 'action_id' | 'queued_at' | 'status'>) => Promise<void>;
  syncQueue: () => Promise<void>; clearResolved: () => Promise<void>; refreshCache: () => Promise<void>;
};

const Context = createContext<AppState | null>(null);
const DB_NAME = 'leagueops.db';
const utcSeconds = () => new Date().toISOString().replace(/\.\d{3}Z$/, 'Z');
const syncExplanation = (code: string | null, status: string) => {
  if (status === 'duplicate') return 'Already received by the server; no second change was made.';
  if (status === 'applied') return 'Applied by the server.';
  const explanations: Record<string, string> = {
    INVALID_BASE_VERSION: 'This action was based on a newer version than the server has. Refresh and retry.',
    MATCH_NOT_IN_PROGRESS: 'The match is not live, so this scoring action was not accepted.',
    NOT_IN_SQUAD: 'This player is no longer in the selected squad.',
    SQUAD_FULL: 'The destination squad is full.',
    TRANSFER_WINDOW_CLOSED: 'The transfer window is closed for this date.',
    INVALID_COMPENSATION: 'That scoring event cannot be corrected.',
    OUT_OF_STOCK: 'This item is no longer available.',
  };
  return explanations[code ?? ''] ?? 'The server rejected this action. Check the current match or roster and try again.';
};
let dbPromise: Promise<SQLite.SQLiteDatabase> | undefined;
const database = () => (dbPromise ??= SQLite.openDatabaseAsync(DB_NAME));

async function initDatabase() {
  const db = await database();
  await db.execAsync('CREATE TABLE IF NOT EXISTS cache (key TEXT PRIMARY KEY, data TEXT NOT NULL); CREATE TABLE IF NOT EXISTS actions (id TEXT PRIMARY KEY, data TEXT NOT NULL);');
}
async function readCache<T>(key: string, fallback: T): Promise<T> {
  const row = await (await database()).getFirstAsync<{ data: string }>('SELECT data FROM cache WHERE key = ?', key);
  return row ? JSON.parse(row.data) as T : fallback;
}
async function writeCache(key: string, data: unknown) {
  await (await database()).runAsync('INSERT OR REPLACE INTO cache (key, data) VALUES (?, ?)', key, JSON.stringify(data));
}
async function readActions() {
  const rows = await (await database()).getAllAsync<{ data: string }>('SELECT data FROM actions ORDER BY id');
  return rows.map(row => JSON.parse(row.data) as PendingAction).sort((a, b) => a.queued_at.localeCompare(b.queued_at));
}
async function saveAction(action: PendingAction) {
  await (await database()).runAsync('INSERT OR REPLACE INTO actions (id, data) VALUES (?, ?)', action.action_id, JSON.stringify(action));
}

export function AppProvider({ children }: { children: React.ReactNode }) {
  const [ready, setReady] = useState(false);
  const [account, setAccount] = useState<Account | null>(null);
  const [serverUrl, setServerUrlState] = useState('http://192.168.43.1:8080');
  const [demoMode, setDemoModeState] = useState(true);
  const [online, setOnline] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [fixtures, setFixtures] = useState(FIXTURES);
  const [standings, setStandings] = useState(STANDINGS);
  const [club, setClub] = useState(CLUB);
  const [queue, setQueue] = useState<PendingAction[]>([]);
  const [cart, setCart] = useState<BasketItem[]>([]);
  const [receipt, setReceipt] = useState<Receipt | null>(null);
  const checkoutOrderId = useRef<{ id: string; fingerprint: string } | null>(null);

  useEffect(() => {
    let active = true;
    (async () => {
      await initDatabase();
      const [savedEmail, savedServer, savedDemo, savedFixtures, savedStandings, savedClub, savedQueue] = await Promise.all([
        SecureStore.getItemAsync('demo_email'), readCache('server_url', serverUrl), readCache('demo_mode', true),
        readCache('fixtures', FIXTURES), readCache('standings', STANDINGS), readCache('club', CLUB), readActions(),
      ]);
      if (!active) return;
      setAccount(ACCOUNTS.find(a => a.email === savedEmail) ?? null);
      setServerUrlState(savedServer); setDemoModeState(savedDemo);
      setFixtures(savedFixtures); setStandings(savedStandings); setClub(savedClub); setQueue(savedQueue);
      await Promise.all([writeCache('fixtures', savedFixtures), writeCache('standings', savedStandings), writeCache('club', savedClub)]);
      setReady(true);
    })().catch(() => setReady(true));
    const subscription = NetInfo.addEventListener(state => setOnline(Boolean(state.isConnected && state.isInternetReachable !== false)));
    return () => { active = false; subscription(); };
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const found = ACCOUNTS.find(a => a.email.toLowerCase() === email.trim().toLowerCase());
    if (!found || password !== DEMO_PASSWORD) return 'Use a listed demo account and the demo password.';
    await SecureStore.setItemAsync('demo_email', found.email);
    setAccount(found);
    return null;
  }, []);
  const logout = useCallback(async () => { await SecureStore.deleteItemAsync('demo_email'); setAccount(null); setCart([]); }, []);
  const setServerUrl = useCallback(async (value: string) => { const clean = value.trim().replace(/\/$/, ''); setServerUrlState(clean); await writeCache('server_url', clean); }, []);
  const setDemoMode = useCallback(async (value: boolean) => { setDemoModeState(value); await writeCache('demo_mode', value); }, []);
  const refreshCache = useCallback(async () => { await Promise.all([writeCache('fixtures', fixtures), writeCache('standings', standings), writeCache('club', club)]); }, [fixtures, standings, club]);
  const addToCart = useCallback((item: BasketItem) => { checkoutOrderId.current = null; setCart(current => {
    const old = current.find(x => x.variantId === item.variantId);
    return old ? current.map(x => x.variantId === item.variantId ? { ...x, quantity: x.quantity + item.quantity } : x) : [...current, item];
  }); }, []);
  const clearCart = useCallback(() => { checkoutOrderId.current = null; setCart([]); }, []);
  const checkout = useCallback(async (token: string, discount: string) => {
    if (!cart.length) return 'Add a product before checking out.';
    if (!online) return 'Connect to the server before paying. Your bag is still here.';
    if (demoMode && token !== 'tok_success') return token === 'tok_declined' ? 'Mock payment declined.' : 'Use the success token for the demo checkout.';
    if (demoMode && discount && discount.toUpperCase() !== 'WELCOME10') return 'Discount code not recognized.';
    if (!demoMode) {
      try {
        const fingerprint = JSON.stringify({ cart, token, discount: discount.trim() });
        if (checkoutOrderId.current?.fingerprint !== fingerprint) checkoutOrderId.current = { id: `ord-${Date.now()}`, fingerprint };
        const response = await fetch(`${serverUrl}/audit/v1/checkout`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({
          order_id: checkoutOrderId.current.id, customer_id: 'cust-mobile-1',
          items: cart.map(item => ({ variant_id: item.variantId, quantity: item.quantity })),
          discount_code: discount.trim() || null, payment: { token },
        }) });
        const data = await response.json();
        if (!response.ok) return data?.error?.message || 'Payment could not be completed. Your bag is unchanged.';
        if (!data?.receipt?.payload || !data?.receipt?.signature) return 'The server did not return a signed receipt. Please ask the team to check this order.';
        setReceipt({ orderId: data.order_id, totalMinor: data.total_minor, discountMinor: data.discount_minor, paidAt: data.receipt.payload.paid_at, items: [...cart], signature: data.receipt.signature, pdfBase64: data.receipt.pdf_base64 });
        checkoutOrderId.current = null;
        setCart([]);
        return null;
      } catch { return 'Cannot reach the payment server. Check the server address and try again.'; }
    }
    const subtotal = cart.reduce((sum, item) => sum + item.unitPriceMinor * item.quantity, 0);
    const discountMinor = discount ? Math.floor(subtotal / 10) : 0;
    setReceipt({ orderId: `demo-${Date.now()}`, totalMinor: subtotal - discountMinor, items: [...cart], paidAt: new Date().toISOString(), discountMinor });
    checkoutOrderId.current = null;
    setCart([]);
    return null;
  }, [cart, demoMode, online, serverUrl]);
  const queueAction = useCallback(async (action: Omit<PendingAction, 'action_id' | 'queued_at' | 'status'>) => {
    const saved: PendingAction = { ...action, action_id: `mobile-${Date.now()}-${Math.floor(Math.random() * 10000)}`, queued_at: utcSeconds(), status: 'pending' };
    await saveAction(saved);
    setQueue(current => [...current, saved]);
  }, []);
  const syncQueue = useCallback(async () => {
    if (!online || syncing) return;
    setSyncing(true);
    try {
      if (demoMode) {
        throw new Error('Switch off Demo data in Settings to sync with the backend. Your actions remain queued.');
      } else {
        // Never mark actions applied without a server response.
        const pending = queue.filter(a => a.status === 'pending').slice(0, 100);
        if (!pending.length) return;
        const response = await fetch(`${serverUrl}/audit/v1/offline-sync`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ device_id: 'leagueops-android', actions: pending.map(({ action_id, type, queued_at, base_version, payload }) => ({ action_id, type, queued_at, base_version, payload })) }) });
        if (!response.ok) throw new Error(`Sync failed: ${response.status}`);
        const data = await response.json() as { results: { action_id: string; status: 'applied' | 'rejected' | 'duplicate'; error_code: string | null }[] };
        const updated: PendingAction[] = queue.map(a => { const result = data.results.find(r => r.action_id === a.action_id); return result ? { ...a, status: result.status === 'rejected' ? 'rejected' : 'applied', resolution: syncExplanation(result.error_code, result.status) } : a; });
        await Promise.all(updated.map(saveAction)); setQueue(updated);
      }
    } finally { setSyncing(false); }
  }, [demoMode, online, queue, serverUrl, syncing]);
  const clearResolved = useCallback(async () => {
    const db = await database();
    const resolved = queue.filter(a => a.status !== 'pending');
    await Promise.all(resolved.map(a => db.runAsync('DELETE FROM actions WHERE id = ?', a.action_id)));
    setQueue(current => current.filter(a => a.status === 'pending'));
  }, [queue]);
  useEffect(() => { if (online && queue.some(a => a.status === 'pending')) void syncQueue().catch(() => undefined); }, [online]);

  const value = useMemo(() => ({ ready, account, serverUrl, demoMode, online, syncing, fixtures, standings, club, queue, cart, receipt, login, logout, setServerUrl, setDemoMode, addToCart, clearCart, checkout, queueAction, syncQueue, clearResolved, refreshCache }), [ready, account, serverUrl, demoMode, online, syncing, fixtures, standings, club, queue, cart, receipt, login, logout, setServerUrl, setDemoMode, addToCart, clearCart, checkout, queueAction, syncQueue, clearResolved, refreshCache]);
  return <Context.Provider value={value}>{children}</Context.Provider>;
}
export function useApp() { const value = useContext(Context); if (!value) throw new Error('AppProvider missing'); return value; }
export function canScore(role?: Role) { return role === 'super_admin' || role === 'league_organizer'; }
export function canManageRoster(role?: Role) { return role === 'super_admin' || role === 'club_manager'; }
