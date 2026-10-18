import { router } from 'expo-router';
import React from 'react';
import { ImageBackground, Text, View } from 'react-native';
import { MatchCard } from '../../components/MatchCard';
import { Button, Card, Muted, Page, SectionTitle } from '../../components/UI';
import { canManageRoster, canScore, useApp } from '../../state/AppContext';
import { C, DISPLAY_FONT } from '../../theme';

export default function Fixtures() {
  const { fixtures, account, demoMode } = useApp();
  const featured = fixtures.find(item => item.status === 'Live') ?? fixtures[0];
  const remaining = fixtures.filter(item => item.id !== featured?.id);
  return <Page eyebrow="Match centre" title="Fixtures" subtitle={`Live scores and upcoming games · ${account?.label ?? 'Guest'}`}>
    <Card accent><Text style={{ color: C.text, fontWeight: '900', fontSize: 20 }}>{account?.label ?? 'Match centre'}</Text><Muted>{demoMode ? 'Interactive demo · actions change this device only.' : 'Connected workspace · permissions are checked by the server.'}</Muted>
      {canScore(account?.role) ? <><Muted>Record scoring events and append corrections for your league.</Muted><Button title="Record match event" disabled={!fixtures.some(item => item.status === 'Live')} onPress={() => router.push({ pathname: '/score', params: { id: fixtures.find(item => item.status === 'Live')!.id } })} /></> : null}
      {canManageRoster(account?.role) ? <><Muted>Add, transfer, loan or release club players.</Muted><Button title="Manage club roster" onPress={() => router.push('/roster')} /></> : null}
      {account?.role === 'player' || account?.role === 'super_admin' ? <><Muted>Start a broadcast and explore co-stream host controls.</Muted><Button title="Open creator studio" onPress={() => router.push('/creator')} /></> : null}
      {account?.role === 'viewer' ? <Muted>Watch matches, browse standings and shop team merchandise.</Muted> : null}
    </Card>
    <ImageBackground source={require('../../../assets/football-matchday.png')} resizeMode="cover" imageStyle={{ borderRadius: 16 }} style={{ height: 146, marginBottom: 18, overflow: 'hidden', borderRadius: 16 }} accessibilityLabel="Football matchday atmosphere">
      <View style={{ flex: 1, justifyContent: 'space-between', padding: 17, backgroundColor: 'rgba(9, 13, 16, 0.14)' }}>
        <Text style={{ color: C.text, fontSize: 11, fontWeight: '900', letterSpacing: 1.3 }}>LEAGUEOPS  /  MATCHDAY</Text>
        <View><Text style={{ color: C.text, fontFamily: DISPLAY_FONT, fontSize: 25, lineHeight: 26, fontWeight: '900', letterSpacing: -.5, textShadowColor: '#000000', textShadowRadius: 5 }}>EVERY MOMENT{'\n'}COUNTS</Text><Text numberOfLines={1} style={{ color: C.text, fontSize: 12, fontWeight: '700', textShadowColor: '#000000', textShadowRadius: 5 }}>{fixtures.length} fixtures · live scores and detail</Text></View>
      </View>
    </ImageBackground>
    {featured ? <MatchCard fixture={featured} featured onPress={() => router.push({ pathname: '/match/[id]', params: { id: featured.id } })} /> : null}
    <SectionTitle title="More matches" action={`${fixtures.length} total`} />
    {remaining.length ? remaining.map(f => <MatchCard key={f.id} fixture={f} onPress={() => router.push({ pathname: '/match/[id]', params: { id: f.id } })} />) : featured ? <Muted>No other matches scheduled yet.</Muted> : <Muted>No matches yet. Check back after a league is created.</Muted>}
  </Page>;
}
