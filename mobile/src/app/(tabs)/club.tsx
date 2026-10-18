import { router } from 'expo-router';
import React from 'react';
import { Text, View } from 'react-native';
import { BrandMark, Button, Card, Muted, Page, Pill, SectionTitle } from '../../components/UI';
import { canManageRoster, useApp } from '../../state/AppContext';
import { C } from '../../theme';

export default function Club() {
  const { club, account, demoMode, logout } = useApp();
  return <Page eyebrow="Club profile" title={club.name} subtitle="Roster, staff, and home venue.">
    <Card accent><BrandMark /><Pill text={club.tag} /><Text style={{ color: C.text, fontSize: 17, fontWeight: '700', marginTop: 15 }}>Home ground · {club.venue}</Text></Card>
    <SectionTitle title="First team roster" action={`${club.roster.length} players`} />
    {club.roster.length ? club.roster.map(p => <Card key={p.id ?? p.name}><View style={{ flexDirection: 'row', alignItems: 'center', gap: 13 }}><Text style={{ color: C.accent, fontSize: 24, fontWeight: '800', width: 32 }}>{p.number}</Text><View style={{ flex: 1 }}><Text style={{ color: C.text, fontSize: 16, fontWeight: '800' }}>{p.name}</Text><Muted>{p.position} {p.role}</Muted></View></View></Card>) : <Muted>No players registered for this club yet.</Muted>}
    {canManageRoster(account?.role) ? <Button title="Manage roster  →" onPress={() => router.push('/roster')} /> : null}
    {(account?.role === 'player' || account?.role === 'super_admin') ? <Button title="Open creator studio  →" onPress={() => router.push('/creator')} /> : null}
    <Button title="Scan match QR" secondary onPress={() => router.push('/scanner')} />
    <Button title="App settings" secondary onPress={() => router.push('/settings')} />
    <Button title={demoMode ? 'Switch demo account' : 'Sign out'} secondary onPress={() => void logout().then(() => router.replace('/login'))} />
    <SectionTitle title="Club staff" />
    <Card>{club.staff.map(s => <Text key={s} style={{ color: C.text, marginVertical: 6 }}>{s}</Text>)}</Card>
    <SectionTitle title="About this club" />
    <Muted>Home venue: {club.venue}. Historical statistics and social channels will load from the connected backend.</Muted>
  </Page>;
}
