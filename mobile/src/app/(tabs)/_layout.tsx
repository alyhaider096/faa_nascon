import { Tabs, router } from 'expo-router';
import React from 'react';
import { Pressable, Text } from 'react-native';
import { C } from '../../theme';

export default function TabLayout() {
  return <Tabs screenOptions={{ tabBarStyle: { backgroundColor: C.surface, borderTopColor: C.line, height: 63 }, tabBarActiveTintColor: C.accent, tabBarInactiveTintColor: C.muted, tabBarLabelStyle: { fontSize: 11, fontWeight: '800', marginBottom: 8 }, headerStyle: { backgroundColor: C.bg }, headerTintColor: C.text, headerTitleStyle: { fontWeight: '800' }, headerRight: () => <Pressable onPress={() => router.push('/settings')} accessibilityRole="button" accessibilityLabel="Settings" style={{ paddingHorizontal: 18 }}><Text style={{ color: C.accent, fontSize: 20 }}>⚙</Text></Pressable> }}>
    <Tabs.Screen name="fixtures" options={{ title: 'Fixtures', tabBarIcon: ({ color }) => <Text style={{ color, fontSize: 21 }}>▦</Text> }} />
    <Tabs.Screen name="standings" options={{ title: 'Standings', tabBarIcon: ({ color }) => <Text style={{ color, fontSize: 21 }}>▤</Text> }} />
    <Tabs.Screen name="store" options={{ title: 'Store', tabBarIcon: ({ color }) => <Text style={{ color, fontSize: 21 }}>▣</Text> }} />
    <Tabs.Screen name="club" options={{ title: 'Club', tabBarIcon: ({ color }) => <Text style={{ color, fontSize: 21 }}>♧</Text> }} />
  </Tabs>;
}
