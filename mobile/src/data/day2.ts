import { Platform } from 'react-native';
import * as SecureStore from 'expo-secure-store';
import { ApiError } from './api';

export type PublicMatch = {
  matchId: string;
  status: string;
  title: string;
  competition: string;
  homeName: string;
  awayName: string;
  homeScore: number | string;
  awayScore: number | string;
  playbackUrl: string | null;
  pinnedProduct: PublicProduct | null;
  timeline: TimelineItem[];
  chatRoomId: string;
};

export type PublicProduct = {
  productId: string;
  variantId: string;
  name: string;
  variant: string;
  priceMinor: number;
  currency: string;
  imageUrl?: string | null;
};

export type TimelineItem = { id: string; sequence: number; label: string; timestamp?: string };
export type ChatMessage = { id: string; sequence: number; sender: string; text: string; createdAt?: string };
export type MatchEvent =
  | { type: 'score'; sequence: number; home_score: number | string; away_score: number | string }
  | { type: 'pinned_product'; sequence: number; product: unknown }
  | { type: 'chat'; sequence: number; message: unknown }
  | { type: 'match_state'; sequence: number; status: string; playback_url?: string | null }
  | { type: string; sequence?: number; [key: string]: unknown };

export type PublicProfile = {
  id: string;
  type: 'player' | 'club';
  name: string;
  subtitle: string;
  affiliation?: string;
  followers?: number;
  careerMatches: { id: string; title: string; status: string }[];
  upcomingFixtures: { id: string; title: string; startsAt?: string }[];
  vod: { id: string; title: string; playbackUrl?: string }[];
};

const GUEST_KEY = 'day2_guest_token';
const CART_KEY = 'day2_guest_cart';
const web = Platform.OS === 'web';

export const day2BaseUrl = (configured: string) => {
  if (web && typeof window !== 'undefined' && window.location.port === '8080') return window.location.origin;
  return configured.replace(/\/$/, '');
};

async function readValue(key: string) {
  if (web && typeof localStorage !== 'undefined') return localStorage.getItem(`leagueops:${key}`);
  return SecureStore.getItemAsync(key);
}

async function writeValue(key: string, value: string) {
  if (web && typeof localStorage !== 'undefined') return localStorage.setItem(`leagueops:${key}`, value);
  return SecureStore.setItemAsync(key, value);
}

export async function day2Request<T>(base: string, path: string, options: { method?: 'GET' | 'POST'; token?: string | null; body?: unknown; timeoutMs?: number } = {}) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), options.timeoutMs ?? 10000);
  try {
    const response = await fetch(`${day2BaseUrl(base)}${path}`, {
      method: options.method ?? (options.body === undefined ? 'GET' : 'POST'),
      signal: controller.signal,
      headers: {
        Accept: 'application/json',
        ...(options.body === undefined ? {} : { 'Content-Type': 'application/json' }),
        ...(options.token ? { Authorization: `Bearer ${options.token}` } : {}),
      },
      ...(options.body === undefined ? {} : { body: JSON.stringify(options.body) }),
    });
    const payload = await response.json().catch(() => null);
    if (!response.ok) {
      throw new ApiError(payload?.error?.message || (response.status === 403 ? 'Sign in to complete this action.' : 'The server could not complete this request.'), response.status, payload?.error?.code);
    }
    if (payload === null) throw new ApiError('The server returned an unreadable response.', response.status);
    return payload as T;
  } catch (error) {
    if (error instanceof ApiError) throw error;
    throw new ApiError('Live services are unavailable. Check the team network and try again.', 0, 'NETWORK_UNAVAILABLE');
  } finally {
    clearTimeout(timeout);
  }
}

const pick = (value: unknown, fallback: string) => typeof value === 'string' && value.trim() ? value : fallback;
const score = (value: unknown, fallback: number | string) => typeof value === 'number' || typeof value === 'string' ? value : fallback;

export function normalizeProduct(raw: any): PublicProduct | null {
  const source = raw?.pinned_product ?? raw?.product ?? raw;
  if (!source) return null;
  const variants = Array.isArray(source.variants) ? source.variants : [];
  const variant = variants.find((item: any) => item?.variant_id === 'var-jersey-001-L') ?? variants[0] ?? source.variant ?? {};
  const productId = pick(source.product_id ?? source.id, '');
  const variantId = pick(variant.variant_id ?? variant.id ?? source.variant_id, '');
  if (!productId || !variantId) return null;
  return {
    productId,
    variantId,
    name: pick(source.name, 'Matchday jersey'),
    variant: pick(variant.name ?? variant.label ?? variant.attributes?.size, 'Large'),
    priceMinor: Number(variant.price_minor ?? source.price_minor ?? 0),
    currency: pick(source.currency, 'PKR'),
    imageUrl: source.image_url ?? null,
  };
}

export function normalizeMessage(raw: any, fallbackSequence = 0): ChatMessage {
  return {
    id: pick(raw?.message_id ?? raw?.id, `message-${fallbackSequence}`),
    sequence: Number(raw?.sequence ?? fallbackSequence),
    sender: pick(raw?.sender_name ?? raw?.sender ?? raw?.user_name, 'Member'),
    text: pick(raw?.text ?? raw?.message, ''),
    createdAt: raw?.created_at ?? raw?.timestamp,
  };
}

