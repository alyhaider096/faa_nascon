import { router } from 'expo-router';
import React from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { useApp } from '../state/AppContext';
import { C } from '../theme';

export function SyncBar() {
  const { demoMode, online, syncing, queue } = useApp();
  const pending = queue.filter(a => a.status === 'pending').length;
  const label = demoMode ? 'Demo preview' : syncing ? 'Syncing' : online ? 'Connected' : 'Disconnected';
  return <Pressable onPress={() => router.push('/queue')} style={styles.bar} accessibilityRole="button" accessibilityLabel={`${label}. ${pending} pending actions. Open sync queue.`}>
    <View style={[styles.dot, { backgroundColor: demoMode || syncing ? C.gold : online ? '#9DEBD6' : C.danger }]} />
    <Text style={styles.text}>{label}</Text>
    <Text style={styles.mode}>{demoMode ? 'LOCAL DATA' : 'BACKEND'}</Text>
    <Text style={styles.count}>{pending} pending  ›</Text>
  </Pressable>;
}
const styles = StyleSheet.create({ bar: { borderBottomWidth: 1, borderBottomColor: C.line, backgroundColor: C.surface, minHeight: 44, flexDirection: 'row', alignItems: 'center', paddingHorizontal: 15, gap: 8 }, dot: { height: 8, width: 8, borderRadius: 4 }, text: { color: C.text, fontWeight: '700', fontSize: 12 }, mode: { color: C.muted, fontWeight: '700', fontSize: 10, letterSpacing: .7, marginLeft: 2, flex: 1 }, count: { color: C.accent, fontWeight: '700', fontSize: 12 } });
