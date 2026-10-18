import React, { forwardRef, useImperativeHandle } from 'react';
import { StyleSheet, Text, View } from 'react-native';
import { C } from '../theme';
import type { WhipPublisherHandle } from './WhipPublisher.native';
export const WhipPublisher = forwardRef<WhipPublisherHandle, { onState: (state: 'idle' | 'connecting' | 'live' | 'degraded' | 'stopped') => void }>((_, ref) => {
  useImperativeHandle(ref, () => ({ start: async () => { throw new Error('Creator broadcasting is available in the installed mobile app.'); }, stop: async () => undefined }), []);
  return <View style={styles.preview}><Text style={styles.title}>MOBILE CREATOR STUDIO</Text><Text style={styles.copy}>Open the installed LeagueOps app to publish camera and microphone media.</Text></View>;
});
WhipPublisher.displayName = 'WhipPublisher';
const styles = StyleSheet.create({ preview: { width: '100%', aspectRatio: 9 / 14, maxHeight: 540, borderRadius: 26, backgroundColor: '#11171B', alignItems: 'center', justifyContent: 'center', padding: 28 }, title: { color: C.accent, fontWeight: '900', letterSpacing: 1.2 }, copy: { color: C.text, textAlign: 'center', lineHeight: 22, marginTop: 10 } });

