import Ionicons from '@expo/vector-icons/Ionicons';
import { useEffect, useMemo, useState } from 'react';
import { FlatList, Linking, Pressable, RefreshControl, StyleSheet, Text, View } from 'react-native';
import { ChipRow, Empty, Loading } from '@/components/ui';
import { api, type Tender, type TenderList } from '@/lib/api';
import { fonts, formatDate, useTheme } from '@/lib/theme';

const IAEA_URL = 'https://www.ungm.org/Public/Notice';

const COUNTRY: Record<string, string> = {
  GBR: 'United Kingdom', FRA: 'France', DEU: 'Germany', ESP: 'Spain', ITA: 'Italy', POL: 'Poland', CZE: 'Czechia',
  SVK: 'Slovakia', HUN: 'Hungary', BGR: 'Bulgaria', ROU: 'Romania', SVN: 'Slovenia', FIN: 'Finland', SWE: 'Sweden',
  BEL: 'Belgium', NLD: 'Netherlands', LTU: 'Lithuania', AUT: 'Austria', HRV: 'Croatia', IRL: 'Ireland',
  DNK: 'Denmark', PRT: 'Portugal', GRC: 'Greece', EST: 'Estonia', LVA: 'Latvia', LUX: 'Luxembourg',
};

const TYPES = [
  { key: 'open', label: 'Open & upcoming' },
  { key: 'awarded', label: 'Awarded' },
  { key: 'all', label: 'All' },
];
const REGIONS = [{ key: '', label: 'All regions' }, { key: 'EU', label: 'EU' }, { key: 'UK', label: 'UK' }];

function daysLeft(deadline: string | null): number | null {
  if (!deadline) return null;
  return Math.ceil((new Date(`${deadline}T23:59:59Z`).getTime() - Date.now()) / 864e5);
}

function money(v: number | null) {
  if (!v) return null;
  return v >= 1e6 ? `£${(v / 1e6).toFixed(v >= 1e7 ? 0 : 1)}M` : v >= 1e3 ? `£${Math.round(v / 1e3)}k` : `£${v}`;
}

function TenderCard({ x }: { x: Tender }) {
  const t = useTheme();
  const left = x.kind === 'Awarded' ? null : daysLeft(x.deadline);
  const badge =
    x.kind === 'Awarded' ? { text: 'Awarded', strong: false } :
    x.kind !== 'Tender' ? { text: x.kind, strong: false } :
    left === null ? { text: 'Open', strong: true } :
    { text: left <= 0 ? 'Closes today' : `Closes in ${left} day${left === 1 ? '' : 's'}`, strong: left <= 14 };
  return (
    <Pressable onPress={() => Linking.openURL(x.url)}
      style={({ pressed }) => [s.card, { backgroundColor: t.card, borderColor: t.faint, opacity: pressed ? 0.85 : 1 }]}>
      <View style={s.row}>
        <Text style={[s.badge, badge.strong ? { color: t.accent, backgroundColor: t.accentSoft } : { color: t.muted, backgroundColor: t.faint }]}>
          {badge.text}
        </Text>
        <Text style={{ color: t.muted, fontSize: 12 }}>{x.source}</Text>
      </View>
      <Text style={[s.title, { color: t.text }]} numberOfLines={3}>{x.title}</Text>
      <Text style={{ color: t.text, marginTop: 6, fontSize: 14 }} numberOfLines={1}>{x.buyer}</Text>
      <Text style={{ color: t.muted, marginTop: 3, fontSize: 13 }} numberOfLines={1}>
        {[COUNTRY[x.country] || x.country, x.category, money(x.value)].filter(Boolean).join(' · ')}
      </Text>
      <Text style={{ color: t.muted, marginTop: 3, fontSize: 12 }}>
        {x.published ? `Published ${formatDate(x.published)}` : ''}
        {x.deadline && x.kind !== 'Awarded' ? ` · Deadline ${new Date(x.deadline).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })}` : ''}
      </Text>
    </Pressable>
  );
}

function IaeaCard() {
  const t = useTheme();
  return (
    <Pressable onPress={() => Linking.openURL(IAEA_URL)} style={[s.card, s.iaea, { borderColor: t.accent }]}>
      <Ionicons name="globe-outline" size={22} color={t.accent} />
      <View style={{ flex: 1 }}>
        <Text style={{ color: t.text, fontWeight: '700', fontSize: 15 }}>IAEA tenders on UNGM</Text>
        <Text style={{ color: t.muted, fontSize: 13, marginTop: 2, lineHeight: 18 }}>
          IAEA publishes its procurement on the UN Global Marketplace. Opens the official list — choose “IAEA” under UN organisation.
        </Text>
      </View>
      <Ionicons name="open-outline" size={18} color={t.muted} />
    </Pressable>
  );
}

export default function Tenders() {
  const t = useTheme();
  const [type, setType] = useState('open');
  const [region, setRegion] = useState('');
  const [data, setData] = useState<TenderList | null>(null);
  const [err, setErr] = useState('');
  const [refreshing, setRefreshing] = useState(false);

  const load = async () => {
    try { setData(await api.tenders()); setErr(''); } catch (e: any) { setErr(e.message); }
  };
  useEffect(() => { load(); }, []);

  const list = useMemo(() => (data?.tenders || [])
    .filter((x) => type === 'all' || (type === 'awarded' ? x.kind === 'Awarded' : x.kind !== 'Awarded'))
    .filter((x) => !region || x.region === region), [data, type, region]);

  const onRefresh = async () => { setRefreshing(true); await load(); setRefreshing(false); };
  const refresh = <RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={t.muted} />;

  return (
    <View style={{ flex: 1 }}>
      {err && !data ? <Empty title="Could not load tenders" hint={err} /> : !data ? <Loading /> : (
        <FlatList
          data={list}
          keyExtractor={(x) => x.id}
          refreshControl={refresh}
          renderItem={({ item }) => <TenderCard x={item} />}
          contentContainerStyle={{ paddingBottom: 24, flexGrow: 1 }}
          ListHeaderComponent={
            <View>
              <ChipRow items={TYPES} value={type} onChange={setType} />
              <View style={{ marginTop: -6 }}><ChipRow items={REGIONS} value={region} onChange={setRegion} /></View>
              <IaeaCard />
              <Text style={{ color: t.muted, fontSize: 12, paddingHorizontal: 16, marginBottom: 10 }}>
                {list.length} notice{list.length === 1 ? '' : 's'} · EU (TED) and UK (Contracts Finder) · updated {formatDate(data.generated_at)}
                {Object.keys(data.errors || {}).length ? ` · not reachable: ${Object.keys(data.errors).join(', ')}` : ''}
              </Text>
            </View>
          }
          ListEmptyComponent={<Empty title="No notices match" hint="Try another filter." />}
        />
      )}
    </View>
  );
}

const s = StyleSheet.create({
  segment: { flexDirection: 'row', margin: 16, marginBottom: 4, borderRadius: 10, padding: 3 },
  segBtn: { flex: 1, alignItems: 'center', paddingVertical: 8, borderRadius: 8 },
  card: { marginHorizontal: 16, marginBottom: 12, padding: 16, borderRadius: 14, borderWidth: StyleSheet.hairlineWidth },
  iaea: { flexDirection: 'row', alignItems: 'center', gap: 12, borderWidth: 1 },
  row: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 },
  badge: { fontSize: 11, fontWeight: '700', paddingHorizontal: 8, paddingVertical: 3, borderRadius: 6, overflow: 'hidden' },
  title: { fontSize: 17, lineHeight: 23, fontWeight: '600', fontFamily: fonts.serif },
});
