import * as Notifications from 'expo-notifications';
import { router, Stack } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { useEffect } from 'react';
import { Platform } from 'react-native';
import { useTheme } from '@/lib/theme';
import '@/lib/push';

export default function RootLayout() {
  const t = useTheme();

  // Tap on a keyword alert → open the article
  useEffect(() => {
    if (Platform.OS === 'web') return;
    const open = (r: Notifications.NotificationResponse | null) => {
      const id = r?.notification.request.content.data?.articleId;
      if (id) router.push({ pathname: '/article/[id]', params: { id: String(id) } });
    };
    Notifications.getLastNotificationResponseAsync().then(open);
    const sub = Notifications.addNotificationResponseReceivedListener(open);
    return () => sub.remove();
  }, []);

  return (
    <>
      <StatusBar style="auto" />
      <Stack
        screenOptions={{
          headerStyle: { backgroundColor: t.bg },
          headerTintColor: t.text,
          headerShadowVisible: false,
          contentStyle: { backgroundColor: t.bg },
          headerBackTitle: 'Back',
        }}>
        <Stack.Screen name="(tabs)" options={{ headerShown: false }} />
        <Stack.Screen name="article/[id]" options={{ title: '' }} />
        <Stack.Screen name="company/[slug]" options={{ title: 'Company' }} />
        <Stack.Screen name="reactor/[slug]" options={{ title: 'Reactor' }} />
        <Stack.Screen name="sources" options={{ title: 'Sources' }} />
      </Stack>
    </>
  );
}
