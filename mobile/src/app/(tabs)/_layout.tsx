import { Tabs } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import React from 'react';
import { C } from '../../theme';

export default function TabLayout() {
  return <Tabs screenOptions={{ tabBarStyle: { position: 'absolute', bottom: 14, left: 16, right: 16, height: 70, paddingTop: 8, paddingBottom: 8, backgroundColor: C.surface, borderTopWidth: 1, borderColor: C.line, borderWidth: 1, borderRadius: 22, elevation: 12, shadowColor: '#000000', shadowOpacity: .3, shadowRadius: 14, shadowOffset: { width: 0, height: 5 } }, tabBarActiveTintColor: C.accent, tabBarInactiveTintColor: C.muted, tabBarLabelStyle: { fontSize: 11, fontWeight: '800' }, headerShown: false }}>
    <Tabs.Screen name="fixtures" options={{ title: 'Fixtures', tabBarIcon: ({ color, focused }) => <Ionicons name={focused ? 'calendar' : 'calendar-outline'} size={22} color={color} /> }} />
    <Tabs.Screen name="standings" options={{ title: 'Standings', tabBarIcon: ({ color, focused }) => <Ionicons name={focused ? 'podium' : 'podium-outline'} size={22} color={color} /> }} />
    <Tabs.Screen name="store" options={{ title: 'Store', tabBarIcon: ({ color, focused }) => <Ionicons name={focused ? 'bag-handle' : 'bag-handle-outline'} size={22} color={color} /> }} />
    <Tabs.Screen name="club" options={{ title: 'Club', tabBarIcon: ({ color, focused }) => <Ionicons name={focused ? 'shield' : 'shield-outline'} size={22} color={color} /> }} />
  </Tabs>;
}
