import { StyleSheet, Text, View } from 'react-native';
import type { Reactor } from '@/lib/api';
import { STAGE_LABELS, useTheme } from '@/lib/theme';

export function StageBadge({ stage }: { stage: string }) {
  const t = useTheme();
  const strong = stage === 'operation' || stage === 'construction';
  return (
    <Text style={[st.badge, { color: strong ? t.accent : t.muted, backgroundColor: strong ? t.accentSoft : t.faint }]}>
      {STAGE_LABELS[stage] ?? stage}
    </Text>
  );
}

export const power = (r: Reactor) =>
  r.power_mwe ? `${r.power_mwe} MWe` : r.power_mwt ? `${r.power_mwt} MWt` : '—';

export function Facts({ rows }: { rows: [string, string | number | null | undefined][] }) {
  const t = useTheme();
  return (
    <View style={[st.facts, { backgroundColor: t.card, borderColor: t.faint }]}>
      {rows.filter(([, v]) => v != null && v !== '').map(([k, v], i) => (
        <View key={k} style={[st.fact, i > 0 && { borderTopColor: t.faint, borderTopWidth: StyleSheet.hairlineWidth }]}>
          <Text style={{ color: t.muted, width: 120 }}>{k}</Text>
          <Text style={{ color: t.text, flex: 1, fontWeight: '500' }}>{String(v)}</Text>
        </View>
      ))}
    </View>
  );
}

const st = StyleSheet.create({
  facts: { marginHorizontal: 16, borderRadius: 12, borderWidth: StyleSheet.hairlineWidth },
  fact: { flexDirection: 'row', paddingHorizontal: 14, paddingVertical: 11, gap: 8 },
  badge: { fontSize: 11, fontWeight: '700', paddingHorizontal: 8, paddingVertical: 4, borderRadius: 6, overflow: 'hidden', alignSelf: 'flex-start' },
});
