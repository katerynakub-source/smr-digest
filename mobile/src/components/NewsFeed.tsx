import { useCallback, useEffect, useRef, useState } from 'react';
import { ActivityIndicator, FlatList, RefreshControl, Text, View } from 'react-native';
import { ArticleCard, Empty, Loading } from '@/components/ui';
import { api, type Article, type ViewMode } from '@/lib/api';
import { cacheFeed, cachedFeed } from '@/lib/offline';
import { useTheme } from '@/lib/theme';

/** One news tab: a section (smr | large | supply) in English, or a language (ru) in the original. */
export function NewsFeed({ section, lang, mode = 'en', intro }: {
  section?: string; lang?: string; mode?: ViewMode; intro?: string;
}) {
  const t = useTheme();
  const key = section || `lang-${lang}`;
  const [items, setItems] = useState<Article[] | null>(null);
  const [offline, setOffline] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [more, setMore] = useState(false);
  const done = useRef(false);

  const load = useCallback(async () => {
    done.current = false;
    try {
      const data = await api.articles({ section, lang, limit: 25 });
      setItems(data);
      setOffline(false);
      cacheFeed(key, data);
    } catch {
      setItems(await cachedFeed(key));
      setOffline(true);
    }
  }, [section, lang, key]);

  useEffect(() => { load(); }, [load]);

  const onRefresh = async () => {
    setRefreshing(true);
    try { await api.refresh(); } catch {}
    await load();
    setRefreshing(false);
  };

  const loadMore = async () => {
    if (!items?.length || more || done.current || offline) return;
    setMore(true);
    try {
      const next = await api.articles({ section, lang, limit: 25, before: items[items.length - 1].published_at });
      if (next.length < 25) done.current = true;
      setItems((prev) => [...(prev || []), ...next.filter((n) => !prev?.some((p) => p.id === n.id))]);
    } finally {
      setMore(false);
    }
  };

  if (items === null) return <Loading />;
  return (
    <FlatList
      data={items}
      keyExtractor={(a) => String(a.id)}
      renderItem={({ item }) => <ArticleCard a={item} mode={mode} />}
      contentContainerStyle={{ paddingTop: 4, paddingBottom: 24, flexGrow: 1 }}
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={t.muted} />}
      onEndReached={loadMore}
      onEndReachedThreshold={0.5}
      ListHeaderComponent={
        <View>
          {intro ? <Text style={{ color: t.muted, fontSize: 12, paddingHorizontal: 16, paddingVertical: 8 }}>{intro}</Text> : null}
          {offline ? (
            <Text style={{ color: t.muted, textAlign: 'center', fontSize: 12, paddingBottom: 6 }}>
              Offline: showing a saved copy
            </Text>
          ) : null}
        </View>
      }
      ListFooterComponent={more ? <ActivityIndicator style={{ margin: 16 }} color={t.muted} /> : undefined}
      ListEmptyComponent={<Empty title="Nothing here yet" hint={offline ? 'No connection and no saved copy.' : 'New items arrive with the next update.'} />}
    />
  );
}
