import { Tabs } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import React from 'react';
import { C } from '../../theme';

export default function TabLayout() {
  return <Tabs screenOptions={{ tabBarStyle: { backgroundColor: C.surface, borderTopColor: C.line, minHeight: 63, paddingTop: 7 }, tabBarActiveTintColor: C.accent, tabBarInactiveTintColor: C.muted, tabBarLabelStyle: { fontSize: 11, fontWeight: '800' }, headerShown: false }}>
    <Tabs.Screen name="fixtures" options={{ title: 'Fixtures', tabBarIcon: ({ color, focused }) => <Ionicons name={focused ? 'calendar' : 'calendar-outline'} size={22} color={color} /> }} />
    <Tabs.Screen name="standings" options={{ title: 'Standings', tabBarIcon: ({ color, focused }) => <Ionicons name={focused ? 'podium' : 'podium-outline'} size={22} color={color} /> }} />
    <Tabs.Screen name="store" options={{ title: 'Store', tabBarIcon: ({ color, focused }) => <Ionicons name={focused ? 'bag-handle' : 'bag-handle-outline'} size={22} color={color} /> }} />
    <Tabs.Screen name="club" options={{ title: 'Club', tabBarIcon: ({ color, focused }) => <Ionicons name={focused ? 'shield' : 'shield-outline'} size={22} color={color} /> }} />
  </Tabs>;
}
