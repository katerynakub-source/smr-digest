import AsyncStorage from '@react-native-async-storage/async-storage';
import Constants from 'expo-constants';
import { Platform } from 'react-native';

export type Article = {
  id: number;
  kind: 'news' | 'report';
  url: string;
  title: string;
  title_en: string | null;
  excerpt: string | null;
  content?: string | null;
  image: string | null;
  lang: string;
  published_at: string;
  tags: string[];
  bullets: string[] | null;
  ai_model: string | null;
  source: { slug: string; name: string };
  also_in: { id: number; url: string; source: string }[];
  snippet?: string;
};

export type Source = {
  slug: string; name: string; url: string; homepage: string | null; kind: string;
  lang: string; builtin: number; enabled: number; articles: number; last_error: string | null; last_fetch: string | null;
};

export type Reactor = {
  slug: string; name: string; reactor_type: string; coolant: string; power_mwe: number | null;
  power_mwt: number | null; stage: string; licensing: string; sites: string; description: string;
  company_name: string; company_slug: string; country: string; news?: Article[];
};

export type Company = {
  slug: string; name: string; country: string; founded: number; kind: string; website: string;
  description: string; reactors: number | Reactor[]; news?: Article[];
};

export type Tender = {
  id: string; source: string; region: string; title: string; subject: string | null; buyer: string;
  country: string; published: string | null; deadline: string | null;
  kind: 'Tender' | 'Awarded' | 'Prior information' | 'Early engagement'; category: string; value: number | null; url: string;
};

export type TenderList = { generated_at: string; tenders: Tender[]; errors: Record<string, string> };

export type Answer = { answer: string; passages: { n: number; text: string }[]; ai_model: string };

const KEY_BASE = 'apiBase';

/** Dev default: the machine running Metro (works on simulators and on a phone in the same Wi-Fi). */
function defaultBase(): string {
  const host = Constants.expoConfig?.hostUri?.split(':')[0];
  if (Platform.OS === 'web') return `http://${typeof window !== 'undefined' ? window.location.hostname : 'localhost'}:8000`;
  if (host) return `http://${host}:8000`;
  return Platform.OS === 'android' ? 'http://10.0.2.2:8000' : 'http://localhost:8000';
}

let base: string | null = null;

export async function getBase(): Promise<string> {
  if (!base) base = (await AsyncStorage.getItem(KEY_BASE)) || defaultBase();
  return base;
}

export async function setBase(url: string) {
  base = url.replace(/\/+$/, '') || defaultBase();
  await AsyncStorage.setItem(KEY_BASE, base);
}

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const r = await fetch(`${await getBase()}/api${path}`, {
    ...init,
    headers: init?.body && !(init.body instanceof FormData) ? { 'Content-Type': 'application/json', ...init?.headers } : init?.headers,
  });
  if (!r.ok) {
    let msg = `HTTP ${r.status}`;
    try { msg = (await r.json()).detail ?? msg; } catch {}
    throw new Error(typeof msg === 'string' ? msg : JSON.stringify(msg));
  }
  return r.status === 204 ? (undefined as T) : r.json();
}

const qs = (p: Record<string, string | number | undefined | null>) =>
  Object.entries(p).filter(([, v]) => v != null && v !== '').map(([k, v]) => `${k}=${encodeURIComponent(String(v))}`).join('&');

const serverApi = {
  health: () => req<{ ok: boolean; ai: boolean; model: string; generated_at?: string }>('/health'),
  articles: (p: { category?: string; source?: string; kind?: string; before?: string; limit?: number }) =>
    req<Article[]>(`/articles?${qs(p)}`),
  article: (id: number) => req<Article>(`/articles/${id}`),
  digest: (id: number, force = false) => req<Article>(`/articles/${id}/digest?force=${force}`, { method: 'POST' }),
  ask: (id: number, question: string) => req<Answer>(`/articles/${id}/ask`, { method: 'POST', body: JSON.stringify({ question }) }),
  search: (q: string) => req<Article[]>(`/search?${qs({ q })}`),
  refresh: () => req<{ status: string; new?: number }>('/refresh', { method: 'POST' }),
  sources: () => req<Source[]>('/sources'),
  addSource: (url: string) => req<Source & { articles: number }>('/sources', { method: 'POST', body: JSON.stringify({ url }) }),
  toggleSource: (slug: string, enabled: boolean) =>
    req(`/sources/${slug}`, { method: 'PATCH', body: JSON.stringify({ enabled }) }),
  deleteSource: (slug: string) => req(`/sources/${slug}`, { method: 'DELETE' }),
  reactors: (p: { stage?: string; q?: string } = {}) => req<Reactor[]>(`/catalog/reactors?${qs(p)}`),
  reactor: (slug: string) => req<Reactor>(`/catalog/reactors/${slug}`),
  companies: () => req<Company[]>('/catalog/companies'),
  company: (slug: string) => req<Company & { reactors: Reactor[] }>(`/catalog/companies/${slug}`),
  alerts: (token: string) => req<string[]>(`/alerts?${qs({ token })}`),
  addAlert: (token: string, keyword: string) =>
    req<string[]>('/alerts', { method: 'POST', body: JSON.stringify({ token, keyword }) }),
  deleteAlert: (token: string, keyword: string) => req<string[]>(`/alerts?${qs({ token, keyword })}`, { method: 'DELETE' }),
  reportFromUrl: (url: string) => req<{ id: number }>('/reports/url', { method: 'POST', body: JSON.stringify({ url }) }),
  tenders: () => req<TenderList>('/tenders'),
  uploadReport: (form: FormData) => req<{ id: number }>('/reports/upload', { method: 'POST', body: form }),
};

import { DATA_URL, staticApi } from './staticApi';

/** true in the free GitHub Pages build: data comes from published JSON files, not a server. */
export const STATIC = !!DATA_URL;
export const api: typeof serverApi = STATIC ? (staticApi as unknown as typeof serverApi) : serverApi;
