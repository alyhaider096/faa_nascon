import NetInfo from '@react-native-community/netinfo';
import * as SecureStore from 'expo-secure-store';
import * as SQLite from 'expo-sqlite';
import React, { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react';
import { Platform } from 'react-native';
import { ACCOUNTS, CLUB, DEMO_PASSWORD, FIXTURES, Fixture, PRODUCTS, Product, Role, STANDINGS } from '../data/mock';
import { ApiError, Bootstrap, ClubProfile, League, Projection, RosterHistory, ServerProduct, Tenant, User, matchFromServer, productFromServer, request } from '../data/api';

type Account = (typeof ACCOUNTS)[number] & Partial<User>;
export type PendingAction = { action_id: string; owner?: string; type: 'score_event' | 'roster_transfer'; queued_at: string; base_version: number; payload: Record<string, unknown>; label: string; status: 'pending' | 'applied' | 'rejected'; resolution?: string };
type BasketItem = { variantId: string; name: string; label: string; unitPriceMinor: number; quantity: number };
type Receipt = { orderId: string; totalMinor: number; items: BasketItem[]; paidAt: string; discountMinor: number; signature?: string; pdfBase64?: string };
type AppState = {
  ready: boolean; account: Account | null; serverUrl: string; demoMode: boolean; online: boolean; syncing: boolean;
  fixtures: Fixture[]; standings: typeof STANDINGS; club: ClubProfile; queue: PendingAction[];
  products: Product[]; tenant: Tenant | null; leagues: League[]; selectedLeague: string; loading: boolean; dataError: string;
  selectLeague: (id: string) => Promise<void>; refreshMatch: (id: string) => Promise<void>; watchMatch: (id: string) => () => void;
  rosterHistory: (id: string) => Promise<RosterHistory>;
  rosterDestinations: () => Promise<{ id: string; clubName: string; leagueId: string }[]>;
  cart: BasketItem[]; receipt: Receipt | null;
  login: (email: string, password: string) => Promise<string | null>; logout: () => Promise<void>;
  setServerUrl: (value: string) => Promise<void>; setDemoMode: (value: boolean) => Promise<void>;
  addToCart: (item: BasketItem) => void; clearCart: () => void; checkout: (token: string, discount: string) => Promise<string | null>;
  addPlayer: (player: { name: string; position: string; number: number }) => Promise<string | null>;
  queueAction: (action: Omit<PendingAction, 'action_id' | 'queued_at' | 'status'>) => Promise<void>;
  syncQueue: () => Promise<void>; clearResolved: () => Promise<void>; refreshCache: () => Promise<void>;
};

const Context = createContext<AppState | null>(null);
const DB_NAME = 'leagueops.db';
const DEFAULT_SERVER_URL = 'http://10.0.2.2:8080';
const EMPTY_CLUB: ClubProfile = { name: 'Club profile', tag: 'No club loaded', founded: 'Not supplied', venue: 'Not supplied', staff: [], roster: [] };
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
const web = Platform.OS === 'web';
const secureGet = (key: string) => web ? Promise.resolve(null) : SecureStore.getItemAsync(key);
const secureSet = (key: string, value: string) => web ? Promise.resolve() : SecureStore.setItemAsync(key, value);
const secureDelete = (key: string) => web ? Promise.resolve() : SecureStore.deleteItemAsync(key);

async function initDatabase() {
  if (web) return;
  const db = await database();
  await db.execAsync('CREATE TABLE IF NOT EXISTS cache (key TEXT PRIMARY KEY, data TEXT NOT NULL); CREATE TABLE IF NOT EXISTS actions (id TEXT PRIMARY KEY, data TEXT NOT NULL);');
}
async function readCache<T>(key: string, fallback: T): Promise<T> {
  if (web) { const data = localStorage.getItem(`leagueops:${key}`); return data ? JSON.parse(data) as T : fallback; }
  const row = await (await database()).getFirstAsync<{ data: string }>('SELECT data FROM cache WHERE key = ?', key);
  return row ? JSON.parse(row.data) as T : fallback;
}
async function writeCache(key: string, data: unknown) {
  if (web) { localStorage.setItem(`leagueops:${key}`, JSON.stringify(data)); return; }
  await (await database()).runAsync('INSERT OR REPLACE INTO cache (key, data) VALUES (?, ?)', key, JSON.stringify(data));
}
async function readActions() {
  if (web) return JSON.parse(localStorage.getItem('leagueops:actions') ?? '[]') as PendingAction[];
  const rows = await (await database()).getAllAsync<{ data: string }>('SELECT data FROM actions ORDER BY id');
  return rows.map(row => JSON.parse(row.data) as PendingAction).sort((a, b) => a.queued_at.localeCompare(b.queued_at));
}
async function saveAction(action: PendingAction) {
  if (web) { const actions = await readActions(); localStorage.setItem('leagueops:actions', JSON.stringify([...actions.filter(a => a.action_id !== action.action_id), action])); return; }
  await (await database()).runAsync('INSERT OR REPLACE INTO actions (id, data) VALUES (?, ?)', action.action_id, JSON.stringify(action));
}

export function AppProvider({ children }: { children: React.ReactNode }) {
  const [ready, setReady] = useState(false);
  const [account, setAccount] = useState<Account | null>(null);
  const [serverUrl, setServerUrlState] = useState(DEFAULT_SERVER_URL);
  const [demoMode, setDemoModeState] = useState(true);
  const tokenRef = useRef<string | null>(null);
  const [tenant, setTenant] = useState<Tenant | null>(null);
  const [products, setProducts] = useState<Product[]>([]);
  const [leagues, setLeagues] = useState<League[]>([]);
  const [knownClubs, setKnownClubs] = useState<Bootstrap['clubs']>([]);
  const [selectedLeague, setSelectedLeague] = useState('');
  const [loading, setLoading] = useState(false);
  const [dataError, setDataError] = useState('');
  const [online, setOnline] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [fixtures, setFixtures] = useState<Fixture[]>([]);
  const [standings, setStandings] = useState<typeof STANDINGS>([]);
  const [club, setClub] = useState<ClubProfile>(EMPTY_CLUB);
  const [queue, setQueue] = useState<PendingAction[]>([]);
  const [cart, setCart] = useState<BasketItem[]>([]);
  const [receipt, setReceipt] = useState<Receipt | null>(null);
  const checkoutOrderId = useRef<{ id: string; fingerprint: string } | null>(null);
  const wasOnline = useRef(false);

  useEffect(() => {
    let active = true;
    (async () => {
      await initDatabase();
      const [savedSession, savedServer, savedDemo, savedQueue] = await Promise.all([
        secureGet('session_v1'), readCache('server_url', DEFAULT_SERVER_URL), readCache('live_demo_mode', true), readActions(),
      ]);
      if (!active) return;
      const session = savedSession ? JSON.parse(savedSession) as { token: string; user: User; tenant: Tenant | null; server: string } : null;
      if (session?.server === savedServer && !savedDemo) { tokenRef.current = session.token; setAccount({ ...session.user, label: session.user.display_name }); setTenant(session.tenant); }
      setServerUrlState(savedServer); setDemoModeState(savedDemo);
      setQueue(savedQueue);
      if (savedDemo) { setFixtures(FIXTURES); setStandings(STANDINGS); setClub(CLUB); setProducts(PRODUCTS); }
      setReady(true);
    })().catch(() => setReady(true));
    // A hotspot can reach the local API without public internet access.
    const subscription = NetInfo.addEventListener(state => setOnline(Boolean(state.isConnected)));
    return () => { active = false; subscription(); };
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    if (!demoMode) {
      try {
        const result = await request<{ token: string; user: User; tenant: Tenant | null }>(serverUrl, '/api/v1/auth/login', null, { email: email.trim().toLowerCase(), password });
        if (!result.token || !result.user?.user_id) return 'The server did not return a valid login.';
        await secureSet('session_v1', JSON.stringify({ ...result, server: serverUrl }));
        tokenRef.current = result.token; setAccount({ ...result.user, label: result.user.display_name }); setTenant(result.tenant); setDataError('');
        return null;
      } catch (error) { return error instanceof Error ? error.message : 'Could not sign in.'; }
    }
    const found = ACCOUNTS.find(a => a.email.toLowerCase() === email.trim().toLowerCase());
    if (!found || password !== DEMO_PASSWORD) return 'Use a listed demo account and the demo password.';
    await secureSet('demo_email', found.email);
    setFixtures(FIXTURES); setStandings(STANDINGS); setProducts(PRODUCTS); setClub(await readCache('demo_club', CLUB));
    setAccount(found);
    return null;
  }, [demoMode, serverUrl]);
  const logout = useCallback(async () => { tokenRef.current = null; await secureDelete('session_v1'); await secureDelete('demo_email'); setAccount(null); setCart([]); setReceipt(null); setFixtures([]); setStandings([]); setClub(EMPTY_CLUB); setProducts([]); setTenant(null); setLeagues([]); setKnownClubs([]); }, []);
  const api = useCallback(async <T,>(path: string, body?: unknown): Promise<T> => {
    try { return await request<T>(serverUrl, path, tokenRef.current, body); }
    catch (error) { if (error instanceof ApiError && error.status === 401) await logout(); throw error; }
  }, [logout, serverUrl]);
  const setServerUrl = useCallback(async (value: string) => { const clean = value.trim().replace(/\/$/, ''); if (clean !== serverUrl) await logout(); setServerUrlState(clean); await writeCache('server_url', clean); }, [logout, serverUrl]);
  const setDemoMode = useCallback(async (value: boolean) => { await logout(); setDemoModeState(value); await writeCache('live_demo_mode', value); if (value) { setFixtures(FIXTURES); setStandings(STANDINGS); setClub(CLUB); setProducts(PRODUCTS); } }, [logout]);
  const cachePrefix = `${serverUrl}:${account?.user_id ?? 'demo'}:`;
  const selectLeague = useCallback(async (id: string) => {
    setSelectedLeague(id);
    if (demoMode) return;
    const cached = await readCache<typeof STANDINGS>(`${cachePrefix}standings:${id}`, []);
    setStandings(cached);
    if (!online) return;
    try {
      const result = await api<{ table: { team_id: string; team_name?: string; played: number; won: number; drawn: number; lost: number; diff: number; points: number; status: string }[] }>(`/api/v1/leagues/${encodeURIComponent(id)}/standings`);
      const rows = result.table.map(row => ({ ...row, team: row.team_name ?? row.team_id, status: row.status.replaceAll('_', ' ') }));
      setStandings(rows); await writeCache(`${cachePrefix}standings:${id}`, rows);
    } catch (error) { setDataError(error instanceof Error ? error.message : 'Standings could not be loaded.'); }
  }, [api, cachePrefix, demoMode, online]);
  const refreshMatch = useCallback(async (id: string) => {
    if (demoMode || !online) return;
    const projection = await api<Projection>(`/api/v1/matches/${encodeURIComponent(id)}`);
    setFixtures(current => { const updated = matchFromServer(projection, current.find(f => f.id === id)); const next = [...current.filter(f => f.id !== id), updated]; void writeCache(`${cachePrefix}fixtures`, next); return next; });
  }, [api, cachePrefix, demoMode, online]);
  const refreshCache = useCallback(async () => {
    if (demoMode || !account) return;
    setLoading(true); setDataError('');
    try {
      const cached = await readCache<{ bootstrap: Bootstrap; club: ClubProfile; products: Product[] } | null>(`${cachePrefix}bootstrap`, null);
      const cachedFixtures = await readCache<Fixture[]>(`${cachePrefix}fixtures`, []); setFixtures(cachedFixtures);
      if (cached) { setTenant(cached.bootstrap.tenant); setLeagues(cached.bootstrap.leagues); setKnownClubs(cached.bootstrap.clubs); setProducts(cached.products); setClub(cached.club); }
      if (!online) { if (cached?.bootstrap.leagues[0]) await selectLeague(account.league_id ?? cached.bootstrap.leagues[0].league_id); return; }
      const data = await api<Bootstrap>('/api/v1/bootstrap');
      setTenant(data.tenant); setLeagues(data.leagues); setKnownClubs(data.clubs);
      const catalogue = await api<{ products: ServerProduct[] }>('/api/v1/products');
      const nextProducts = catalogue.products.map(productFromServer); setProducts(nextProducts);
      const clubId = account.club_id ?? data.clubs[0]?.club_id;
      let profile = EMPTY_CLUB;
      if (clubId) {
        const c = await api<{ club_id: string; name: string; venue?: { name?: string }; staff?: { name: string; role: string }[]; roster: { player_id: string; name: string; position?: string; number?: number }[] }>(`/api/v1/clubs/${encodeURIComponent(clubId)}`);
        profile = { name: c.name, tag: c.club_id, founded: 'Not supplied', venue: c.venue?.name ?? 'Not supplied', staff: (c.staff ?? []).map(s => `${s.role} · ${s.name}`), roster: c.roster.map(p => ({ id: p.player_id, name: p.name, position: p.position ?? 'Player', number: p.number ?? '—', role: '' })) };
      }
      setClub(profile); await writeCache(`${cachePrefix}bootstrap`, { bootstrap: data, club: profile, products: nextProducts });
      const leagueId = account.league_id ?? data.leagues[0]?.league_id;
      if (leagueId) await selectLeague(leagueId);
      // Only discover match IDs supplied by the server. Never promote demo matches into live mode.
      const ids = [...new Set([...(data.fixtures ?? []).map(f => f.match_id), ...catalogue.products.map(p => p.pinned_match_id).filter((id): id is string => Boolean(id))])];
      for (const id of ids) {
        try {
          await refreshMatch(id);
          const pinnedProductId = catalogue.products.find(p => p.pinned_match_id === id)?.product_id;
          if (pinnedProductId) setFixtures(current => current.map(f => f.id === id ? { ...f, pinnedProductId } : f));
        } catch (error) { setDataError(error instanceof Error ? error.message : 'Match could not be loaded.'); }
      }
    } catch (error) { setDataError(error instanceof Error ? error.message : 'Could not refresh data.'); }
    finally { setLoading(false); }
  }, [account, api, cachePrefix, demoMode, online, refreshMatch, selectLeague]);
  useEffect(() => { if (ready && account && !demoMode) void refreshCache(); }, [ready, account, demoMode, refreshCache]);
  const rosterHistory = useCallback(async (id: string) => {
    const key = `${cachePrefix}roster:${id}`;
    if (!online) { const saved = await readCache<RosterHistory | null>(key, null); if (!saved) throw new Error('Open this player while connected before making an offline change.'); return saved; }
    const history = await api<RosterHistory>(`/api/v1/roster/history/${encodeURIComponent(id)}`); await writeCache(key, history); return history;
  }, [api, cachePrefix, online]);
  const rosterDestinations = useCallback(async () => {
    const key = `${cachePrefix}destinations`;
    if (!online) return readCache<{ id: string; clubName: string; leagueId: string }[]>(key, []);
    const result: { id: string; clubName: string; leagueId: string }[] = [];
    for (const candidate of knownClubs.filter(c => c.club_id !== account?.club_id)) {
      try {
        const profile = await api<{ roster: { player_id: string }[] }>(`/api/v1/clubs/${encodeURIComponent(candidate.club_id)}`);
        if (!profile.roster[0]) continue;
        const history = await rosterHistory(profile.roster[0].player_id);
        if (history.current_squad_id && !result.some(item => item.id === history.current_squad_id)) result.push({ id: history.current_squad_id, clubName: candidate.name, leagueId: history.league_id });
      } catch { /* This club may not have a roster in the active league. */ }
    }
    await writeCache(key, result); return result;
  }, [account, api, cachePrefix, knownClubs, online, rosterHistory]);
  const watchMatch = useCallback((id: string) => {
    if (demoMode || !online || !tokenRef.current) return () => {};
    let stopped = false; let busy = false; let last = 0;
    const update = async () => { if (stopped || busy || Date.now() - last < 2000) return; busy = true; last = Date.now(); try { await refreshMatch(id); } catch (error) { if (!stopped) setDataError(error instanceof Error ? error.message : 'Live update failed.'); } finally { busy = false; } };
    const socket = new WebSocket(`${serverUrl.replace(/^http/, 'ws')}/ws/v1/matches/${encodeURIComponent(id)}?token=${encodeURIComponent(tokenRef.current)}`);
    socket.onmessage = () => { void update(); }; socket.onerror = () => socket.close();
    void update();
    const poll = setInterval(() => { if (socket.readyState !== WebSocket.OPEN) void update(); }, 5000);
    return () => { stopped = true; clearInterval(poll); socket.close(); };
  }, [demoMode, online, refreshMatch, serverUrl]);
  const addToCart = useCallback((item: BasketItem) => { checkoutOrderId.current = null; setCart(current => {
    const old = current.find(x => x.variantId === item.variantId);
    return old ? current.map(x => x.variantId === item.variantId ? { ...x, quantity: x.quantity + item.quantity } : x) : [...current, item];
  }); }, []);
  const clearCart = useCallback(() => { checkoutOrderId.current = null; setCart([]); }, []);
  const addPlayer = useCallback(async (player: { name: string; position: string; number: number }) => {
    if (club.roster.some(existing => existing.number === player.number)) return 'That shirt number is already taken.';
    if (!demoMode) {
      return 'Player registration is not exposed by the backend yet. Existing players can be transferred, loaned or released.';
    }
    const updated = { ...club, roster: [...club.roster, { ...player, role: 'Substitute' }] };
    setClub(updated); await writeCache('demo_club', updated);
    return null;
  }, [club, demoMode]);
  const checkout = useCallback(async (token: string, discount: string) => {
    if (!cart.length) return 'Add a product before checking out.';
    if (!online) return 'Connect to the server before paying. Your bag is still here.';
    if (demoMode && token !== 'tok_success') {
      if (token === 'tok_declined') return 'Mock payment declined. No stock was taken; try another token.';
      if (token === 'tok_capture_fail') return 'Payment authorization succeeded, but capture failed. No charge was completed.';
      return 'Use tok_success, tok_declined or tok_capture_fail for the mock gateway.';
    }
    if (demoMode && discount && discount.toUpperCase() !== 'WELCOME10') return 'Discount code not recognized.';
    if (!demoMode) {
      try {
        const fingerprint = JSON.stringify({ cart, token, discount: discount.trim() });
        if (checkoutOrderId.current?.fingerprint !== fingerprint) checkoutOrderId.current = { id: `ord-${Date.now()}`, fingerprint };
        const data = await api<{ order_id: string; total_minor: number; discount_minor: number; receipt: { payload: { paid_at: string }; signature: string; pdf_base64?: string } }>('/api/v1/checkout', {
          order_id: checkoutOrderId.current.id,
          items: cart.map(item => ({ variant_id: item.variantId, quantity: item.quantity })),
          discount_code: discount.trim() || null, payment: { token },
        });
        if (!data?.receipt?.payload || !data?.receipt?.signature) return 'The server did not return a signed receipt. Please ask the team to check this order.';
        setReceipt({ orderId: data.order_id, totalMinor: data.total_minor, discountMinor: data.discount_minor, paidAt: data.receipt.payload.paid_at, items: [...cart], signature: data.receipt.signature, pdfBase64: data.receipt.pdf_base64 });
        checkoutOrderId.current = null;
        setCart([]);
        return null;
      } catch (error) { return error instanceof Error ? error.message : 'Payment could not be completed.'; }
    }
    const subtotal = cart.reduce((sum, item) => sum + item.unitPriceMinor * item.quantity, 0);
    const discountMinor = discount ? Math.floor(subtotal / 10) : 0;
    setReceipt({ orderId: `demo-${Date.now()}`, totalMinor: subtotal - discountMinor, items: [...cart], paidAt: new Date().toISOString(), discountMinor });
    checkoutOrderId.current = null;
    setCart([]);
    return null;
  }, [api, cart, demoMode, online]);
  const queueAction = useCallback(async (action: Omit<PendingAction, 'action_id' | 'queued_at' | 'status'>) => {
    const saved: PendingAction = { ...action, owner: `${serverUrl}:${account?.user_id ?? 'demo'}`, action_id: `mobile-${Date.now()}-${Math.floor(Math.random() * 10000)}`, queued_at: utcSeconds(), status: 'pending' };
    await saveAction(saved);
    setQueue(current => [...current, saved]);
    if (online && !demoMode && action.type === 'score_event') {
      try {
        await api(`/api/v1/matches/${encodeURIComponent(String(action.payload.match_id))}/events`, action.payload);
        const applied: PendingAction = { ...saved, status: 'applied', resolution: 'Applied by the server.' }; await saveAction(applied); setQueue(current => current.map(a => a.action_id === saved.action_id ? applied : a));
        await refreshMatch(String(action.payload.match_id));
      } catch (error) {
        // A lost response is safely retried with the same event_id through offline-sync.
        if (error instanceof ApiError && error.status >= 400 && error.status < 500 && error.status !== 401 && error.status !== 429) {
          const rejected: PendingAction = { ...saved, status: 'rejected', resolution: error.message }; await saveAction(rejected); setQueue(current => current.map(a => a.action_id === saved.action_id ? rejected : a));
        }
      }
    }
  }, [account, api, demoMode, online, refreshMatch, serverUrl]);
  const syncQueue = useCallback(async () => {
    if (!online || syncing) return;
    setSyncing(true);
    try {
      if (demoMode) {
        throw new Error('Switch off Demo data in Settings to sync with the backend. Your actions remain queued.');
      } else {
        // Never mark actions applied without a server response.
        const pending = queue.filter(a => a.status === 'pending' && a.owner === `${serverUrl}:${account?.user_id}`).slice(0, 100);
        if (!pending.length) return;
        const data = await api<{ results: { action_id: string; status: 'applied' | 'rejected' | 'duplicate'; error_code: string | null; message?: string }[] }>('/api/v1/offline-sync', { device_id: 'leagueops-android', actions: pending.map(({ action_id, type, queued_at, base_version, payload }) => ({ action_id, type, queued_at, base_version, payload })) });
        const updated: PendingAction[] = pending.map(a => { const result = data.results.find(r => r.action_id === a.action_id); return result ? { ...a, status: result.status === 'rejected' ? 'rejected' : 'applied', resolution: result.message || syncExplanation(result.error_code, result.status) } : a; });
        await Promise.all(updated.map(saveAction)); setQueue(current => current.map(a => updated.find(u => u.action_id === a.action_id) ?? a));
      }
    } finally { setSyncing(false); }
  }, [account, api, demoMode, online, queue, serverUrl, syncing]);
  const clearResolved = useCallback(async () => {
    if (web) { const retained = queue.filter(a => a.status === 'pending' || a.owner !== `${serverUrl}:${account?.user_id ?? 'demo'}`); localStorage.setItem('leagueops:actions', JSON.stringify(retained)); setQueue(retained); return; }
    const db = await database();
    const resolved = queue.filter(a => a.status !== 'pending' && a.owner === `${serverUrl}:${account?.user_id ?? 'demo'}`);
    await Promise.all(resolved.map(a => db.runAsync('DELETE FROM actions WHERE id = ?', a.action_id)));
    setQueue(current => current.filter(a => !resolved.some(r => r.action_id === a.action_id)));
  }, [account, queue, serverUrl]);
  useEffect(() => {
    if (!ready) return;
    if (online && !wasOnline.current && !demoMode && queue.some(a => a.status === 'pending')) void syncQueue().catch(() => undefined);
    wasOnline.current = online;
  }, [ready, online, demoMode, queue, syncQueue]);

  const visibleQueue = queue.filter(a => a.owner === `${serverUrl}:${account?.user_id ?? 'demo'}`);
  const value = useMemo(() => ({ ready, account, serverUrl, demoMode, online, syncing, fixtures, standings, club, queue: visibleQueue, cart, receipt, login, logout, setServerUrl, setDemoMode, addToCart, clearCart, checkout, addPlayer, queueAction, syncQueue, clearResolved, refreshCache, products, tenant, leagues, selectedLeague, loading, dataError, selectLeague, refreshMatch, watchMatch, rosterHistory, rosterDestinations }), [ready, account, serverUrl, demoMode, online, syncing, fixtures, standings, club, visibleQueue, cart, receipt, login, logout, setServerUrl, setDemoMode, addToCart, clearCart, checkout, addPlayer, queueAction, syncQueue, clearResolved, refreshCache, products, tenant, leagues, selectedLeague, loading, dataError, selectLeague, refreshMatch, watchMatch, rosterHistory, rosterDestinations]);
  return <Context.Provider value={value}>{children}</Context.Provider>;
}
export function useApp() { const value = useContext(Context); if (!value) throw new Error('AppProvider missing'); return value; }
export function canScore(role?: Role) { return role === 'super_admin' || role === 'league_organizer'; }
export function canManageRoster(role?: Role) { return role === 'super_admin' || role === 'club_manager'; }
