import React, { useState } from 'react';
import { Text, View } from 'react-native';
import { Button, Card, Muted, Page, Pill } from './UI';
import { C } from '../theme';

export function DemoStudio() {
  const [live, setLive] = useState(false);
  const [layout, setLayout] = useState('grid_4');
  const [people, setPeople] = useState(['You', 'Player Alpha 2', 'Player Beta 1', 'Player Beta 2']);
  const [muted, setMuted] = useState<string[]>([]);
  const [spotlight, setSpotlight] = useState('');
  return <Page eyebrow="Player tools" title="Creator studio" subtitle="Explore broadcast and host controls before connecting the media server.">
    <Card accent><Pill text="DEMO SIMULATION · NO MEDIA PUBLISHED" tone="gold" /><Muted>This rehearsal changes local screen state. Real camera broadcasting is available with Demo data switched off and a connected backend.</Muted></Card>
    <Button title={live ? 'Stop demo broadcast' : 'Start demo broadcast'} onPress={() => setLive(!live)} />
    <Card><Text style={{ color: C.text, fontWeight: '800' }}>{live ? 'Demo broadcast active' : 'Demo broadcast stopped'}</Text><Muted>Host: {people[0] ?? 'Session ended'} · {people.length}/4 participants</Muted><Muted>Layout: {layout}{spotlight ? ` · Spotlight: ${spotlight}` : ''}</Muted></Card>
    <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 8 }}>{['grid_2', 'grid_4', 'spotlight'].map(value => <Button key={value} title={value.replace('_', ' ')} secondary onPress={() => setLayout(value)} />)}</View>
    {people.map((person, index) => <Card key={person}><Text style={{ color: C.text, fontSize: 18, fontWeight: '800' }}>{person}{index === 0 ? ' · Host' : ''}</Text><Muted>{muted.includes(person) ? 'Microphone muted' : 'Microphone enabled'}</Muted><Button title={muted.includes(person) ? 'Unmute' : 'Mute'} secondary onPress={() => setMuted(current => current.includes(person) ? current.filter(item => item !== person) : [...current, person])} /><Button title="Spotlight" secondary onPress={() => { setSpotlight(person); setLayout('spotlight'); }} />{index > 0 ? <Button title="Remove participant" danger onPress={() => setPeople(current => current.filter(item => item !== person))} /> : null}</Card>)}
    <Button title="Invite demo participant" disabled={people.length >= 4} secondary onPress={() => setPeople(current => [...current, `Invited player ${Date.now().toString().slice(-4)}`])} />
    <Button title="Simulate host disconnect" disabled={!people.length} secondary onPress={() => { setPeople(current => current.slice(1)); setSpotlight(''); }} />
    <Muted>Host handoff here is a rehearsal. In connected mode the backend elects and announces the next host.</Muted>
  </Page>;
}
