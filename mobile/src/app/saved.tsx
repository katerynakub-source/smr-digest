import { FlatList, Text, View } from 'react-native';
import { ArticleCard, Empty } from '@/components/ui';
import { useFavorites } from '@/lib/offline';
import { useTheme } from '@/lib/theme';

export default function Saved() {
  const t = useTheme();
  const items = useFavorites();
  return (
    <View style={{ flex: 1 }}>
      <FlatList
        data={items}
        keyExtractor={(a) => String(a.id)}
        renderItem={({ item }) => <ArticleCard a={item} compact />}
        ListHeaderComponent={items.length ? (
          <Text style={{ color: t.muted, fontSize: 13, paddingHorizontal: 16, paddingVertical: 12 }}>
            Stored in full on this device — available offline.
          </Text>
        ) : undefined}
        contentContainerStyle={{ paddingBottom: 24, flexGrow: 1 }}
        ListEmptyComponent={<Empty title="Saved items will appear here" hint="Tap the bookmark on an article or report — the text and AI digest are saved for offline reading." />}
      />
    </View>
  );
}
