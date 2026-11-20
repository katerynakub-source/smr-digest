/** Favorites with full text kept on-device, plus a cached copy of the last feed for offline start. */
import AsyncStorage from '@react-native-async-storage/async-storage';
import { useCallback, useEffect, useState } from 'react';
import type { Article } from './api';

const FAV = 'favorites:v1';
const FEED = 'feedCache:v1';

type Listener = () => void;
const listeners = new Set<Listener>();
let cache: Record<string, Article> | null = null;

async function load(): Promise<Record<string, Article>> {
  if (!cache) cache = JSON.parse((await AsyncStorage.getItem(FAV)) || '{}');
  return cache!;
}

async function persist() {
  await AsyncStorage.setItem(FAV, JSON.stringify(cache));
  listeners.forEach((l) => l());
}

export async function saveArticle(a: Article) {
  const favs = await load();
  favs[a.id] = { ...a, saved_at: new Date().toISOString() } as Article;
  await persist();
}

export async function removeArticle(id: number) {
  const favs = await load();
  delete favs[id];
  await persist();
}

export async function getSaved(id: number): Promise<Article | undefined> {
  return (await load())[id];
}

export function useFavorites() {
  const [items, setItems] = useState<Article[]>([]);
  const refresh = useCallback(async () => {
    const favs = await load();
    setItems(Object.values(favs).sort((a: any, b: any) => (b.saved_at || '').localeCompare(a.saved_at || '')));
  }, []);
  useEffect(() => {
    refresh();
    listeners.add(refresh);
    return () => { listeners.delete(refresh); };
  }, [refresh]);
  return items;
}

export function useIsSaved(id: number) {
  const favs = useFavorites();
  return favs.some((a) => a.id === id);
}

export async function cacheFeed(key: string, items: Article[]) {
  await AsyncStorage.setItem(`${FEED}:${key}`, JSON.stringify(items.slice(0, 60)));
}

export async function cachedFeed(key: string): Promise<Article[]> {
  return JSON.parse((await AsyncStorage.getItem(`${FEED}:${key}`)) || '[]');
}
