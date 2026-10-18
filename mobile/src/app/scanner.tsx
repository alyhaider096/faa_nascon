import { CameraView, useCameraPermissions } from 'expo-camera';
import { Href, router, useLocalSearchParams } from 'expo-router';
import React, { useCallback, useState } from 'react';
import { ActivityIndicator, Linking, Pressable, StyleSheet, Text, View } from 'react-native';
import { C } from '../theme';

export default function Scanner() {
  const { error: initialError } = useLocalSearchParams<{ error?: string }>();
  const [permission, requestPermission] = useCameraPermissions();
  const [locked, setLocked] = useState(false);
  const [error, setError] = useState(initialError ? 'That link was not recognized.' : '');
  const resolve = useCallback(async (data: string) => {
    if (locked) return; setLocked(true); setError('');
    try {
      const url = new URL(data);
      if (url.protocol === 'nascon:' && (url.hostname === 'entity' || url.hostname === 'stream')) {
        router.replace(`/${url.hostname}/${encodeURIComponent(url.pathname.replace(/^\//, ''))}` as Href); return;
      }
      if (!['http:', 'https:'].includes(url.protocol)) throw new Error('Unsupported QR format.');
      const response = await fetch(data);
      const resolved = new URL(response.url || data);
      if (resolved.pathname.startsWith('/web/')) { router.replace(`${resolved.pathname}${resolved.search}` as Href); return; }
      await Linking.openURL(data);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'This QR code could not be opened.'); setLocked(false);
    }
  }, [locked]);

  if (!permission) return <View style={styles.center}><ActivityIndicator color={C.accent} /><Text style={styles.copy}>Checking camera access…</Text></View>;
  if (!permission.granted) return <View style={styles.center}><Text style={styles.title}>Camera access needed</Text><Text style={styles.copy}>LeagueOps uses the camera only while this screen is open to scan match, player and club QR codes.</Text><Pressable accessibilityRole="button" onPress={() => void requestPermission()} style={styles.button}><Text style={styles.buttonText}>Allow camera</Text></Pressable>{!permission.canAskAgain ? <Pressable accessibilityRole="button" onPress={() => void Linking.openSettings()} style={styles.secondary}><Text style={styles.secondaryText}>Open device settings</Text></Pressable> : null}</View>;
  return <View style={styles.screen}><CameraView style={StyleSheet.absoluteFill} facing="back" barcodeScannerSettings={{ barcodeTypes: ['qr'] }} onBarcodeScanned={locked ? undefined : result => void resolve(result.data)} /><View style={styles.overlay}><View style={styles.frame} /><Text style={styles.instruction}>{locked ? 'Resolving destination…' : 'Place the QR code inside the frame'}</Text>{error ? <Text accessibilityRole="alert" style={styles.error}>{error}</Text> : null}{locked && !error ? <ActivityIndicator color={C.accent} /> : null}<Pressable accessibilityRole="button" onPress={() => router.back()} style={styles.secondary}><Text style={styles.secondaryText}>Cancel</Text></Pressable></View></View>;
}
const styles = StyleSheet.create({ screen: { flex: 1, backgroundColor: '#000' }, center: { flex: 1, backgroundColor: C.bg, alignItems: 'center', justifyContent: 'center', padding: 28, gap: 16 }, overlay: { flex: 1, backgroundColor: 'rgba(0,0,0,.28)', alignItems: 'center', justifyContent: 'center', padding: 24 }, frame: { width: 260, height: 260, borderRadius: 32, borderWidth: 3, borderColor: C.accent, backgroundColor: 'transparent' }, title: { color: C.text, fontSize: 28, fontWeight: '900', textAlign: 'center' }, copy: { color: C.muted, textAlign: 'center', lineHeight: 22, maxWidth: 430 }, instruction: { color: '#FFFFFF', backgroundColor: 'rgba(0,0,0,.72)', borderRadius: 18, paddingHorizontal: 18, paddingVertical: 12, marginTop: 20, fontWeight: '800', textAlign: 'center' }, error: { color: '#FFFFFF', backgroundColor: '#6E3039', borderRadius: 14, padding: 12, marginTop: 12 }, button: { minHeight: 52, minWidth: 190, borderRadius: 26, backgroundColor: C.accent, justifyContent: 'center', alignItems: 'center', paddingHorizontal: 20 }, buttonText: { color: C.bg, fontWeight: '900' }, secondary: { minHeight: 48, minWidth: 140, borderRadius: 24, backgroundColor: C.surface2, justifyContent: 'center', alignItems: 'center', paddingHorizontal: 20, marginTop: 16 }, secondaryText: { color: C.text, fontWeight: '800' } });

