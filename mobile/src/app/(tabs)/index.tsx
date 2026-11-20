import { useCallback, useEffect, useRef, useState } from 'react';
import { ActivityIndicator, FlatList, RefreshControl, Text, View } from 'react-native';
import { ArticleCard, ChipRow, Empty, Loading } from '@/components/ui';
import { api, type Article } from '@/lib/api';
import { cacheFeed, cachedFeed } from '@/lib/offline';
import { useTheme } from '@/lib/theme';

const CATS = [
  { key: '', label: 'All' },
  { key: 'smr', label: 'SMR' },
  { key: 'tech', label: 'Technology' },
  { key: 'startups', label: 'Companies' },
  { key: 'policy', label: 'Policy' },
  { key: 'supply', label: 'Supply chain' },
];

export default function Feed() {
  const t = useTheme();
  const [cat, setCat] = useState('');
  const [items, setItems] = useState<Article[] | null>(null);
  const [offline, setOffline] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [more, setMore] = useState(false);
  const done = useRef(false);

  const load = useCallback(async (category: string) => {
    done.current = false;
    try {
      const data = await api.articles({ category, limit: 25 });
      setItems(data);
      setOffline(false);
      cacheFeed(category || 'all', data);
    } catch {
      setItems(await cachedFeed(category || 'all'));
      setOffline(true);
    }
  }, []);

  useEffect(() => { setItems(null); load(cat); }, [cat, load]);

  const onRefresh = async () => {
    setRefreshing(true);
    try { await api.refresh(); } catch {}
    await load(cat);
    setRefreshing(false);
  };

  const loadMore = async () => {
    if (!items?.length || more || done.current || offline) return;
    setMore(true);
    try {
      const next = await api.articles({ category: cat, limit: 25, before: items[items.length - 1].published_at });
      if (next.length < 25) done.current = true;
      setItems((prev) => [...(prev || []), ...next.filter((n) => !prev?.some((p) => p.id === n.id))]);
    } finally {
      setMore(false);
    }
  };

  return (
    <View style={{ flex: 1 }}>
      <View><ChipRow items={CATS} value={cat} onChange={setCat} /></View>
      {offline ? (
        <Text style={{ color: t.muted, textAlign: 'center', fontSize: 12, paddingBottom: 6 }}>
          Offline: showing a saved copy of the feed
        </Text>
      ) : null}
      {items === null ? <Loading /> : (
        <FlatList
          data={items}
          keyExtractor={(a) => String(a.id)}
          renderItem={({ item }) => <ArticleCard a={item} />}
          contentContainerStyle={{ paddingTop: 4, paddingBottom: 24, flexGrow: 1 }}
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={t.muted} />}
          onEndReached={loadMore}
          onEndReachedThreshold={0.5}
          ListFooterComponent={more ? <ActivityIndicator style={{ margin: 16 }} color={t.muted} /> : undefined}
          ListEmptyComponent={<Empty title="Nothing here yet" hint={offline ? 'No connection to the server and no saved copy.' : 'Pull down to refresh the sources.'} />}
        />
      )}
    </View>
  );
}
