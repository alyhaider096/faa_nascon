import { Ionicons } from '@expo/vector-icons';
import { router } from 'expo-router';
import React, { useRef, useState } from 'react';
import { ActivityIndicator, Pressable, StyleSheet, Text, View } from 'react-native';
import { ApiError } from '../data/api';
import { useApp } from '../state/AppContext';
import { C, DISPLAY_FONT } from '../theme';
import { WhipPublisher, WhipPublisherHandle } from '../components/WhipPublisher';
import { DemoStudio } from '../components/DemoStudio';

type StreamResponse = { player_id: string; stream_key: string; status: string; ingest_endpoints: { webrtc?: string; whip?: string; rtmp?: string } | null; playback_url: string | null };

export default function CreatorStudio() {
  const { account, authorizedRequest, demoMode } = useApp();
  const publisher = useRef<WhipPublisherHandle>(null);
  const [stream, setStream] = useState<StreamResponse | null>(null);
  const [state, setState] = useState<'idle' | 'connecting' | 'live' | 'degraded' | 'stopped'>('idle');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const eligible = account?.role === 'player' || account?.role === 'super_admin';
  const call = async (action: 'generate' | 'rotate' | 'revoke') => {
    const body = { action, player_id: account?.player_id ?? 'player-alpha-1', label: 'mobile-camera' };
    try { return await authorizedRequest<StreamResponse>('/api/v1/stream/key', body); }
    catch (cause) { if (cause instanceof ApiError && cause.status === 404) return authorizedRequest<StreamResponse>('/audit/v1/stream/key', body); throw cause; }
  };
  const start = async () => {
    if (!eligible || busy) return; setBusy(true); setError('');
    try {
      const next = await call(stream ? 'rotate' : 'generate'); setStream(next);
      const endpoint = next.ingest_endpoints?.whip ?? next.ingest_endpoints?.webrtc;
      if (!endpoint) throw new Error('The backend did not provide a WebRTC/WHIP ingest endpoint.');
      await publisher.current?.start(endpoint, next.stream_key); setState('live');
    } catch (cause) { setState('degraded'); setError(cause instanceof Error ? cause.message : 'Broadcast could not start.'); }
    finally { setBusy(false); }
  };
  const stop = async () => {
    if (busy) return; setBusy(true); setError('');
    try { await publisher.current?.stop(); if (stream) await call('revoke'); setStream(current => current ? { ...current, status: 'revoked', stream_key: '', ingest_endpoints: null } : current); setState('stopped'); }
    catch (cause) { setError(cause instanceof Error ? cause.message : 'Broadcast could not stop safely.'); }
    finally { setBusy(false); }
  };
  if (!eligible) return <View style={styles.denied}><Ionicons name="lock-closed" color={C.gold} size={42} /><Text style={styles.title}>Creator access required</Text><Text style={styles.copy}>Only eligible players and platform administrators can start a broadcast.</Text><Pressable accessibilityRole="button" onPress={() => router.back()} style={styles.secondary}><Text style={styles.secondaryText}>Go back</Text></Pressable></View>;
  if (demoMode) return <DemoStudio />;
  return <View style={styles.screen}><View style={styles.header}><View><Text style={styles.eyebrow}>NATIVE BROADCAST</Text><Text style={styles.title}>Creator studio</Text></View><View style={[styles.badge, state === 'live' && { backgroundColor: '#184A43' }]}><Text style={styles.badgeText}>{state.toUpperCase()}</Text></View></View><WhipPublisher ref={publisher} onState={setState} /><View style={styles.controls}><Text style={styles.copy}>{state === 'live' ? 'Your camera and microphone are publishing to the team media server.' : 'Start only when the match organizer confirms the stream slot.'}</Text>{error ? <Text accessibilityRole="alert" style={styles.error}>{error}</Text> : null}<Pressable accessibilityRole="button" disabled={busy} onPress={() => void (state === 'live' ? stop() : start())} style={[styles.primary, state === 'live' && styles.stop]}>{busy ? <ActivityIndicator color={C.bg} /> : <><Ionicons name={state === 'live' ? 'stop' : 'radio'} color={C.bg} size={21} /><Text style={styles.primaryText}>{state === 'live' ? 'Stop broadcast' : 'Start broadcast'}</Text></>}</Pressable>{stream?.playback_url ? <Text style={styles.hint}>Playback is available to viewers. Stream credentials are hidden.</Text> : null}</View></View>;
}
const styles = StyleSheet.create({ screen: { flex: 1, backgroundColor: C.bg, padding: 20 }, denied: { flex: 1, backgroundColor: C.bg, alignItems: 'center', justifyContent: 'center', padding: 28, gap: 14 }, header: { flexDirection: 'row', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 16 }, eyebrow: { color: C.accent, fontSize: 10, fontWeight: '900', letterSpacing: 1.4 }, title: { color: C.text, fontSize: 30, fontWeight: '900', fontFamily: DISPLAY_FONT, textTransform: 'uppercase', marginTop: 5, textAlign: 'center' }, badge: { borderRadius: 17, backgroundColor: C.surface2, paddingHorizontal: 12, paddingVertical: 8 }, badgeText: { color: C.text, fontWeight: '900', fontSize: 10 }, controls: { paddingTop: 16 }, copy: { color: C.muted, lineHeight: 22, textAlign: 'center' }, error: { color: C.danger, textAlign: 'center', marginTop: 10 }, primary: { minHeight: 54, borderRadius: 27, backgroundColor: C.accent, flexDirection: 'row', gap: 9, alignItems: 'center', justifyContent: 'center', marginTop: 14 }, stop: { backgroundColor: C.danger }, primaryText: { color: C.bg, fontWeight: '900', fontSize: 16 }, secondary: { minHeight: 50, borderRadius: 25, backgroundColor: C.surface2, paddingHorizontal: 20, alignItems: 'center', justifyContent: 'center' }, secondaryText: { color: C.text, fontWeight: '800' }, hint: { color: C.muted, textAlign: 'center', fontSize: 12, marginTop: 10 } });

