import { router, useLocalSearchParams } from 'expo-router';
import React, { useState } from 'react';
import { Alert, Pressable, Text, View } from 'react-native';
import { Button, Card, Field, Muted, Page, Pill } from '../components/UI';
import { canScore, useApp } from '../state/AppContext';
import { C } from '../theme';

export default function Score() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const { account, online, queueAction, fixtures } = useApp();
  const fixture = fixtures.find(item => item.id === id);
  const [team, setTeam] = useState(fixture?.homeId ?? '');
  const [eventType, setEventType] = useState(fixture?.eventTypes[0] ?? '');
  const [compensates, setCompensates] = useState('');
  const [feedback, setFeedback] = useState('');
  if (!canScore(account?.role)) return <Page title="Scoring"><Muted>Your role cannot record scores.</Muted></Page>;
  async function submit(compensation: boolean) {
    if (compensation && !compensates.trim()) { setFeedback('Enter the event ID to correct.'); return; }
    if (!compensation && (!team.trim() || !eventType.trim())) { setFeedback('Choose a team and event type.'); return; }
    const payload = compensation ? { compensates: compensates.trim(), reason: 'Organizer correction' } : { team_id: team.trim(), event_type: eventType.trim() };
    await queueAction({ type: 'score_event', base_version: fixture?.version ?? 0, label: compensation ? `Correct ${compensates}` : `${eventType} · ${team}`, payload: { event_id: `evt-${Date.now()}`, match_id: id ?? '', type: compensation ? 'compensation' : 'score', payload } });
    setFeedback(online ? 'Event saved to the sync queue.' : 'Event saved offline. It will sync after reconnection.');
  }
  return <Page eyebrow="League organizer tools" title="Scoring entry" subtitle={`Match ${id ?? ''} · append-only event log`}>
    <Card accent><Pill text={online ? 'CONNECTED' : 'OFFLINE · QUEUE ACTIVE'} tone={online ? 'mint' : 'gold'} /><Text style={{ color: C.text, fontWeight: '800', marginTop: 12 }}>Every correction creates a new event.</Text><Muted>The backend signs each accepted event with the team salt.</Muted></Card>
    <Text style={{ color: C.text, fontSize: 18, fontWeight: '800', marginBottom: 10 }}>Which team?</Text>
    <View style={{ flexDirection: 'row', gap: 10, marginBottom: 16 }}>
      {fixture ? [{ id: fixture.homeId, label: fixture.home }, { id: fixture.awayId, label: fixture.away }].map(option => <Pressable key={option.id} onPress={() => setTeam(option.id)} accessibilityRole="button" accessibilityState={{ selected: team === option.id }} style={{ flex: 1, minHeight: 54, padding: 10, justifyContent: 'center', borderRadius: 12, borderWidth: 1, backgroundColor: team === option.id ? C.surface2 : C.surface, borderColor: team === option.id ? C.accent : C.line }}><Text numberOfLines={2} style={{ color: team === option.id ? C.accent : C.text, fontWeight: '800', textAlign: 'center' }}>{option.label}</Text></Pressable>) : <Muted>Open a match first to choose its teams.</Muted>}
    </View>
    <Text style={{ color: C.text, fontSize: 18, fontWeight: '800', marginBottom: 10 }}>What happened?</Text>
    <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 8, marginBottom: 15 }}>
      {fixture?.eventTypes.map(value => <Pressable key={value} onPress={() => setEventType(value)} accessibilityRole="button" accessibilityState={{ selected: eventType === value }} style={{ minHeight: 48, paddingHorizontal: 14, borderRadius: 24, borderWidth: 1, borderColor: eventType === value ? C.accent : C.line, backgroundColor: eventType === value ? C.surface2 : C.surface, justifyContent: 'center' }}><Text style={{ color: eventType === value ? C.accent : C.text, fontWeight: '700' }}>{value.replaceAll('_', ' ')}</Text></Pressable>)}
    </View>
    <Button title="Add scoring event" onPress={() => void submit(false)} />
    <Text style={{ color: C.text, fontSize: 18, fontWeight: '800', marginTop: 23, marginBottom: 10 }}>Correct an event</Text>
    <Field label="Event ID to compensate" value={compensates} onChangeText={setCompensates} placeholder="evt-..." />
    <Button title="Append correction" secondary onPress={() => Alert.alert('Confirm correction', 'The original event will remain in the audit log.', [{ text: 'Cancel', style: 'cancel' }, { text: 'Append', onPress: () => void submit(true) }])} />
    {feedback ? <Text style={{ color: C.accent, marginTop: 10 }}>{feedback}</Text> : null}
    <Button title="Open sync queue" secondary onPress={() => router.push('/queue')} />
  </Page>;
}
