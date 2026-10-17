import { router } from 'expo-router';
import React from 'react';
import { MatchCard } from '../../components/MatchCard';
import { Muted, Page, SectionTitle } from '../../components/UI';
import { useApp } from '../../state/AppContext';

export default function Fixtures() {
  const { fixtures, account } = useApp();
  const featured = fixtures.find(item => item.status === 'Live') ?? fixtures[0];
  const remaining = fixtures.filter(item => item.id !== featured?.id);
  return <Page eyebrow="Match centre" title="Fixtures" subtitle={`Live scores and upcoming games · ${account?.label ?? 'Guest'}`}>
    {featured ? <MatchCard fixture={featured} featured onPress={() => router.push({ pathname: '/match/[id]', params: { id: featured.id } })} /> : null}
    <SectionTitle title="More matches" action={`${fixtures.length} total`} />
    {remaining.length ? remaining.map(f => <MatchCard key={f.id} fixture={f} onPress={() => router.push({ pathname: '/match/[id]', params: { id: f.id } })} />) : featured ? <Muted>No other matches scheduled yet.</Muted> : <Muted>No matches yet. Check back after a league is created.</Muted>}
  </Page>;
}
