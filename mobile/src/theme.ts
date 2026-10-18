import { Platform } from 'react-native';

// Mock tenant branding is data, so a real tenant response can replace it later.
// The warm accent is a LeagueOps demo choice; live tenant marks use server branding.
export const TENANT = { name: 'Tenant Alpha', logoText: 'A', primary: '#FFA980' };
export const DISPLAY_FONT = Platform.select({ android: 'sans-serif-condensed', default: 'Arial' }) ?? 'Arial';
export const C = {
  bg: '#0B1220', surface: '#142031', surface2: '#1D2C40', line: '#40516A',
  text: '#F7FAFF', muted: '#C1CDDD', accent: TENANT.primary, accentDark: '#814538',
  gold: '#FFCC74', danger: '#FF9999', blue: '#91C9EF',
};
