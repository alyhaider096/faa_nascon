import { Stack, router, usePathname } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import React, { useEffect } from 'react';
import { ActivityIndicator, Text, View } from 'react-native';
import { SyncBar } from '../components/SyncBar';
import { AppProvider, useApp } from '../state/AppContext';
import { C } from '../theme';

function Shell() {
  const { account, ready } = useApp();
  const path = usePathname();
  useEffect(() => {
    if (!ready) return;
    if (!account && path !== '/login' && path !== '/settings') router.replace('/login');
    else if (account && (path === '/' || path === '/login')) router.replace('/(tabs)/fixtures');
  }, [account, path, ready]);
  if (!ready) return <View style={{ flex: 1, justifyContent: 'center', alignItems: 'center', backgroundColor: C.bg }}><Text style={{ color: C.text, fontSize: 29, fontWeight: '800', marginBottom: 20 }}>LeagueOps</Text><ActivityIndicator size="large" color={C.accent} /><Text style={{ color: C.muted, marginTop: 16 }}>Opening your league…</Text></View>;
  return <View style={{ flex: 1, backgroundColor: C.bg }}>
    <StatusBar style="light" />
    <SyncBar />
    <Stack screenOptions={{ headerStyle: { backgroundColor: C.bg }, headerTintColor: C.text, headerTitleStyle: { fontWeight: '700' }, contentStyle: { backgroundColor: C.bg } }}>
      <Stack.Screen name="index" options={{ headerShown: false }} />
      <Stack.Screen name="login" options={{ headerShown: false }} />
      <Stack.Screen name="(tabs)" options={{ headerShown: false }} />
      <Stack.Screen name="match/[id]" options={{ title: 'Match detail' }} />
      <Stack.Screen name="product/[id]" options={{ title: 'Product' }} />
      <Stack.Screen name="checkout" options={{ title: 'Checkout' }} />
      <Stack.Screen name="receipt" options={{ title: 'Receipt' }} />
      <Stack.Screen name="roster" options={{ title: 'Roster management' }} />
      <Stack.Screen name="score" options={{ title: 'Scoring entry' }} />
      <Stack.Screen name="queue" options={{ title: 'Sync queue' }} />
      <Stack.Screen name="settings" options={{ title: 'Settings' }} />
    </Stack>
  </View>;
}
export default function RootLayout() { return <AppProvider><Shell /></AppProvider>; }
