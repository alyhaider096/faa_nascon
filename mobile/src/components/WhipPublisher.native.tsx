import React, { forwardRef, useCallback, useImperativeHandle, useRef, useState } from 'react';
import { StyleSheet, Text, View } from 'react-native';
import { mediaDevices, MediaStream, RTCPeerConnection, RTCSessionDescription, RTCView } from 'react-native-webrtc';
import { C } from '../theme';

export type WhipPublisherHandle = { start: (endpoint: string, bearer?: string) => Promise<void>; stop: () => Promise<void> };

export const WhipPublisher = forwardRef<WhipPublisherHandle, { onState: (state: 'idle' | 'connecting' | 'live' | 'degraded' | 'stopped') => void }>(({ onState }, ref) => {
  const [stream, setStream] = useState<MediaStream | null>(null);
  const [message, setMessage] = useState('Camera preview will appear when broadcast starts.');
  const peer = useRef<RTCPeerConnection | null>(null);
  const resourceUrl = useRef<string | null>(null);
  const streamRef = useRef<MediaStream | null>(null);

  const stop = useCallback(async () => {
    if (resourceUrl.current) await fetch(resourceUrl.current, { method: 'DELETE' }).catch(() => undefined);
    peer.current?.close(); peer.current = null; resourceUrl.current = null;
    streamRef.current?.getTracks().forEach(track => track.stop()); streamRef.current = null; setStream(null); setMessage('Broadcast stopped safely.'); onState('stopped');
  }, [onState]);

  useImperativeHandle(ref, () => ({
    start: async (endpoint, bearer) => {
      await stop(); onState('connecting'); setMessage('Requesting camera and microphone…');
      const local = await mediaDevices.getUserMedia({ audio: true, video: { facingMode: 'user', frameRate: 30, width: 1280, height: 720 } });
      streamRef.current = local; setStream(local); setMessage('Negotiating secure media ingest…');
      const connection = new RTCPeerConnection({ iceServers: [] }); peer.current = connection;
      local.getTracks().forEach(track => connection.addTrack(track, local));
      const events = connection as unknown as { addEventListener: (name: string, listener: () => void) => void; removeEventListener: (name: string, listener: () => void) => void };
      events.addEventListener('connectionstatechange', () => {
        if (connection.connectionState === 'connected') { setMessage('You are live.'); onState('live'); }
        else if (['disconnected', 'failed'].includes(connection.connectionState)) { setMessage('Connection degraded. Check the hotspot.'); onState('degraded'); }
      });
      const offer = await connection.createOffer({ offerToReceiveAudio: false, offerToReceiveVideo: false });
      await connection.setLocalDescription(offer);
      if (connection.iceGatheringState !== 'complete') await new Promise<void>((resolve, reject) => {
        const timeout = setTimeout(() => reject(new Error('Media negotiation timed out.')), 5000);
        const listener = () => { if (connection.iceGatheringState === 'complete') { clearTimeout(timeout); events.removeEventListener('icegatheringstatechange', listener); resolve(); } };
        events.addEventListener('icegatheringstatechange', listener);
      });
      const response = await fetch(endpoint, { method: 'POST', headers: { 'Content-Type': 'application/sdp', ...(bearer ? { Authorization: `Bearer ${bearer}` } : {}) }, body: connection.localDescription?.sdp ?? offer.sdp });
      if (!response.ok) throw new Error(`Media server rejected the broadcast (${response.status}).`);
      const answer = await response.text();
      resourceUrl.current = response.headers.get('location') ? new URL(response.headers.get('location')!, endpoint).toString() : null;
      await connection.setRemoteDescription(new RTCSessionDescription({ type: 'answer', sdp: answer }));
    },
    stop,
  }), [onState, stop]);

  return <View style={styles.preview}>{stream ? <RTCView streamURL={stream.toURL()} objectFit="cover" mirror style={StyleSheet.absoluteFill} /> : null}<View style={styles.caption}><Text style={styles.captionText}>{message}</Text></View></View>;
});
WhipPublisher.displayName = 'WhipPublisher';
const styles = StyleSheet.create({ preview: { width: '100%', aspectRatio: 9 / 14, maxHeight: 540, borderRadius: 26, overflow: 'hidden', backgroundColor: '#11171B', alignItems: 'center', justifyContent: 'center' }, caption: { position: 'absolute', left: 12, right: 12, bottom: 12, borderRadius: 14, padding: 12, backgroundColor: 'rgba(0,0,0,.72)' }, captionText: { color: C.text, textAlign: 'center', fontWeight: '700' } });

