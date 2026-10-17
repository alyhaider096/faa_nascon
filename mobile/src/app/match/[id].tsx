import { router, useLocalSearchParams } from 'expo-router';
import React from 'react';
import { Text } from 'react-native';
import { Button, Card, Muted, Page, Pill, SectionTitle } from '../../components/UI';
import { MatchCard } from '../../components/MatchCard';
import { canScore, useApp } from '../../state/AppContext';
import { PRODUCTS } from '../../data/mock';
import { C } from '../../theme';

export default function MatchDetail() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const { fixtures, account } = useApp();
  const f = fixtures.find(x => x.id === id);
  if (!f) return <Page title="Match not found"><Muted>This match is unavailable.</Muted></Page>;
  const pinned = PRODUCTS.find(product => product.id === f.pinnedProductId);
  return <Page eyebrow={`${f.sport} · ${f.league}`} title="Match centre" subtitle={`${f.time} · ${f.venue}`}>
    <MatchCard fixture={f} featured />
    {canScore(account?.role) ? <Button title="Enter scoring event  →" onPress={() => router.push({ pathname: '/score', params: { id: f.id } })} /> : null}
    <SectionTitle title="Event timeline" />
    {f.events.length ? f.events.map((event, index) => <Card key={`${event.clock}-${index}`}><Text style={{ color: C.accent, fontWeight: '800' }}>{event.clock} · {event.label} · {event.team}</Text></Card>) : <Muted>No events yet. Updates will appear here when the match starts.</Muted>}
    <SectionTitle title="Pinned matchday product" />
    {pinned ? <Card onPress={() => router.push({ pathname: '/product/[id]', params: { id: pinned.id } })}><Pill text="SHOP THE MATCH" /><Text style={{ color: C.text, fontSize: 18, fontWeight: '800', marginTop: 12 }}>{pinned.name}  →</Text><Muted>Choose a variant and check out with the mock gateway.</Muted></Card> : <Muted>No product is pinned to this match yet.</Muted>}
  </Page>;
}
