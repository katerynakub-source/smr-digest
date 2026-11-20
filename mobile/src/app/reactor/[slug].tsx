import { router, Stack, useLocalSearchParams } from 'expo-router';
import { useEffect, useState } from 'react';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { Facts, StageBadge } from '@/components/catalog';
import { ArticleCard, Empty, Loading, SectionTitle } from '@/components/ui';
import { api, type Reactor } from '@/lib/api';
import { fonts, useTheme } from '@/lib/theme';

export default function ReactorScreen() {
  const t = useTheme();
  const { slug } = useLocalSearchParams<{ slug: string }>();
  const [r, setR] = useState<Reactor | null>(null);
  const [err, setErr] = useState('');
  useEffect(() => { api.reactor(slug).then(setR).catch((e) => setErr(e.message)); }, [slug]);
  if (err) return <Empty title="Could not load" hint={err} />;
  if (!r) return <Loading />;
  return (
    <ScrollView contentContainerStyle={{ paddingBottom: 40 }}>
      <Stack.Screen options={{ title: r.name }} />
      <View style={s.head}>
        <Text style={[s.h1, { color: t.text }]}>{r.name}</Text>
        <Pressable onPress={() => router.push({ pathname: '/company/[slug]', params: { slug: r.company_slug } })}>
          <Text style={{ color: t.accent, fontSize: 16, marginTop: 4 }}>{r.company_name} →</Text>
        </Pressable>
        <View style={{ marginTop: 12 }}><StageBadge stage={r.stage} /></View>
        <Text style={{ color: t.text, marginTop: 12, fontSize: 15, lineHeight: 22 }}>{r.description}</Text>
      </View>
      <SectionTitle>Specifications</SectionTitle>
      <Facts rows={[
        ['Type', r.reactor_type],
        ['Coolant', r.coolant],
        ['Electric power', r.power_mwe ? `${r.power_mwe} MWe` : null],
        ['Thermal power', r.power_mwt ? `${r.power_mwt} MWt` : null],
        ['Sites', r.sites],
        ['Country', r.country],
      ]} />
      <SectionTitle>Licensing</SectionTitle>
      <Text style={{ color: t.text, paddingHorizontal: 16, fontSize: 15, lineHeight: 22 }}>{r.licensing}</Text>
      <Text style={{ color: t.muted, paddingHorizontal: 16, fontSize: 12, marginTop: 6 }}>
        Check against IAEA ARIS and the feed below — statuses change quickly.
      </Text>
      <SectionTitle>Project news</SectionTitle>
      {r.news?.length ? r.news.map((a) => <ArticleCard key={a.id} a={a} compact />) :
        <Text style={{ color: t.muted, paddingHorizontal: 16 }}>No publications in the loaded sources yet.</Text>}
    </ScrollView>
  );
}

const s = StyleSheet.create({
  head: { padding: 16 },
  h1: { fontSize: 28, fontWeight: '700', fontFamily: fonts.serif },
});
