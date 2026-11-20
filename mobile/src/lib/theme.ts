import { Platform, useColorScheme } from 'react-native';

const light = {
  bg: '#FBFAF7',
  card: '#FFFFFF',
  text: '#16181D',
  muted: '#6B6F78',
  faint: '#E8E6E1',
  accent: '#0F6E5C', // calm "reactor teal"
  accentSoft: '#E3F1ED',
  danger: '#B42318',
};
const dark: typeof light = {
  bg: '#111214',
  card: '#1A1B1F',
  text: '#ECEBE8',
  muted: '#9A9DA4',
  faint: '#2A2C31',
  accent: '#4FC1A6',
  accentSoft: '#1D2E2A',
  danger: '#F97066',
};

export type Theme = typeof light;

export function useTheme(): Theme {
  return useColorScheme() === 'dark' ? dark : light;
}

/** Reading typography: serif body, generous line height (Particle/Artifact-style). */
export const fonts = {
  serif: Platform.select({ ios: 'Georgia', android: 'serif', default: 'Georgia, serif' }),
  sans: Platform.select({ ios: 'System', android: 'sans-serif', default: 'system-ui, -apple-system, sans-serif' }),
};

export const CATEGORY_LABELS: Record<string, string> = {
  smr: 'SMR',
  tech: 'Technology',
  startups: 'Companies',
  policy: 'Policy',
};

export const STAGE_LABELS: Record<string, string> = {
  concept: 'Concept',
  design: 'Design',
  licensing: 'Licensing',
  construction: 'Construction',
  operation: 'Operation',
};

export function formatDate(iso: string): string {
  const d = new Date(iso);
  const diffH = (Date.now() - d.getTime()) / 36e5;
  if (diffH < 1) return 'just now';
  if (diffH < 24) return `${Math.floor(diffH)}h ago`;
  return d.toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: diffH > 24 * 300 ? 'numeric' : undefined });
}
