import * as DocumentPicker from 'expo-document-picker';
import { router } from 'expo-router';
import { useEffect, useState } from 'react';
import { Platform, Pressable, ScrollView, StyleSheet, Text, TextInput, View } from 'react-native';
import { Btn, SectionTitle } from '@/components/ui';
import { api, getBase, setBase, STATIC } from '@/lib/api';
import { getDeviceToken } from '@/lib/push';
import { useTheme } from '@/lib/theme';

export default function Settings() {
  const t = useTheme();
  const [server, setServer] = useState('');
  const [health, setHealth] = useState<string>('…');
  const [token, setToken] = useState<string | null>(null);
  const [pushNote, setPushNote] = useState<string | undefined>();
  const [alerts, setAlerts] = useState<string[]>([]);
  const [kw, setKw] = useState('');
  const [pdfUrl, setPdfUrl] = useState('');
  const [busy, setBusy] = useState('');
  const [msg, setMsg] = useState('');

  const check = async () => {
    try {
      const h = await api.health();
      if (STATIC) { setHealth(h.generated_at ? `Last update: ${new Date(h.generated_at).toLocaleString('en-GB')}.` : ''); return; }
      setHealth(h.ai ? `connected · AI: ${h.model}` : 'connected · no AI key set (digests use fact extraction)');
    } catch {
      setHealth('unreachable');
    }
  };

  useEffect(() => {
    getBase().then(setServer);
    check();
    if (!STATIC) getDeviceToken().then(async ({ token, reason }) => {
      setToken(token);
      setPushNote(reason);
      setAlerts(await api.alerts(token).catch(() => []));
    });
  }, []);

  const run = async (label: string, fn: () => Promise<void>) => {
    setBusy(label); setMsg('');
    try { await fn(); } catch (e: any) { setMsg(e.message); } finally { setBusy(''); }
  };

  const addAlert = () => kw.trim() && token && run('alert', async () => {
    setAlerts(await api.addAlert(token, kw.trim()));
    setKw('');
  });

  const openReport = (id: number) => router.push({ pathname: '/article/[id]', params: { id: String(id) } });

  const pickPdf = () => run('upload', async () => {
    const res = await DocumentPicker.getDocumentAsync({ type: 'application/pdf', copyToCacheDirectory: true });
    if (res.canceled) return;
    const asset = res.assets[0];
    const form = new FormData();
    if (Platform.OS === 'web' && asset.file) form.append('file', asset.file, asset.name);
    else form.append('file', { uri: asset.uri, name: asset.name, type: asset.mimeType || 'application/pdf' } as any);
    openReport((await api.uploadReport(form)).id);
  });

  const input = [s.input, { color: t.text, backgroundColor: t.card, borderColor: t.faint }];

  return (
    <ScrollView contentContainerStyle={{ paddingBottom: 48 }} keyboardShouldPersistTaps="handled">
      {!STATIC ? (<>
      <SectionTitle>Keyword alerts</SectionTitle>
      <View style={s.pad}>
        <View style={s.rowWrap}>
          {alerts.map((a) => (
            <Pressable key={a} onPress={() => token && api.deleteAlert(token, a).then(setAlerts)}
              style={[s.pill, { backgroundColor: t.accentSoft }]}>
              <Text style={{ color: t.accent, fontWeight: '600' }}>{a}  ✕</Text>
            </Pressable>
          ))}
        </View>
        <View style={s.inline}>
          <TextInput value={kw} onChangeText={setKw} onSubmitEditing={addAlert} placeholder="e.g. BWRX-300"
            placeholderTextColor={t.muted} style={[...input, { flex: 1 }]} autoCapitalize="none" />
          <Btn label="Add" onPress={addAlert} busy={busy === 'alert'} />
        </View>
        <Text style={[s.note, { color: t.muted }]}>
          The server checks new items on every source refresh and sends a push on matches.
          {pushNote ? ` ${pushNote}.` : ''}
        </Text>
      </View>

      <SectionTitle>Reports (PDF)</SectionTitle>
      <View style={s.pad}>
        <View style={s.inline}>
          <TextInput value={pdfUrl} onChangeText={setPdfUrl} placeholder="PDF link" placeholderTextColor={t.muted}
            style={[...input, { flex: 1 }]} autoCapitalize="none" keyboardType="url" />
          <Btn label="Import" busy={busy === 'pdf'} onPress={() => pdfUrl && run('pdf', async () => openReport((await api.reportFromUrl(pdfUrl.trim())).id))} />
        </View>
        <Btn label="Choose a file on this device" outline busy={busy === 'upload'} onPress={pickPdf} />
        <Text style={[s.note, { color: t.muted }]}>The report opens in reading mode: digest, full text and questions about the document.</Text>
      </View>
      </>) : null}

      <SectionTitle>Sources</SectionTitle>
      <View style={s.pad}>
        <Btn label={STATIC ? 'View sources' : 'Manage sources and custom RSS'} outline onPress={() => router.push('/sources')} />
        <Btn label={STATIC ? 'Reload latest news' : 'Refresh all sources now'} outline busy={busy === 'refresh'}
          onPress={() => run('refresh', async () => { const r = await api.refresh(); setMsg(`New items: ${r.new ?? 0}`); })} />
      </View>

      {!STATIC ? (<>
      <SectionTitle>Server</SectionTitle>
      <View style={s.pad}>
        <TextInput value={server} onChangeText={setServer} onEndEditing={() => setBase(server).then(check)}
          autoCapitalize="none" keyboardType="url" style={input} />
        <Text style={[s.note, { color: t.muted }]}>Status: {health}</Text>
      </View>
      </>) : (
        <Text style={[s.note, s.pad, { color: t.muted, marginTop: 16 }]}>
          Free version: news is collected automatically every 2 hours. {health}
        </Text>
      )}
      {msg ? <Text style={[s.note, s.pad, { color: t.text }]}>{msg}</Text> : null}
    </ScrollView>
  );
}

const s = StyleSheet.create({
  pad: { paddingHorizontal: 16, gap: 10 },
  input: { paddingHorizontal: 12, paddingVertical: 11, borderRadius: 10, fontSize: 15, borderWidth: StyleSheet.hairlineWidth },
  inline: { flexDirection: 'row', gap: 8, alignItems: 'center' },
  rowWrap: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  pill: { paddingHorizontal: 12, paddingVertical: 7, borderRadius: 999 },
  note: { fontSize: 13, lineHeight: 18 },
});
