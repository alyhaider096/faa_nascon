import { router } from 'expo-router';
import React from 'react';
import { Text, View } from 'react-native';
import { Button, Card, Muted, Page, Pill, SectionTitle } from '../../components/UI';
import { useApp } from '../../state/AppContext';
import { C } from '../../theme';

export default function Standings() {
  const { standings, fixtures } = useApp();
  return <Page eyebrow="League table" title="Standings" subtitle="Capital League · 2026 season">
    <Card accent><Text style={{ color: C.muted, fontSize: 12 }}>TOP OF THE TABLE</Text><Text style={{ color: C.text, fontSize: 25, fontWeight: '800', marginTop: 8 }}>{standings[0]?.team ?? 'No teams'}</Text><Text style={{ color: C.accent, fontSize: 15, marginTop: 5 }}>{standings[0]?.points ?? 0} pts · {standings[0]?.status ?? ''}</Text></Card>
    <SectionTitle title="Rankings" action={`${standings.length} clubs`} />
    {standings.length ? standings.map((row, i) => <Card key={row.team}>
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 12 }}><Text style={{ color: C.accent, fontSize: 19, fontWeight: '800', width: 25 }}>{i + 1}</Text><View style={{ flex: 1 }}><Text numberOfLines={1} style={{ color: C.text, fontWeight: '800', fontSize: 16 }}>{row.team}</Text><Text style={{ color: C.muted, fontSize: 12, marginTop: 3 }}>P {row.played}  ·  W {row.won}  ·  D {row.drawn}  ·  L {row.lost}  ·  GD {row.diff > 0 ? '+' : ''}{row.diff}</Text></View><View style={{ alignItems: 'center' }}><Text style={{ color: C.text, fontSize: 22, fontWeight: '800' }}>{row.points}</Text><Text style={{ color: C.muted, fontSize: 10, fontWeight: '800' }}>PTS</Text></View></View>
      <View style={{ marginTop: 12 }}><Pill text={row.status} tone={row.status === 'Clinched' ? 'mint' : row.status === 'Eliminated' ? 'red' : 'gold'} /></View>
    </Card>) : <Muted>No standings yet. Completed matches will appear here.</Muted>}
    <SectionTitle title="Next match" />
    <Button title={`Open ${fixtures[0]?.home ?? 'match'} match  →`} secondary onPress={() => fixtures[0] && router.push({ pathname: '/match/[id]', params: { id: fixtures[0].id } })} />
  </Page>;
}
