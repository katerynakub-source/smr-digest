/**
 * Serverless data layer: reads the JSON files that the scheduled GitHub Action publishes
 * (articles.json, catalog.json, meta.json) and answers the same calls as the server API.
 * Enabled when EXPO_PUBLIC_DATA_URL is set at build time.
 */
import AsyncStorage from '@react-native-async-storage/async-storage';
import type { Answer, Article, Company, Reactor, Source, TenderList } from './api';

export const DATA_URL = (process.env.EXPO_PUBLIC_DATA_URL || '').replace(/\/+$/, '');

type Meta = { generated_at: string; ai: boolean; model: string; sources: Source[] };
type StaticReactor = Reactor & { news_ids: number[] };
type StaticCompany = Company & { reactor_slugs: string[]; news_ids: number[] };
type Data = {
  articles: Article[];
  byId: Map<number, Article>;
  dupToCanon: Map<number, number>;
  reactors: StaticReactor[];
  companies: StaticCompany[];
  meta: Meta;
};

const CACHE = 'staticData:v1';
let data: Promise<Data> | null = null;

async function getJson<T>(name: string): Promise<T> {
  const r = await fetch(`${DATA_URL}/${name}?t=${Date.now()}`, { cache: 'no-store' });
  if (!r.ok) throw new Error(`Could not load ${name} (HTTP ${r.status})`);
  return r.json();
}

function build(raw: { a: any; c: any; m: Meta }): Data {
  const articles: Article[] = raw.a.articles;
  const dupToCanon = new Map<number, number>(raw.a.duplicates.map((d: any) => [d.id, d.cluster_id]));
  return {
    articles,
    byId: new Map(articles.map((a) => [a.id, a])),
    dupToCanon,
    reactors: raw.c.reactors,
    companies: raw.c.companies,
    meta: raw.m,
  };
}

async function download(): Promise<Data> {
  try {
    const [a, c, m] = await Promise.all([getJson<any>('articles.json'), getJson<any>('catalog.json'), getJson<Meta>('meta.json')]);
    AsyncStorage.setItem(CACHE, JSON.stringify({ a, c, m })).catch(() => {}); // offline copy (may exceed quota on web)
    return build({ a, c, m });
  } catch (e) {
    const cached = await AsyncStorage.getItem(CACHE);
    if (cached) return build(JSON.parse(cached));
    throw e;
  }
}

function load(force = false): Promise<Data> {
  if (!data || force) {
    data = download();
    data.catch(() => { data = null; });
  }
  return data;
}

const strip = (a: Article): Article => ({ ...a, content: undefined });

function norm(s: string) {
  return s.toLowerCase().normalize('NFKD').replace(/[̀-ͯ]/g, '');
}

function searchArticles(d: Data, q: string): Article[] {
  const terms = norm(q).split(/[^\p{L}\p{N}-]+/u).filter((t) => t.length > 1);
  if (!terms.length) return [];
  const scored: [number, Article][] = [];
  for (const a of d.articles) {
    const title = norm(`${a.title} ${a.title_en || ''}`);
    const body = norm(`${a.excerpt || ''} ${(a.bullets || []).join(' ')} ${a.content || ''}`);
    let score = 0;
    for (const t of terms) {
      const inTitle = title.includes(t), inBody = body.includes(t);
      if (!inTitle && !inBody) { score = 0; break; }
      score += (inTitle ? 8 : 0) + (inBody ? 1 : 0);
    }
    if (score) scored.push([score, a]);
  }
  scored.sort((x, y) => y[0] - x[0] || y[1].published_at.localeCompare(x[1].published_at));
  return scored.slice(0, 50).map(([, a]) => {
    const text = a.content || a.excerpt || '';
    const i = norm(text).indexOf(terms[0]);
    const snippet = i >= 0 ? `…${text.slice(Math.max(0, i - 60), i + 120)}…` : undefined;
    return { ...strip(a), snippet };
  });
}

const notAvailable = (what: string) => Promise.reject(new Error(`${what} needs the server version of the app`));

export const staticApi = {
  health: async () => {
    const d = await load();
    return { ok: true, ai: d.meta.ai, model: d.meta.model, generated_at: d.meta.generated_at };
  },
  articles: async (p: { category?: string; source?: string; kind?: string; before?: string; limit?: number }) => {
    const d = await load();
    return d.articles
      .filter((a) => (p.kind || 'news') === a.kind)
      .filter((a) => !p.category || a.tags.includes(p.category))
      .filter((a) => !p.source || a.source.slug === p.source)
      .filter((a) => !p.before || a.published_at < p.before)
      .slice(0, p.limit || 30)
      .map(strip);
  },
  article: async (id: number) => {
    const d = await load();
    const a = d.byId.get(d.dupToCanon.get(id) ?? id);
    if (!a) throw new Error('This item is no longer in the archive');
    return a;
  },
  digest: async (id: number, _force = false) => staticApi.article(id),
  ask: (_id: number, _q: string): Promise<Answer> => notAvailable('Asking AI about a text'),
  search: async (q: string) => searchArticles(await load(), q),
  refresh: async () => {
    const before = (await load()).articles.length;
    const d = await load(true);
    return { status: 'ok', new: Math.max(0, d.articles.length - before) };
  },
  sources: async () => (await load()).meta.sources,
  addSource: (_url: string): Promise<Source & { articles: number }> => notAvailable('Adding sources from the app'),
  toggleSource: (_slug: string, _enabled: boolean) => notAvailable('Turning sources on/off'),
  deleteSource: (_slug: string) => notAvailable('Deleting sources'),
  reactors: async (p: { stage?: string; q?: string; size?: string } = {}) =>
    (await load()).reactors.filter((r) => (!p.stage || r.stage === p.stage) && (!p.size || r.size === p.size)) as Reactor[],
  reactor: async (slug: string) => {
    const d = await load();
    const r = d.reactors.find((x) => x.slug === slug);
    if (!r) throw new Error('Reactor not found');
    return { ...r, news: r.news_ids.map((i) => d.byId.get(i)).filter(Boolean).map((a) => strip(a!)) } as Reactor;
  },
  companies: async () =>
    (await load()).companies.map((c) => ({ ...c, reactors: c.reactor_slugs.length })) as Company[],
  company: async (slug: string) => {
    const d = await load();
    const c = d.companies.find((x) => x.slug === slug);
    if (!c) throw new Error('Company not found');
    return {
      ...c,
      reactors: d.reactors.filter((r) => c.reactor_slugs.includes(r.slug)),
      news: c.news_ids.map((i) => d.byId.get(i)).filter(Boolean).map((a) => strip(a!)),
    } as Company & { reactors: Reactor[] };
  },
  alerts: async (_token: string) => [] as string[],
  addAlert: (_t: string, _k: string): Promise<string[]> => notAvailable('Keyword alerts'),
  deleteAlert: async (_t: string, _k: string) => [] as string[],
  reportFromUrl: (_url: string): Promise<{ id: number }> => notAvailable('Importing PDF reports'),
  tenders: () => getJson<TenderList>('tenders.json'),
  uploadReport: (_f: FormData): Promise<{ id: number }> => notAvailable('Importing PDF reports'),
};
