import AsyncStorage from '@react-native-async-storage/async-storage';
import Constants from 'expo-constants';
import * as Device from 'expo-device';
import * as Notifications from 'expo-notifications';
import { Platform } from 'react-native';
import { api } from './api';

Notifications.setNotificationHandler({
  handleNotification: async () => ({
    shouldPlaySound: false,
    shouldSetBadge: false,
    shouldShowBanner: true,
    shouldShowList: true,
  }),
});

/**
 * Returns the Expo push token, or a stable local id when push is unavailable
 * (web, simulator, no EAS projectId) so keyword subscriptions still persist.
 */
export async function getDeviceToken(): Promise<{ token: string; push: boolean; reason?: string }> {
  const stored = await AsyncStorage.getItem('deviceToken');
  if (Platform.OS !== 'web' && Device.isDevice) {
    try {
      let { status } = await Notifications.getPermissionsAsync();
      if (status !== 'granted') status = (await Notifications.requestPermissionsAsync()).status;
      if (status === 'granted') {
        if (Platform.OS === 'android') {
          await Notifications.setNotificationChannelAsync('alerts', {
            name: 'Keyword alerts', importance: Notifications.AndroidImportance.DEFAULT,
          });
        }
        const projectId = Constants.expoConfig?.extra?.eas?.projectId ?? Constants.easConfig?.projectId;
        const token = (await Notifications.getExpoPushTokenAsync({ projectId })).data;
        await AsyncStorage.setItem('deviceToken', token);
        await api.alerts(token).catch(() => {});
        return { token, push: true };
      }
      return { token: stored || (await localId()), push: false, reason: 'Notifications are disabled in system settings' };
    } catch (e: any) {
      return { token: stored || (await localId()), push: false, reason: 'Requires an EAS build with a projectId' };
    }
  }
  return { token: stored || (await localId()), push: false, reason: 'Push works only on a physical device' };
}

async function localId() {
  const id = `local-${Math.random().toString(36).slice(2)}${Date.now().toString(36)}`;
  await AsyncStorage.setItem('deviceToken', id);
  return id;
}
