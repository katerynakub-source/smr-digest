import Ionicons from '@expo/vector-icons/Ionicons';
import { router, Tabs } from 'expo-router';
import { Pressable, View } from 'react-native';
import { useTheme } from '@/lib/theme';

type IconName = React.ComponentProps<typeof Ionicons>['name'];
const icon = (name: IconName) => ({ color, size }: { color: any; size: number }) =>
  <Ionicons name={name} color={color} size={size - 2} />;

/** Search · Saved · Projects · Settings live in the header of every tab. */
function HeaderIcons() {
  const t = useTheme();
  const items: [IconName, string, '/search' | '/saved' | '/projects' | '/settings'][] = [
    ['search-outline', 'Search', '/search'],
    ['bookmark-outline', 'Saved', '/saved'],
    ['grid-outline', 'Project database', '/projects'],
    ['options-outline', 'Settings', '/settings'],
  ];
  return (
    <View style={{ flexDirection: 'row', gap: 18, marginRight: 16 }}>
      {items.map(([name, label, href]) => (
        <Pressable key={href} hitSlop={8} onPress={() => router.push(href)} accessibilityLabel={label}>
          <Ionicons name={name} size={21} color={t.text} />
        </Pressable>
      ))}
    </View>
  );
}

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
        headerTitleAlign: 'left',
        headerRight: () => <HeaderIcons />,
        sceneStyle: { backgroundColor: t.bg },
      }}>
      <Tabs.Screen name="index" options={{ title: 'SMR', headerTitle: 'SMR', tabBarIcon: icon('cube-outline') }} />
      <Tabs.Screen name="large" options={{ title: 'Large', headerTitle: 'Large reactors', tabBarIcon: icon('business-outline') }} />
      <Tabs.Screen name="russian" options={{ title: 'Russian', headerTitle: 'Russian tech', tabBarIcon: icon('language-outline') }} />
      <Tabs.Screen name="supply" options={{ title: 'Supply', headerTitle: 'Supply chain', tabBarIcon: icon('git-network-outline') }} />
      <Tabs.Screen name="tenders" options={{ title: 'Tenders', headerTitle: 'Tenders', tabBarIcon: icon('document-text-outline') }} />
    </Tabs>
  );
}
