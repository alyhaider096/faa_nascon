export type Role = 'super_admin' | 'league_organizer' | 'club_manager' | 'player' | 'viewer';
export type Fixture = { id: string; sport: string; league: string; home: string; away: string; homeId: string; awayId: string; version: number; eventTypes: string[]; events: { id?: string; clock: string; label: string; team: string }[]; pinnedProductId?: string; time: string; status: string; score: string; venue: string };
export type Product = { id: string; name: string; category: string; priceMinor: number; variants: { id: string; label: string; stock: number; priceMinor?: number }[] };

export const DEMO_PASSWORD = 'Nascon@26';
export const ACCOUNTS: { email: string; role: Role; label: string }[] = [
  { email: 'admin@nascon.test', role: 'super_admin', label: 'Platform admin' },
  { email: 'organizer@nascon.test', role: 'league_organizer', label: 'League organizer' },
  { email: 'manager@nascon.test', role: 'club_manager', label: 'Club manager' },
  { email: 'player@nascon.test', role: 'player', label: 'Player' },
  { email: 'viewer@nascon.test', role: 'viewer', label: 'Viewer' },
];

export const FIXTURES: Fixture[] = [
  { id: 'match-001', sport: 'Football', league: 'Capital League', home: 'Falcons FC', away: 'North Stars', homeId: 'team-alpha-1', awayId: 'team-alpha-2', version: 3, eventTypes: ['goal'], events: [{ clock: '58′', label: 'Goal', team: 'Falcons FC' }, { clock: '24′', label: 'Goal', team: 'North Stars' }], pinnedProductId: 'prod-jersey-001', time: 'Today · 15:30', status: 'Live', score: '2 : 1', venue: 'A-01 Arena' },
  { id: 'match-002', sport: 'Basketball', league: 'Capital League', home: 'Falcons Hoops', away: 'Ravens', homeId: 'team-alpha-3', awayId: 'team-alpha-4', version: 0, eventTypes: ['free_throw', 'two_pointer', 'three_pointer'], events: [], time: 'Today · 17:00', status: 'Upcoming', score: '— : —', venue: 'Main Court' },
  { id: 'match-003', sport: 'Cricket', league: 'City Cup', home: 'Alpha XI', away: 'Metro Strikers', homeId: 'team-alpha-5', awayId: 'team-alpha-6', version: 0, eventTypes: ['run', 'wicket'], events: [], time: 'Tomorrow · 10:00', status: 'Upcoming', score: '— : —', venue: 'South Ground' },
];

export const STANDINGS = [
  { team: 'Falcons FC', played: 8, won: 6, drawn: 1, lost: 1, diff: 12, points: 19, status: 'Clinched' },
  { team: 'North Stars', played: 8, won: 5, drawn: 1, lost: 2, diff: 6, points: 16, status: 'Still possible' },
  { team: 'Ravens', played: 8, won: 3, drawn: 2, lost: 3, diff: 1, points: 11, status: 'Still possible' },
  { team: 'Metro City', played: 8, won: 1, drawn: 0, lost: 7, diff: -19, points: 3, status: 'Eliminated' },
];

export const PRODUCTS: Product[] = [
  { id: 'prod-jersey-001', name: 'Falcons home jersey', category: 'APPAREL', priceMinor: 450000, variants: [{ id: 'var-jersey-001-M', label: 'Medium', stock: 1 }, { id: 'var-jersey-001-L', label: 'Large', stock: 5 }] },
  { id: 'prod-scarf-001', name: 'Supporter scarf', category: 'ACCESSORIES', priceMinor: 180000, variants: [{ id: 'var-scarf-001', label: 'One size', stock: 14 }] },
  { id: 'prod-pass-001', name: 'Season digital pass', category: 'DIGITAL', priceMinor: 250000, variants: [{ id: 'var-pass-001', label: 'Digital', stock: 100 }] },
];

export const CLUB = { name: 'Falcons FC', tag: 'CLUB-ALPHA-1', founded: '2018', venue: 'A-01 Arena, Islamabad', staff: ['Head coach · Ayesha Khan', 'Manager · Daniyal Raza', 'Physio · Sana Malik'], roster: [
  { name: 'Hamza Ali', position: 'Goalkeeper', role: 'Captain', number: 1 },
  { name: 'Zara Shah', position: 'Defender', role: 'Starter', number: 4 },
  { name: 'Umar Farooq', position: 'Midfielder', role: 'Vice captain', number: 8 },
  { name: 'Mariam Noor', position: 'Forward', role: 'Starter', number: 10 },
] };

export const formatMoney = (minor: number) => `PKR ${(minor / 100).toFixed(2)}`;
