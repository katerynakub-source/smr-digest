import Ionicons from '@expo/vector-icons/Ionicons';
import { router, Tabs } from 'expo-router';
import { Pressable } from 'react-native';
import { useTheme } from '@/lib/theme';

type IconName = React.ComponentProps<typeof Ionicons>['name'];
const icon = (name: IconName) => ({ color, size }: { color: any; size: number }) =>
  <Ionicons name={name} color={color} size={size - 2} />;

export default function TabLayout() {
  const t = useTheme();
  return (
    <Tabs
      screenOptions={{
        tabBarActiveTintColor: t.text,
        tabBarInactiveTintColor: t.muted,
        tabBarStyle: { backgroundColor: t.bg, borderTopColor: t.faint },
        headerStyle: { backgroundColor: t.bg },
        headerTitleStyle: { color: t.text, fontWeight: '700' },
        headerShadowVisible: false,
        sceneStyle: { backgroundColor: t.bg },
      }}>
      <Tabs.Screen name="index" options={{
        title: 'Feed', headerTitle: 'SMR Digest', tabBarIcon: icon('newspaper-outline'),
        headerRight: () => (
          <Pressable hitSlop={12} onPress={() => router.push('/settings')} style={{ marginRight: 16 }} accessibilityLabel="Settings">
            <Ionicons name="options-outline" size={22} color={t.text} />
          </Pressable>
        ),
      }} />
      <Tabs.Screen name="search" options={{ title: 'Search', tabBarIcon: icon('search-outline') }} />
      <Tabs.Screen name="catalog" options={{ title: 'Projects', headerTitle: 'Project database', tabBarIcon: icon('grid-outline') }} />
      <Tabs.Screen name="supply" options={{ title: 'Supply', headerTitle: 'Supply chain', tabBarIcon: icon('cube-outline') }} />
      <Tabs.Screen name="saved" options={{ title: 'Saved', tabBarIcon: icon('bookmark-outline') }} />
      {/* reachable from the gear on the Feed header; hidden from the tab bar to keep 5 tabs */}
      <Tabs.Screen name="settings" options={{ title: 'Settings', href: null }} />
    </Tabs>
  );
}
