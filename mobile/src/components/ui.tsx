import { router } from 'expo-router';
import { memo } from 'react';
import { ActivityIndicator, Image, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { view, type Article, type ViewMode } from '@/lib/api';
import { CATEGORY_LABELS, fonts, formatDate, useTheme } from '@/lib/theme';

export function Chip({ label, active, onPress }: { label: string; active?: boolean; onPress?: () => void }) {
  const t = useTheme();
  return (
    <Pressable
      onPress={onPress}
      style={[s.chip, { backgroundColor: active ? t.text : 'transparent', borderColor: active ? t.text : t.faint }]}>
      <Text style={[s.chipText, { color: active ? t.bg : t.muted }]}>{label}</Text>
    </Pressable>
  );
}

export function ChipRow({ items, value, onChange }: {
  items: { key: string; label: string }[]; value: string; onChange: (k: string) => void;
}) {
  return (
    <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={s.chipRow}>
      {items.map((i) => <Chip key={i.key} label={i.label} active={value === i.key} onPress={() => onChange(i.key)} />)}
    </ScrollView>
  );
}

export function Meta({ a }: { a: Article }) {
  const t = useTheme();
  return (
    <Text style={[s.meta, { color: t.muted }]} numberOfLines={1}>
      <Text style={{ color: t.accent, fontWeight: '600' }}>{a.source.name}</Text>
      {'  ·  '}{formatDate(a.published_at)}
      {a.also_in?.length ? `  ·  +${a.also_in.length} ${plural(a.also_in.length, 'source', 'sources', 'sources')}` : ''}
    </Text>
  );
}

export function Bullets({ items, size = 15 }: { items: string[]; size?: number }) {
  const t = useTheme();
  return (
    <View style={{ gap: 6 }}>
      {items.map((b, i) => (
        <View key={i} style={{ flexDirection: 'row', gap: 8 }}>
          <Text style={{ color: t.accent, fontSize: size, lineHeight: size * 1.45 }}>•</Text>
          <Text style={{ flex: 1, color: t.text, fontSize: size, lineHeight: size * 1.45, fontFamily: fonts.sans }}>{b}</Text>
        </View>
      ))}
    </View>
  );
}

// SMR / Large / Supply are tabs now; cards only show cross-cutting topics
const TOPIC_TAGS = new Set(['tech', 'startups', 'policy']);

/** Feed card: source/date, title (RU when available), AI digest inside the card, tags. */
export const ArticleCard = memo(function ArticleCard({ a, compact, mode = 'en' }: { a: Article; compact?: boolean; mode?: ViewMode }) {
  const t = useTheme();
  const v = view(a, mode);
  const title = v.title;
  const bullets = v.bullets.slice(0, compact ? 0 : 3);
  return (
    <Pressable
      onPress={() => router.push({ pathname: '/article/[id]', params: { id: String(a.id), mode } })}
      style={({ pressed }) => [s.card, { backgroundColor: t.card, borderColor: t.faint, opacity: pressed ? 0.85 : 1 }]}>
      <Meta a={a} />
      <View style={{ flexDirection: 'row', gap: 12 }}>
        <Text style={[s.title, { color: t.text }]} numberOfLines={compact ? 3 : 4}>{title}</Text>
        {a.image && compact ? <Image source={{ uri: a.image }} style={s.thumb} /> : null}
      </View>
      {v.translated ? (
        <Text style={[s.orig, { color: t.muted }]} numberOfLines={1}>Translated from Russian</Text>
      ) : null}
      {a.snippet ? <Text style={[s.snippet, { color: t.muted }]} numberOfLines={2}>{a.snippet}</Text> : null}
      {bullets.length ? <View style={{ marginTop: 10 }}><Bullets items={bullets} size={14} /></View> : null}
      {a.tags.some((tg) => TOPIC_TAGS.has(tg)) || a.kind === 'report' ? (
        <View style={s.tags}>
          {a.tags.filter((tg) => TOPIC_TAGS.has(tg)).map((tag) => (
            <Text key={tag} style={[s.tag, { color: t.accent, backgroundColor: t.accentSoft }]}>
              {CATEGORY_LABELS[tag] ?? tag}
            </Text>
          ))}
          {a.kind === 'report' ? <Text style={[s.tag, { color: t.muted, backgroundColor: t.faint }]}>PDF</Text> : null}
        </View>
      ) : null}
    </Pressable>
  );
});

export function Centered({ children }: { children: React.ReactNode }) {
  return <View style={s.centered}>{children}</View>;
}

export function Loading() {
  const t = useTheme();
  return <Centered><ActivityIndicator color={t.muted} /></Centered>;
}

export function Empty({ title, hint }: { title: string; hint?: string }) {
  const t = useTheme();
  return (
    <Centered>
      <Text style={{ color: t.text, fontSize: 16, fontWeight: '600', textAlign: 'center' }}>{title}</Text>
      {hint ? <Text style={{ color: t.muted, marginTop: 6, textAlign: 'center', lineHeight: 20 }}>{hint}</Text> : null}
    </Centered>
  );
}

export function SectionTitle({ children }: { children: React.ReactNode }) {
  const t = useTheme();
  return <Text style={[s.section, { color: t.muted }]}>{children}</Text>;
}

export function plural(n: number, one: string, _few: string, many: string) {
  return n === 1 ? one : many;
}

export function Btn({ label, onPress, busy, outline }: { label: string; onPress: () => void; busy?: boolean; outline?: boolean }) {
  const t = useTheme();
  return (
    <Pressable onPress={onPress} disabled={busy}
      style={({ pressed }) => [s.btn, outline ? { borderColor: t.faint, borderWidth: 1 } : { backgroundColor: t.text }, { opacity: pressed ? 0.7 : 1 }]}>
      {busy ? <ActivityIndicator color={outline ? t.text : t.bg} /> :
        <Text style={{ color: outline ? t.text : t.bg, fontWeight: '600' }}>{label}</Text>}
    </Pressable>
  );
}

const s = StyleSheet.create({
  btn: { paddingHorizontal: 16, paddingVertical: 12, borderRadius: 10, alignItems: 'center', justifyContent: 'center', minHeight: 44 },
  chip: { paddingHorizontal: 14, paddingVertical: 7, borderRadius: 999, borderWidth: StyleSheet.hairlineWidth },
  chipText: { fontSize: 14, fontWeight: '500' },
  chipRow: { gap: 8, paddingHorizontal: 16, paddingVertical: 10 },
  card: { marginHorizontal: 16, marginBottom: 12, padding: 16, borderRadius: 14, borderWidth: StyleSheet.hairlineWidth },
  meta: { fontSize: 12, marginBottom: 6, letterSpacing: 0.2 },
  title: { flex: 1, fontSize: 18, lineHeight: 24, fontWeight: '600', fontFamily: fonts.serif },
  orig: { fontSize: 12, marginTop: 4, fontStyle: 'italic' },
  snippet: { fontSize: 13, marginTop: 6, lineHeight: 18 },
  thumb: { width: 64, height: 64, borderRadius: 8 },
  tags: { flexDirection: 'row', flexWrap: 'wrap', gap: 6, marginTop: 12 },
  tag: { fontSize: 11, fontWeight: '600', paddingHorizontal: 8, paddingVertical: 3, borderRadius: 6, overflow: 'hidden' },
  centered: { flex: 1, alignItems: 'center', justifyContent: 'center', padding: 32, minHeight: 240 },
  section: { fontSize: 12, fontWeight: '700', letterSpacing: 0.8, textTransform: 'uppercase', marginTop: 24, marginBottom: 8, paddingHorizontal: 16 },
});
