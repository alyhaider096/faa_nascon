import React from 'react';
import { Text, View } from 'react-native';
import { Fixture } from '../data/mock';
import { C, DISPLAY_FONT } from '../theme';
import { Card, Pill } from './UI';

function Team({ name }: { name: string }) {
  const initials = name.split(/\s+/).slice(0, 2).map(part => part[0]).join('').toUpperCase();
  return <View style={{ flex: 1, alignItems: 'center', minWidth: 0 }}>
    <View style={{ width: 43, height: 43, borderRadius: 22, backgroundColor: C.surface2, borderWidth: 1, borderColor: C.line, alignItems: 'center', justifyContent: 'center', marginBottom: 9 }}>
      <Text style={{ color: C.text, fontSize: 14, fontWeight: '900' }}>{initials}</Text>
    </View>
    <Text numberOfLines={2} style={{ color: C.text, fontSize: 14, fontWeight: '800', textAlign: 'center', lineHeight: 18 }}>{name}</Text>
  </View>;
}

export function MatchCard({ fixture, featured = false, onPress }: { fixture: Fixture; featured?: boolean; onPress?: () => void }) {
  return <Card accent={featured} onPress={onPress}>
    <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}>
      <Text numberOfLines={1} style={{ color: C.muted, fontSize: 11, fontWeight: '800', flex: 1 }}>{fixture.league.toUpperCase()}  ·  {fixture.sport.toUpperCase()}</Text>
      <Pill text={fixture.status.toUpperCase()} tone={fixture.status === 'Live' ? 'mint' : 'blue'} />
    </View>
    <View style={{ flexDirection: 'row', alignItems: 'center', gap: 7, marginTop: featured ? 24 : 18, marginBottom: 18 }}>
      <Team name={fixture.home} />
      <View style={{ minWidth: featured ? 95 : 80, alignItems: 'center' }}>
        <Text style={{ color: C.text, fontFamily: DISPLAY_FONT, fontSize: featured ? 46 : 32, fontWeight: '900', letterSpacing: -1.5 }}>{fixture.score}</Text>
        <Text style={{ color: fixture.status === 'Live' ? C.accent : C.muted, fontSize: 11, fontWeight: '800', marginTop: 5 }}>{fixture.status === 'Live' ? 'LIVE NOW' : fixture.time}</Text>
      </View>
      <Team name={fixture.away} />
    </View>
    <View style={{ borderTopWidth: 1, borderTopColor: C.line, paddingTop: 11, flexDirection: 'row', justifyContent: 'space-between', gap: 6 }}>
      <Text numberOfLines={1} style={{ color: C.muted, fontSize: 12, flex: 1 }}>{fixture.venue}</Text>
      {onPress ? <Text style={{ color: C.accent, fontSize: 12, fontWeight: '900', letterSpacing: .3 }}>MATCH CENTRE  →</Text> : null}
    </View>
  </Card>;
}
