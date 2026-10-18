import { Fixture, Product, Role } from './mock';

export type User = { user_id: string; email: string; role: Role; display_name: string; tenant_id: string | null; league_id: string | null; club_id: string | null; player_id: string | null };
export type Tenant = { name: string; tenant_id: string; branding: { display_name?: string; logo_url?: string; primary_color?: string; secondary_color?: string } };
export type League = { league_id: string; name: string; sport_id: string };
export type ServerProduct = { product_id: string; name: string; category: string; pinned_match_id?: string; variants: { variant_id: string; attributes: Record<string, string>; price_minor: number; stock: number }[] };
export type ClubProfile = { name: string; tag: string; founded: string; venue: string; staff: string[]; roster: { id?: string; name: string; position: string; number: number | string; role: string }[] };
export type Bootstrap = { user: User; tenant: Tenant | null; leagues: League[]; clubs: { club_id: string; name: string }[]; products: ServerProduct[]; fixtures?: { match_id: string }[] };
export type Projection = { match_id: string; sport_id: string; league_id: string; status: string; version: number; home: { team_id: string; score: number; wickets?: number | null; overs?: string | null }; away: { team_id: string; score: number; wickets?: number | null; overs?: string | null }; scoring_events?: Record<string, unknown>; events: { event_id: string; sequence: number; type: string; payload: { team_id?: string; event_type?: string }; compensated: boolean }[] };
export type RosterHistory = { player_id: string; league_id: string; current_squad_id: string | null; parent_squad_id: string | null; history: unknown[] };
export class ApiError extends Error { constructor(message: string, public status: number, public code?: string) { super(message); } }

export async function request<T>(base: string, path: string, token: string | null, body?: unknown, method: 'GET' | 'POST' | 'DELETE' = body === undefined ? 'GET' : 'POST'): Promise<T> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 12000);
  try {
    const response = await fetch(`${base}${path}`, { method, signal: controller.signal,
      headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}) },
      ...(body === undefined ? {} : { body: JSON.stringify(body) }) });
    const data = await response.json().catch(() => null);
    if (!response.ok) throw new ApiError(response.status === 403 ? 'Not allowed. Your role cannot perform this action.' : data?.error?.message || (response.status === 401 ? 'Please sign in again.' : 'The server could not complete this request.'), response.status, data?.error?.code);
    if (data === null) throw new ApiError('The server returned an unreadable response.', response.status);
    return data as T;
  } catch (error) {
    if (error instanceof ApiError) throw error;
    throw new ApiError('Cannot reach the server. Check the hotspot and server address, then retry.', 0);
  } finally { clearTimeout(timer); }
}

export const productFromServer = (p: ServerProduct): Product => ({ id: p.product_id, name: p.name, category: p.category,
  priceMinor: p.variants[0]?.price_minor ?? 0, variants: p.variants.map(v => ({ id: v.variant_id, label: Object.values(v.attributes).join(' · ') || v.variant_id, stock: v.stock, priceMinor: v.price_minor })) });
export function matchFromServer(p: Projection, old?: Fixture): Fixture {
  const score = (side: Projection['home']) => `${side.score}${side.wickets == null ? '' : `/${side.wickets} (${side.overs} ov)`}`;
  return { id: p.match_id, league: old?.league ?? p.league_id, sport: p.sport_id, home: old?.home ?? p.home.team_id, away: old?.away ?? p.away.team_id,
    homeId: p.home.team_id, awayId: p.away.team_id, version: p.version, eventTypes: p.scoring_events ? Object.keys(p.scoring_events) : old?.eventTypes ?? [],
    events: p.events.map(e => ({ id: e.event_id, clock: `#${e.sequence}`, label: `${e.payload.event_type ?? e.type}${e.compensated ? ' (corrected)' : ''}`, team: e.payload.team_id ?? '' })),
    status: p.status === 'in_progress' ? 'Live' : p.status === 'completed' ? 'Completed' : 'Upcoming', score: `${score(p.home)} : ${score(p.away)}`, time: old?.time ?? 'Time not supplied', venue: old?.venue ?? 'Venue not supplied', pinnedProductId: old?.pinnedProductId };
}
