import { router } from 'expo-router';
import React from 'react';
import { MatchCard } from '../../components/MatchCard';
import { Muted, Page, SectionTitle } from '../../components/UI';
import { useApp } from '../../state/AppContext';

export default function Fixtures() {
  const { fixtures, account } = useApp();
  return <Page eyebrow="Match centre" title="Fixtures" subtitle={`Live scores and upcoming games · ${account?.label ?? 'Guest'}`}>
    {fixtures[0] ? <MatchCard fixture={fixtures[0]} featured onPress={() => router.push({ pathname: '/match/[id]', params: { id: fixtures[0].id } })} /> : null}
    <SectionTitle title="All matches" action={`${fixtures.length} fixtures`} />
    {fixtures.length ? fixtures.map(f => <MatchCard key={f.id} fixture={f} onPress={() => router.push({ pathname: '/match/[id]', params: { id: f.id } })} />) : <Muted>No matches yet. Check back after a league is created.</Muted>}
  </Page>;
}
