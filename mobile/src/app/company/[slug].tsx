import { router, Stack, useLocalSearchParams } from 'expo-router';
import { useEffect, useState } from 'react';
import { Linking, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { Facts, power, StageBadge } from '@/components/catalog';
import { ArticleCard, Empty, Loading, SectionTitle } from '@/components/ui';
import { api, type Company, type Reactor } from '@/lib/api';
import { fonts, useTheme } from '@/lib/theme';

export default function CompanyScreen() {
  const t = useTheme();
  const { slug } = useLocalSearchParams<{ slug: string }>();
  const [c, setC] = useState<(Company & { reactors: Reactor[] }) | null>(null);
  const [err, setErr] = useState('');
  useEffect(() => { api.company(slug).then(setC).catch((e) => setErr(e.message)); }, [slug]);
  if (err) return <Empty title="Could not load" hint={err} />;
  if (!c) return <Loading />;
  return (
    <ScrollView contentContainerStyle={{ paddingBottom: 40 }}>
      <Stack.Screen options={{ title: c.name }} />
      <View style={{ padding: 16 }}>
        <Text style={[s.h1, { color: t.text }]}>{c.name}</Text>
        <Text style={{ color: t.text, marginTop: 10, fontSize: 15, lineHeight: 22 }}>{c.description}</Text>
      </View>
      <Facts rows={[['Country', c.country], ['Founded', c.founded], ['Type', c.kind], ['Website', c.website?.replace(/^https?:\/\//, '')]]} />
      {c.website ? (
        <Pressable onPress={() => Linking.openURL(c.website)}>
          <Text style={{ color: t.accent, paddingHorizontal: 16, paddingTop: 10 }}>Visit website →</Text>
        </Pressable>
      ) : null}
      <SectionTitle>Reactors</SectionTitle>
      {c.reactors.map((r) => (
        <Pressable key={r.slug} onPress={() => router.push({ pathname: '/reactor/[slug]', params: { slug: r.slug } })}
          style={[s.row, { borderBottomColor: t.faint }]}>
          <View style={{ flex: 1 }}>
            <Text style={{ color: t.text, fontSize: 16, fontWeight: '600' }}>{r.name}</Text>
            <Text style={{ color: t.muted, marginTop: 3, fontSize: 13 }}>{r.reactor_type} · {r.coolant} · {power(r)}</Text>
          </View>
          <StageBadge stage={r.stage} />
        </Pressable>
      ))}
      <SectionTitle>News feed</SectionTitle>
      {c.news?.length ? c.news.map((a) => <ArticleCard key={a.id} a={a} compact />) :
        <Text style={{ color: t.muted, paddingHorizontal: 16 }}>No publications in the loaded sources yet.</Text>}
    </ScrollView>
  );
}

const s = StyleSheet.create({
  h1: { fontSize: 28, fontWeight: '700', fontFamily: fonts.serif },
  row: { flexDirection: 'row', gap: 12, paddingHorizontal: 16, paddingVertical: 12, borderBottomWidth: StyleSheet.hairlineWidth },
});
