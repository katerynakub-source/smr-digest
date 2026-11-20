import { useEffect, useState } from 'react';
import { FlatList, StyleSheet, TextInput, View } from 'react-native';
import { ArticleCard, Chip, Empty, Loading } from '@/components/ui';
import { api, type Article } from '@/lib/api';
import { useFavorites } from '@/lib/offline';
import { useTheme } from '@/lib/theme';

const SUGGEST = ['BWRX-300', 'NuScale', 'RITM-200', 'fusion', 'licensing', 'HALEU', 'Rolls-Royce SMR'];

export default function Search() {
  const t = useTheme();
  const favs = useFavorites();
  const [q, setQ] = useState('');
  const [res, setRes] = useState<Article[] | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const query = q.trim();
    if (query.length < 2) { setRes(null); return; }
    setLoading(true);
    const h = setTimeout(async () => {
      try {
        setRes(await api.search(query));
      } catch {
        // offline: search inside saved articles
        const ql = query.toLowerCase();
        setRes(favs.filter((a) => [a.title, a.title_en, a.content, ...(a.bullets || [])].join(' ').toLowerCase().includes(ql)));
      } finally {
        setLoading(false);
      }
    }, 250);
    return () => clearTimeout(h);
  }, [q, favs]);

  return (
    <View style={{ flex: 1 }}>
      <TextInput
        value={q}
        onChangeText={setQ}
        placeholder="Articles, reports, reactors, companies…"
        placeholderTextColor={t.muted}
        autoCorrect={false}
        clearButtonMode="while-editing"
        style={[s.input, { color: t.text, backgroundColor: t.card, borderColor: t.faint }]}
      />
      {res === null && !loading ? (
        <View style={s.suggest}>
          {SUGGEST.map((x) => <Chip key={x} label={x} onPress={() => setQ(x)} />)}
        </View>
      ) : loading && !res ? <Loading /> : (
        <FlatList
          data={res ?? []}
          keyExtractor={(a) => String(a.id)}
          renderItem={({ item }) => <ArticleCard a={item} compact />}
          keyboardDismissMode="on-drag"
          contentContainerStyle={{ paddingBottom: 24, flexGrow: 1 }}
          ListEmptyComponent={<Empty title="Nothing found" hint="Try a different spelling or keyword." />}
        />
      )}
    </View>
  );
}

const s = StyleSheet.create({
  input: { margin: 16, marginBottom: 12, paddingHorizontal: 14, paddingVertical: 12, borderRadius: 12, fontSize: 16, borderWidth: StyleSheet.hairlineWidth },
  suggest: { flexDirection: 'row', flexWrap: 'wrap', gap: 8, paddingHorizontal: 16 },
});
