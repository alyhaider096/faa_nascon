import { Platform } from 'react-native';

// Mock tenant branding is data, so a real tenant response can replace it later.
// The warm accent is a LeagueOps demo choice; live tenant marks use server branding.
export const TENANT = { name: 'Tenant Alpha', logoText: 'A', primary: '#F29A7B' };
export const DISPLAY_FONT = Platform.select({ android: 'sans-serif-condensed', default: 'Arial' }) ?? 'Arial';
export const C = {
  bg: '#0E0F11', surface: '#1B2025', surface2: '#29333B', line: '#3A454E',
  text: '#F1F1F0', muted: '#B8C0C6', accent: TENANT.primary, accentDark: '#814538',
  gold: '#FFCC74', danger: '#FF9999', blue: '#91C9EF',
};
