import { router } from 'expo-router';
import { useEffect, useState } from 'react';
import { FlatList, Pressable, StyleSheet, Text, View } from 'react-native';
import { ChipRow, Empty, Loading, plural } from '@/components/ui';
import { api, type Company, type Reactor } from '@/lib/api';
import { power, StageBadge } from '@/components/catalog';
import { fonts, STAGE_LABELS, useTheme } from '@/lib/theme';

const STAGES = [{ key: '', label: 'All stages' }, ...Object.entries(STAGE_LABELS).map(([key, label]) => ({ key, label }))];

export default function Catalog() {
  const t = useTheme();
  const [tab, setTab] = useState<'reactors' | 'companies'>('reactors');
  const [stage, setStage] = useState('');
  const [reactors, setReactors] = useState<Reactor[] | null>(null);
  const [companies, setCompanies] = useState<Company[] | null>(null);
  const [error, setError] = useState('');

  useEffect(() => {
    setReactors(null);
    api.reactors({ stage }).then(setReactors).catch((e) => setError(e.message));
  }, [stage]);
  useEffect(() => { api.companies().then(setCompanies).catch((e) => setError(e.message)); }, []);

  return (
    <View style={{ flex: 1 }}>
      <View style={[s.segment, { backgroundColor: t.faint }]}>
        {(['reactors', 'companies'] as const).map((k) => (
          <Pressable key={k} onPress={() => setTab(k)} style={[s.segBtn, tab === k && { backgroundColor: t.card }]}>
            <Text style={{ color: tab === k ? t.text : t.muted, fontWeight: '600' }}>{k === 'reactors' ? 'Reactors' : 'Companies'}</Text>
          </Pressable>
        ))}
      </View>
      {error && !reactors ? <Empty title="Cannot reach the server" hint={error} /> : tab === 'reactors' ? (
        <>
          <View><ChipRow items={STAGES} value={stage} onChange={setStage} /></View>
          {!reactors ? <Loading /> : (
            <FlatList
              data={reactors}
              keyExtractor={(r) => r.slug}
              contentContainerStyle={{ paddingBottom: 24 }}
              ListEmptyComponent={<Empty title="No projects at this stage" />}
              renderItem={({ item: r }) => (
                <Pressable onPress={() => router.push({ pathname: '/reactor/[slug]', params: { slug: r.slug } })}
                  style={[s.row, { borderBottomColor: t.faint }]}>
                  <View style={{ flex: 1 }}>
                    <Text style={[s.name, { color: t.text }]}>{r.name}</Text>
                    <Text style={{ color: t.muted, marginTop: 2 }}>{r.company_name} · {r.country}</Text>
                    <Text style={{ color: t.muted, marginTop: 6, fontSize: 13 }}>
                      {r.reactor_type} · {r.coolant} · <Text style={{ color: t.text, fontWeight: '600' }}>{power(r)}</Text>
                    </Text>
                  </View>
                  <StageBadge stage={r.stage} />
                </Pressable>
              )}
            />
          )}
        </>
      ) : !companies ? <Loading /> : (
        <FlatList
          data={companies}
          keyExtractor={(c) => c.slug}
          contentContainerStyle={{ paddingBottom: 24, paddingTop: 8 }}
          renderItem={({ item: c }) => (
            <Pressable onPress={() => router.push({ pathname: '/company/[slug]', params: { slug: c.slug } })}
              style={[s.row, { borderBottomColor: t.faint }]}>
              <View style={{ flex: 1 }}>
                <Text style={[s.name, { color: t.text }]}>{c.name}</Text>
                <Text style={{ color: t.muted, marginTop: 2 }}>
                  {c.country} · {c.kind} · {c.reactors as number} {plural(c.reactors as number, 'project', 'projects', 'projects')}
                </Text>
              </View>
            </Pressable>
          )}
        />
      )}
    </View>
  );
}

const s = StyleSheet.create({
  segment: { flexDirection: 'row', margin: 16, marginBottom: 4, borderRadius: 10, padding: 3 },
  segBtn: { flex: 1, alignItems: 'center', paddingVertical: 8, borderRadius: 8 },
  row: { flexDirection: 'row', alignItems: 'flex-start', gap: 12, paddingHorizontal: 16, paddingVertical: 14, borderBottomWidth: StyleSheet.hairlineWidth },
  name: { fontSize: 17, fontWeight: '600', fontFamily: fonts.serif },
});
