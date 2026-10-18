import { Ionicons } from '@expo/vector-icons';
import { Href, router, useLocalSearchParams } from 'expo-router';
import React, { useEffect, useState } from 'react';
import { ActivityIndicator, Pressable, StyleSheet, Text, View } from 'react-native';
import { day2Request } from '../../data/day2';
import { useApp } from '../../state/AppContext';
import { C } from '../../theme';

export default function EntityResolver() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const { serverUrl } = useApp();
  const [error, setError] = useState('');
  useEffect(() => {
    let active = true;
    day2Request<{ target_route: string }>(serverUrl, `/audit/v1/qr/${encodeURIComponent(id)}?inspect=true`)
      .then(result => { if (active && result.target_route.startsWith('/web/')) router.replace(result.target_route as Href); else if (active) setError('The QR destination is not supported by this app.'); })
      .catch(cause => active && setError(cause instanceof Error ? cause.message : 'This QR code could not be resolved.'));
    return () => { active = false; };
  }, [id, serverUrl]);
  return <View style={styles.screen}>{error ? <><Ionicons name="alert-circle-outline" color={C.danger} size={42} /><Text accessibilityRole="alert" style={styles.error}>{error}</Text><Pressable accessibilityRole="button" onPress={() => router.replace('/scanner')} style={styles.button}><Text style={styles.buttonText}>Scan another code</Text></Pressable></> : <><ActivityIndicator size="large" color={C.accent} /><Text style={styles.copy}>Opening the latest match destination…</Text></>}</View>;
}
const styles = StyleSheet.create({ screen: { flex: 1, backgroundColor: C.bg, alignItems: 'center', justifyContent: 'center', padding: 28, gap: 16 }, copy: { color: C.muted, textAlign: 'center' }, error: { color: C.text, textAlign: 'center', fontSize: 17 }, button: { minHeight: 50, borderRadius: 25, paddingHorizontal: 20, backgroundColor: C.accent, justifyContent: 'center' }, buttonText: { color: C.bg, fontWeight: '900' } });

