import { useCallback, useEffect, useState } from 'react';
import { Alert, FlatList, Platform, Pressable, StyleSheet, Switch, Text, TextInput, View } from 'react-native';
import { Btn, Empty, Loading } from '@/components/ui';
import { api, STATIC, type Source } from '@/lib/api';
import { formatDate, useTheme } from '@/lib/theme';

export default function Sources() {
  const t = useTheme();
  const [list, setList] = useState<Source[] | null>(null);
  const [url, setUrl] = useState('');
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState('');
  const [err, setErr] = useState('');

  const load = useCallback(() => api.sources().then(setList).catch((e) => setErr(e.message)), []);
  useEffect(() => { load(); }, [load]);

  const add = async () => {
    if (!url.trim()) return;
    setBusy(true); setMsg('');
    try {
      const s = await api.addSource(url.trim());
      setMsg(`Added: ${s.name} (${s.kind === 'rss' ? 'RSS' : 'website'}), items: ${s.articles}`);
      setUrl('');
      load();
    } catch (e: any) { setMsg(e.message); } finally { setBusy(false); }
  };

  const remove = (s: Source) => {
    const go = () => api.deleteSource(s.slug).then(load);
    if (Platform.OS === 'web') { if (window.confirm(`Delete "${s.name}"?`)) go(); return; }
    Alert.alert('Delete source?', s.name, [{ text: 'Cancel', style: 'cancel' }, { text: 'Delete', style: 'destructive', onPress: go }]);
  };

  if (err && !list) return <Empty title="Cannot reach the server" hint={err} />;
  if (!list) return <Loading />;

  return (
    <FlatList
      data={list}
      keyExtractor={(s) => s.slug}
      keyboardShouldPersistTaps="handled"
      ListHeaderComponent={STATIC ? (
        <Text style={{ color: t.muted, lineHeight: 19, padding: 16 }}>
          Sources are collected automatically. To add your own RSS feed or website, add its address to backend/extra_sources.json in the project (or ask Claude).
        </Text>
      ) : (
        <View style={{ padding: 16, gap: 10 }}>
          <Text style={{ color: t.muted, lineHeight: 19 }}>
            Paste an RSS feed or website URL: the server finds the feed itself, and if there is none it collects article links from the page.
          </Text>
          <TextInput value={url} onChangeText={setUrl} onSubmitEditing={add} placeholder="https://example.org/news"
            placeholderTextColor={t.muted} autoCapitalize="none" keyboardType="url"
            style={[s.input, { color: t.text, backgroundColor: t.card, borderColor: t.faint }]} />
          <Btn label="Add source" onPress={add} busy={busy} />
          {msg ? <Text style={{ color: t.text }}>{msg}</Text> : null}
        </View>
      )}
      renderItem={({ item: src }) => (
        <View style={[s.row, { borderBottomColor: t.faint }]}>
          <View style={{ flex: 1 }}>
            <Text style={{ color: t.text, fontSize: 16, fontWeight: '600' }}>{src.name}</Text>
            <Text style={{ color: t.muted, fontSize: 12, marginTop: 3 }} numberOfLines={1}>
              {src.kind === 'rss' ? 'RSS' : 'Website scraping'} · {src.articles} items
              {src.last_fetch ? ` · updated ${formatDate(src.last_fetch)}` : ''}
            </Text>
            {src.last_error ? <Text style={{ color: t.danger, fontSize: 12, marginTop: 3 }} numberOfLines={2}>Error: {src.last_error}</Text> : null}
            {!src.builtin && !STATIC ? (
              <Pressable onPress={() => remove(src)}><Text style={{ color: t.danger, fontSize: 13, marginTop: 6 }}>Delete</Text></Pressable>
            ) : null}
          </View>
          {STATIC ? null : <Switch value={!!src.enabled} onValueChange={(v) => api.toggleSource(src.slug, v).then(load)} />}
        </View>
      )}
    />
  );
}

const s = StyleSheet.create({
  input: { paddingHorizontal: 12, paddingVertical: 11, borderRadius: 10, fontSize: 15, borderWidth: StyleSheet.hairlineWidth },
  row: { flexDirection: 'row', alignItems: 'center', gap: 12, paddingHorizontal: 16, paddingVertical: 12, borderBottomWidth: StyleSheet.hairlineWidth },
});
