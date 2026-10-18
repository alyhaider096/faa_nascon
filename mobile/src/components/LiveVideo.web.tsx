import HlsJs from 'hls.js';
import React, { forwardRef, useEffect, useImperativeHandle, useRef, useState } from 'react';
import { StyleSheet, Text, View } from 'react-native';
import { C } from '../theme';

export type LiveVideoHandle = { currentTime: () => number; restore: (seconds: number, shouldPlay: boolean) => void; isPlaying: () => boolean };

export const LiveVideo = forwardRef<LiveVideoHandle, { uri: string | null; label: string }>(({ uri, label }, ref) => {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const [problem, setProblem] = useState('');
  useImperativeHandle(ref, () => ({ currentTime: () => videoRef.current?.currentTime ?? 0, restore: (seconds, shouldPlay) => { const video = videoRef.current; if (!video) return; video.currentTime = Math.max(0, seconds); if (shouldPlay) void video.play().catch(() => undefined); }, isPlaying: () => Boolean(videoRef.current && !videoRef.current.paused) }), []);
  useEffect(() => {
    const video = videoRef.current;
    if (!video || !uri) return;
    setProblem('');
    // hls.js exposes these runtime statics on its default class despite the lint rule's named-export suggestion.
    // eslint-disable-next-line import/no-named-as-default-member
    if (uri.includes('.m3u8') && HlsJs.isSupported()) {
      const hls = new HlsJs({ lowLatencyMode: true, liveSyncDurationCount: 2 });
      hls.loadSource(uri); hls.attachMedia(video);
      // eslint-disable-next-line import/no-named-as-default-member
      hls.on(HlsJs.Events.ERROR, (_event, data) => { if (data.fatal) setProblem('The live stream disconnected. Retrying…'); });
      return () => hls.destroy();
    }
    video.src = uri;
    return () => { video.removeAttribute('src'); video.load(); };
  }, [uri]);
  if (!uri) return <View testID="guest-video-player" accessibilityLabel={`${label}. Stream unavailable`} style={styles.empty}><Text style={styles.kicker}>STREAM NOT AVAILABLE</Text><Text style={styles.message}>The broadcaster has not published a playable stream yet. Score and chat updates remain live.</Text></View>;
  return <View testID="guest-video-player" accessibilityLabel={`${label} video player`} style={styles.frame}>
    <video ref={videoRef} controls playsInline preload="metadata" aria-label={`${label} video player`} style={{ width: '100%', height: '100%', background: '#000', display: 'block' }} />
    {problem ? <View pointerEvents="none" style={styles.status}><Text style={styles.statusText}>{problem}</Text></View> : null}
  </View>;
});
LiveVideo.displayName = 'LiveVideo';
const styles = StyleSheet.create({ frame: { width: '100%', aspectRatio: 16 / 9, borderRadius: 24, overflow: 'hidden', backgroundColor: '#000', position: 'relative' }, empty: { width: '100%', aspectRatio: 16 / 9, borderRadius: 24, backgroundColor: '#141B20', alignItems: 'center', justifyContent: 'center', padding: 28 }, kicker: { color: C.gold, fontSize: 12, fontWeight: '900', letterSpacing: 1.4, marginBottom: 8 }, message: { color: C.text, fontSize: 15, lineHeight: 22, textAlign: 'center', maxWidth: 430 }, status: { position: 'absolute', left: 12, bottom: 12, backgroundColor: 'rgba(0,0,0,.78)', borderRadius: 18, paddingHorizontal: 14, paddingVertical: 9 }, statusText: { color: '#FFF', fontWeight: '800', fontSize: 12 } });
