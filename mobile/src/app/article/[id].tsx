import Ionicons from '@expo/vector-icons/Ionicons';
import { router, Stack, useLocalSearchParams } from 'expo-router';
import { useEffect, useState } from 'react';
import { ActivityIndicator, Image, Linking, Pressable, ScrollView, Share, StyleSheet, Text, TextInput, View } from 'react-native';
import { Btn, Bullets, Empty, Loading, Meta } from '@/components/ui';
import { api, STATIC, view, type Answer, type Article, type ViewMode } from '@/lib/api';
import { getSaved, removeArticle, saveArticle, useIsSaved } from '@/lib/offline';
import { CATEGORY_LABELS, fonts, useTheme } from '@/lib/theme';

export default function ArticleScreen() {
  const t = useTheme();
  const params = useLocalSearchParams<{ id: string; mode?: string }>();
  const id = Number(params.id);
  const mode: ViewMode = params.mode === 'orig' ? 'orig' : 'en';
  const [a, setA] = useState<Article | null>(null);
  const [error, setError] = useState('');
  const [offline, setOffline] = useState(false);
  const [digesting, setDigesting] = useState(false);
  const [showFull, setShowFull] = useState(false);
  const saved = useIsSaved(id);

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        let art = await api.article(id);
        if (alive) setA(art);
        if (!art.bullets?.length) {
          setDigesting(true);
          art = await api.digest(id).catch(() => art);
          if (alive) setA(art);
          setDigesting(false);
        }
        if (await getSaved(id)) saveArticle(art); // keep offline copy fresh
      } catch (e: any) {
        const local = await getSaved(id);
        if (!alive) return;
        if (local) { setA(local); setOffline(true); } else setError(e.message);
      }
    })();
    return () => { alive = false; };
  }, [id]);

  if (error) return <Empty title="Could not open this item" hint={error} />;
  if (!a) return <Loading />;

  const isReport = a.kind === 'report';
  const v = view(a, mode);
  // full text exists only in the server version; in English mode a Russian item shows its translated excerpt
  const paragraphs = ((v.translated ? '' : a.content) || v.excerpt || '').split(/\n{2,}/).filter(Boolean);
  const visible = isReport && !showFull ? paragraphs.slice(0, 12) : paragraphs;

  return (
    <>
      <Stack.Screen options={{
        title: isReport ? 'Report' : a.source.name,
        headerRight: () => (
          <View style={{ flexDirection: 'row', gap: 18 }}>
            <Pressable hitSlop={10} onPress={() => Share.share({ message: `${v.title}\n${a.url}` })}>
              <Ionicons name="share-outline" size={22} color={t.text} />
            </Pressable>
            <Pressable hitSlop={10} onPress={() => (saved ? removeArticle(a.id) : saveArticle(a))}>
              <Ionicons name={saved ? 'bookmark' : 'bookmark-outline'} size={22} color={saved ? t.accent : t.text} />
            </Pressable>
          </View>
        ),
      }} />
      <ScrollView contentContainerStyle={s.wrap} keyboardShouldPersistTaps="handled">
        {offline ? <Text style={[s.small, { color: t.muted, marginBottom: 8 }]}>Offline copy</Text> : null}
        <Meta a={a} />
        <Text style={[s.h1, { color: t.text }]}>{v.title}</Text>
        {v.translated ? <Text style={[s.small, { color: t.muted, fontStyle: 'italic' }]}>Translated automatically from Russian · original: {a.title}</Text> : null}
        <View style={s.tags}>
          {a.tags.map((tag) => <Text key={tag} style={[s.tag, { color: t.accent, backgroundColor: t.accentSoft }]}>{CATEGORY_LABELS[tag] ?? tag}</Text>)}
        </View>

        <View style={[s.digest, { backgroundColor: t.card, borderColor: t.faint }]}>
          <Text style={[s.label, { color: t.muted }]}>
            {a.ai_model === 'extractive' ? 'Key facts' : 'AI digest'}
          </Text>
          {v.bullets.length ? <Bullets items={v.bullets} size={15} /> :
            digesting ? <ActivityIndicator color={t.muted} /> :
              <Text style={{ color: t.muted }}>Not enough text for a digest.</Text>}
          {v.translated ? (
            <Text style={[s.small, { color: t.muted, marginTop: 8 }]}>Machine-translated with a free offline translator — check the original for exact wording.</Text>
          ) : null}
        </View>

        {a.image && !isReport ? <Image source={{ uri: a.image }} style={s.image} resizeMode="cover" /> : null}

        {visible.map((p, i) => (
          <Text key={i} selectable style={[s.body, { color: t.text }]}>{p}</Text>
        ))}
        {isReport && paragraphs.length > visible.length ? (
          <Btn outline label={`Show full document (${paragraphs.length} sections)`} onPress={() => setShowFull(true)} />
        ) : null}

        {a.content && !STATIC ? <AskBox id={a.id} isReport={isReport} /> : null}

        {a.also_in.length ? (
          <View style={{ marginTop: 28 }}>
            <Text style={[s.label, { color: t.muted }]}>Same story in other sources</Text>
            {a.also_in.map((d) => (
              <Pressable key={d.id} onPress={() => router.push({ pathname: '/article/[id]', params: { id: String(d.id) } })}>
                <Text style={{ color: t.accent, paddingVertical: 6, fontSize: 15 }}>{d.source} →</Text>
              </Pressable>
            ))}
          </View>
        ) : null}

        {!a.url.startsWith('upload://') ? (
          <View style={{ marginTop: 24 }}>
            <Btn outline label="Open original" onPress={() => Linking.openURL(a.url)} />
          </View>
        ) : null}
      </ScrollView>
    </>
  );
}

