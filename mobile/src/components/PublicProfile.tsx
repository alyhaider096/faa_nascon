import { Ionicons } from '@expo/vector-icons';
import { router } from 'expo-router';
import React, { useEffect, useState } from 'react';
import { ActivityIndicator, Linking, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { PublicProfile as Profile, day2BaseUrl, loadProfile } from '../data/day2';
import { useApp } from '../state/AppContext';
import { C, DISPLAY_FONT } from '../theme';

export function PublicProfile({ type, id }: { type: 'player' | 'club'; id: string }) {
  const { serverUrl, account, authorizedRequest } = useApp();
  const [profile, setProfile] = useState<Profile | null>(null);
  const [error, setError] = useState('');
  const [following, setFollowing] = useState(false);
  const [followBusy, setFollowBusy] = useState(false);
  useEffect(() => { let active = true; loadProfile(serverUrl, type, id).then(data => active && setProfile(data)).catch(cause => active && setError(cause instanceof Error ? cause.message : 'Profile unavailable.')); return () => { active = false; }; }, [id, serverUrl, type]);
  return <ScrollView style={styles.screen} contentContainerStyle={styles.content}>
    <View style={styles.nav}><Pressable accessibilityRole="button" accessibilityLabel="Back" onPress={() => router.canGoBack() ? router.back() : router.replace('/login')} style={styles.icon}><Ionicons name="arrow-back" size={22} color={C.text} /></Pressable><Text style={styles.navTitle}>LEAGUEOPS PROFILE</Text></View>
    {!profile && !error ? <ActivityIndicator color={C.accent} size="large" style={{ marginTop: 100 }} /> : null}
    {error ? <View style={styles.card}><Text accessibilityRole="alert" style={styles.error}>{error}</Text></View> : null}
    {profile ? <>
      <View style={styles.hero}><Text style={styles.eyebrow}>{type.toUpperCase()}</Text><Text style={styles.title}>{profile.name}</Text><Text style={styles.subtitle}>{profile.subtitle}{profile.affiliation ? ` · ${profile.affiliation}` : ''}</Text>{profile.followers !== undefined ? <Text style={styles.followers}>{profile.followers.toLocaleString()} followers</Text> : null}<Pressable accessibilityRole="button" disabled={followBusy} onPress={async () => {
        if (!account) { router.push('/login'); return; }
        setFollowBusy(true); setError('');
        try {
          const result = await authorizedRequest<{ following: boolean; followers?: number }>('/api/v1/follows', { entity_type: type, entity_id: id, action: following ? 'unfollow' : 'follow' });
          setFollowing(result.following);
          if (result.followers !== undefined) setProfile(current => current ? { ...current, followers: result.followers } : current);
        } catch (cause) { setError(cause instanceof Error ? cause.message : 'Could not update this follow.'); }
        finally { setFollowBusy(false); }
      }} style={[styles.follow, followBusy && { opacity: 0.65 }]}><Text style={styles.followText}>{!account ? 'Sign in to follow' : followBusy ? 'Updating…' : following ? 'Following' : 'Follow'}</Text></Pressable></View>
      <Section title="Upcoming fixtures" empty="No upcoming fixtures have been announced.">{profile.upcomingFixtures.map(item => <MatchLink key={item.id} id={item.id} title={item.title} meta={item.startsAt ?? 'Scheduled'} />)}</Section>
      <Section title="Career matches" empty="No career match history is available.">{profile.careerMatches.map(item => <MatchLink key={item.id} id={item.id} title={item.title} meta={item.status} />)}</Section>
      <Section title="VOD archive" empty="No completed stream recordings yet.">{profile.vod.map(item => <MatchLink key={item.id} id={item.id} title={item.title} meta="Watch recording" vod />)}</Section>
      {(account?.role === 'league_organizer' || account?.role === 'super_admin') ? <View style={{ marginTop: 24 }}><Text style={styles.section}>QR exports</Text><View style={styles.exportRow}>{(['svg', 'png', 'pdf'] as const).map(format => <Pressable key={format} accessibilityRole="link" onPress={() => void Linking.openURL(`${day2BaseUrl(serverUrl)}/audit/v1/qr/${encodeURIComponent(id)}/export.${format}`)} style={styles.exportButton}><Ionicons name="download-outline" color={C.text} size={19} /><Text style={styles.exportText}>{format.toUpperCase()}</Text></Pressable>)}</View></View> : null}
    </> : null}
  </ScrollView>;
}
function Section({ title, empty, children }: { title: string; empty: string; children: React.ReactNode[] }) { return <View style={{ marginTop: 24 }}><Text style={styles.section}>{title}</Text>{children.length ? children : <Text style={styles.muted}>{empty}</Text>}</View>; }
function MatchLink({ id, title, meta, vod }: { id: string; title: string; meta: string; vod?: boolean }) { return <Pressable accessibilityRole="button" onPress={() => router.push(`/web/matches/${id}/${vod ? 'vod' : 'preview'}`)} style={styles.row}><View style={{ flex: 1 }}><Text style={styles.rowTitle}>{title}</Text><Text style={styles.muted}>{meta}</Text></View><Ionicons name="chevron-forward" color={C.accent} size={21} /></Pressable>; }
const styles = StyleSheet.create({ screen: { flex: 1, backgroundColor: C.bg }, content: { width: '100%', maxWidth: 900, alignSelf: 'center', padding: 20, paddingBottom: 70 }, nav: { minHeight: 62, flexDirection: 'row', alignItems: 'center', gap: 14 }, icon: { width: 48, height: 48, borderRadius: 24, alignItems: 'center', justifyContent: 'center', backgroundColor: C.surface2 }, navTitle: { color: C.text, fontWeight: '900', letterSpacing: 1.2 }, hero: { backgroundColor: C.surface, borderRadius: 28, padding: 24, marginTop: 18 }, eyebrow: { color: C.accent, fontSize: 11, fontWeight: '900', letterSpacing: 1.4 }, title: { color: C.text, fontSize: 36, fontFamily: DISPLAY_FONT, fontWeight: '900', textTransform: 'uppercase', marginTop: 7 }, subtitle: { color: C.muted, fontSize: 16, marginTop: 7 }, followers: { color: C.text, fontWeight: '800', marginTop: 14 }, follow: { minHeight: 48, alignSelf: 'flex-start', borderRadius: 24, backgroundColor: C.accent, paddingHorizontal: 20, alignItems: 'center', justifyContent: 'center', marginTop: 14 }, followText: { color: C.bg, fontWeight: '900' }, section: { color: C.text, fontSize: 21, fontWeight: '900', textTransform: 'uppercase', marginBottom: 10 }, row: { minHeight: 70, backgroundColor: C.surface, borderRadius: 18, marginBottom: 9, padding: 15, flexDirection: 'row', alignItems: 'center', gap: 12 }, rowTitle: { color: C.text, fontWeight: '800', marginBottom: 4 }, muted: { color: C.muted, lineHeight: 21 }, card: { backgroundColor: C.surface, borderRadius: 20, padding: 18, marginTop: 30 }, error: { color: C.danger }, exportRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 }, exportButton: { minHeight: 48, borderRadius: 24, backgroundColor: C.surface2, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 7, paddingHorizontal: 18 }, exportText: { color: C.text, fontWeight: '900' } });