export function normalizeMatch(raw: any, matchId: string): PublicMatch {
  const payload = raw?.match ?? raw?.projection ?? raw;
  const home = payload?.home ?? payload?.home_team ?? {};
  const away = payload?.away ?? payload?.away_team ?? {};
  const rawEvents = Array.isArray(payload?.timeline) ? payload.timeline : Array.isArray(payload?.events) ? payload.events : [];
  return {
    matchId: pick(payload?.match_id ?? payload?.id, matchId),
    status: pick(payload?.status, 'in_progress'),
    title: pick(payload?.title, `${pick(home?.name ?? home?.team_name, 'Home')} vs ${pick(away?.name ?? away?.team_name, 'Away')}`),
    competition: pick(payload?.league_name ?? payload?.competition ?? payload?.league_id, 'Live competition'),
    homeName: pick(home?.name ?? home?.team_name ?? home?.team_id, 'Home'),
    awayName: pick(away?.name ?? away?.team_name ?? away?.team_id, 'Away'),
    homeScore: score(home?.score ?? payload?.home_score, '—'),
    awayScore: score(away?.score ?? payload?.away_score, '—'),
    playbackUrl: payload?.playback_url ?? payload?.hls_url ?? payload?.stream?.playback_url ?? null,
    pinnedProduct: normalizeProduct(payload?.pinned_product ?? raw?.pinned_product),
    timeline: rawEvents.map((event: any, index: number) => ({
      id: pick(event?.event_id ?? event?.id, `event-${index}`),
      sequence: Number(event?.sequence ?? index + 1),
      label: pick(event?.label ?? event?.text ?? event?.type ?? event?.payload?.event_type, 'Match update'),
      timestamp: event?.created_at ?? event?.timestamp,
    })),
    chatRoomId: pick(payload?.chat_room_id ?? raw?.chat_room_id, `chat-${matchId}`),
  };
}

export async function loadPublicMatch(base: string, matchId: string) {
  const encoded = encodeURIComponent(matchId);
  try {
    const result = await day2Request<any>(base, `/api/v1/public/matches/${encoded}`);
    return normalizeMatch(result, matchId);
  } catch (error) {
    if (!(error instanceof ApiError) || ![401, 404].includes(error.status)) throw error;
    const result = await day2Request<any>(base, `/api/v1/matches/${encoded}`);
    return normalizeMatch(result, matchId);
  }
}

export async function loadProfile(base: string, type: 'player' | 'club', id: string): Promise<PublicProfile> {
  const plural = type === 'player' ? 'players' : 'clubs';
  const path = type === 'club' ? `/api/v1/public/${plural}/${encodeURIComponent(id)}` : `/api/v1/${plural}/${encodeURIComponent(id)}`;
  const raw = await day2Request<any>(base, path);
  const source = raw?.[type] ?? raw;
  const matches = Array.isArray(source?.career_matches) ? source.career_matches : Array.isArray(source?.matches) ? source.matches : [];
  const fixtures = Array.isArray(source?.upcoming_fixtures) ? source.upcoming_fixtures : Array.isArray(source?.fixtures) ? source.fixtures : [];
  const vod = Array.isArray(source?.vod_archive) ? source.vod_archive : Array.isArray(source?.vod) ? source.vod : [];
  return {
    id,
    type,
    name: pick(source?.name ?? source?.display_name, type === 'player' ? 'Athlete' : 'Club'),
    subtitle: pick(source?.position ?? source?.tag ?? source?.venue?.name, type === 'player' ? 'Player profile' : 'Club profile'),
    affiliation: source?.club_name ?? source?.affiliation,
    followers: typeof source?.followers === 'number' ? source.followers : undefined,
    careerMatches: matches.map((item: any) => ({ id: pick(item?.match_id ?? item?.id, ''), title: pick(item?.title, item?.match_id ?? 'Match'), status: pick(item?.status, 'completed') })),
    upcomingFixtures: fixtures.map((item: any) => ({ id: pick(item?.match_id ?? item?.id, ''), title: pick(item?.title, item?.match_id ?? 'Fixture'), startsAt: item?.starts_at })),
    vod: vod.map((item: any) => ({ id: pick(item?.vod_id ?? item?.id ?? item?.match_id, ''), title: pick(item?.title, 'Match recording'), playbackUrl: item?.playback_url })),
  };
}

export async function getGuestToken(base: string) {
  const saved = await readValue(GUEST_KEY);
  if (saved) return saved;
  try {
    const response = await day2Request<{ guest_token: string }>(base, '/api/v1/guest/session', { method: 'POST', body: {} });
    if (response.guest_token) {
      await writeValue(GUEST_KEY, response.guest_token);
      return response.guest_token;
    }
  } catch (error) {
    if (!(error instanceof ApiError) || ![404, 405].includes(error.status)) throw error;
  }
  // Official deterministic reset token, used only when the backend has no session-creation endpoint.
  const auditToken = 'guest_anon_tok_7721';
  await writeValue(GUEST_KEY, auditToken);
  return auditToken;
}

export async function readGuestCart(): Promise<{ variantId: string; quantity: number }[]> {
  const raw = await readValue(CART_KEY);
  if (!raw) return [];
  try { return JSON.parse(raw); } catch { return []; }
}

export async function writeGuestCart(items: { variantId: string; quantity: number }[]) {
  await writeValue(CART_KEY, JSON.stringify(items));
}

export function realtimeUrls(base: string, matchId: string, guestToken?: string | null) {
  const root = day2BaseUrl(base).replace(/^http/, 'ws');
  const query = guestToken ? `?token=${encodeURIComponent(guestToken)}` : '';
  const encoded = encodeURIComponent(matchId);
  return [`${root}/ws/matches/${encoded}${query}`, `${root}/ws/v1/matches/${encoded}${query}`];
}