/** Readwise Reader-style: ask a question about this document. */
function AskBox({ id, isReport }: { id: number; isReport: boolean }) {
  const t = useTheme();
  const [q, setQ] = useState('');
  const [ans, setAns] = useState<Answer | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');

  const ask = async () => {
    if (!q.trim()) return;
    setBusy(true); setErr('');
    try { setAns(await api.ask(id, q.trim())); } catch (e: any) { setErr(e.message); } finally { setBusy(false); }
  };

  return (
    <View style={[s.digest, { backgroundColor: t.card, borderColor: t.faint, marginTop: 28 }]}>
      <Text style={[s.label, { color: t.muted }]}>Ask AI about this text</Text>
      <View style={{ flexDirection: 'row', gap: 8 }}>
        <TextInput value={q} onChangeText={setQ} onSubmitEditing={ask} returnKeyType="send"
          placeholder={isReport ? 'What SMR cost does the report give?' : 'What is the reactor output?'}
          placeholderTextColor={t.muted}
          style={[s.input, { color: t.text, borderColor: t.faint, backgroundColor: t.bg }]} />
        <Pressable onPress={ask} style={[s.send, { backgroundColor: t.text }]}>
          {busy ? <ActivityIndicator color={t.bg} /> : <Ionicons name="arrow-up" size={18} color={t.bg} />}
        </Pressable>
      </View>
      {err ? <Text style={{ color: t.danger, marginTop: 8 }}>{err}</Text> : null}
      {ans ? (
        <View style={{ marginTop: 12, gap: 10 }}>
          <Text style={{ color: t.text, fontSize: 15, lineHeight: 22 }}>{ans.answer}</Text>
          {ans.passages.map((p) => (
            <Text key={p.n} style={[s.quote, { color: t.muted, borderLeftColor: t.faint }]} numberOfLines={6}>
              [{p.n}] {p.text}
            </Text>
          ))}
        </View>
      ) : null}
    </View>
  );
}

const s = StyleSheet.create({
  wrap: { padding: 20, paddingBottom: 60, maxWidth: 720, width: '100%', alignSelf: 'center' },
  h1: { fontSize: 26, lineHeight: 33, fontWeight: '700', fontFamily: fonts.serif, marginTop: 4 },
  small: { fontSize: 13, marginTop: 6 },
  tags: { flexDirection: 'row', flexWrap: 'wrap', gap: 6, marginTop: 12 },
  tag: { fontSize: 11, fontWeight: '600', paddingHorizontal: 8, paddingVertical: 3, borderRadius: 6, overflow: 'hidden' },
  digest: { marginTop: 20, padding: 16, borderRadius: 14, borderWidth: StyleSheet.hairlineWidth },
  label: { fontSize: 12, fontWeight: '700', letterSpacing: 0.8, textTransform: 'uppercase', marginBottom: 10 },
  image: { width: '100%', aspectRatio: 16 / 9, borderRadius: 12, marginTop: 20 },
  body: { fontSize: 18, lineHeight: 30, fontFamily: fonts.serif, marginTop: 18 },
  input: { flex: 1, borderWidth: StyleSheet.hairlineWidth, borderRadius: 10, paddingHorizontal: 12, paddingVertical: 10, fontSize: 15 },
  send: { width: 42, height: 42, borderRadius: 21, alignItems: 'center', justifyContent: 'center' },
  quote: { fontSize: 13, lineHeight: 19, borderLeftWidth: 2, paddingLeft: 10 },
});
