import { useEvent } from 'expo';
import { VideoSource, VideoView, useVideoPlayer } from 'expo-video';
import React, { forwardRef, useEffect, useImperativeHandle, useMemo } from 'react';
import { StyleSheet, Text, View } from 'react-native';
import { C } from '../theme';

export type LiveVideoHandle = { currentTime: () => number; restore: (seconds: number, shouldPlay: boolean) => void; isPlaying: () => boolean };

export const LiveVideo = forwardRef<LiveVideoHandle, { uri: string | null; label: string }>(({ uri, label }, ref) => {
  const source: VideoSource | null = useMemo(() => uri ? { uri, contentType: uri.includes('.m3u8') ? 'hls' : 'auto' } : null, [uri]);
  const player = useVideoPlayer(source, instance => { instance.timeUpdateEventInterval = 0.25; });
  const { isPlaying } = useEvent(player, 'playingChange', { isPlaying: player.playing });
  useEffect(() => { void player.replaceAsync(source); }, [player, source]);
  useImperativeHandle(ref, () => ({ currentTime: () => player.currentTime, restore: (seconds, shouldPlay) => { player.currentTime = Math.max(0, seconds); if (shouldPlay) player.play(); }, isPlaying: () => player.playing }), [player]);
  if (!uri) return <Empty label={label} />;
  return <View testID="guest-video-player" accessibilityLabel={`${label} video player`} style={styles.frame}>
    <VideoView player={player} style={StyleSheet.absoluteFill} nativeControls contentFit="contain" surfaceType="textureView" />
    {!isPlaying ? <View pointerEvents="none" style={styles.status}><Text style={styles.statusText}>Tap play to watch live</Text></View> : null}
  </View>;
});
LiveVideo.displayName = 'LiveVideo';
function Empty({ label }: { label: string }) { return <View testID="guest-video-player" accessibilityLabel={`${label}. Stream unavailable`} style={styles.empty}><Text style={styles.kicker}>STREAM NOT AVAILABLE</Text><Text style={styles.message}>The broadcaster has not published a playable stream yet. Score and chat updates remain live.</Text></View>; }
const styles = StyleSheet.create({ frame: { width: '100%', aspectRatio: 16 / 9, borderRadius: 24, overflow: 'hidden', backgroundColor: '#000', position: 'relative' }, empty: { width: '100%', aspectRatio: 16 / 9, borderRadius: 24, backgroundColor: '#141B20', alignItems: 'center', justifyContent: 'center', padding: 28 }, kicker: { color: C.gold, fontSize: 12, fontWeight: '900', letterSpacing: 1.4, marginBottom: 8 }, message: { color: C.text, fontSize: 15, lineHeight: 22, textAlign: 'center', maxWidth: 430 }, status: { position: 'absolute', left: 12, bottom: 12, backgroundColor: 'rgba(0,0,0,.75)', borderRadius: 18, paddingHorizontal: 14, paddingVertical: 9 }, statusText: { color: '#FFF', fontWeight: '800', fontSize: 12 } });
