import { router, useLocalSearchParams } from 'expo-router';
import React, { useState } from 'react';
import { Alert, Text } from 'react-native';
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
    <Field label="Team ID" value={team} onChangeText={setTeam} />
    <Field label="Scoring event type" value={eventType} onChangeText={setEventType} placeholder="From sport configuration" />
    <Muted>Configured event types: {fixture?.eventTypes.join(', ') || 'Load a match to see its options.'}</Muted>
    <Button title="Add scoring event" onPress={() => void submit(false)} />
    <Text style={{ color: C.text, fontSize: 18, fontWeight: '800', marginTop: 23, marginBottom: 10 }}>Correct an event</Text>
    <Field label="Event ID to compensate" value={compensates} onChangeText={setCompensates} placeholder="evt-..." />
    <Button title="Append correction" secondary onPress={() => Alert.alert('Confirm correction', 'The original event will remain in the audit log.', [{ text: 'Cancel', style: 'cancel' }, { text: 'Append', onPress: () => void submit(true) }])} />
    {feedback ? <Text style={{ color: C.accent, marginTop: 10 }}>{feedback}</Text> : null}
    <Button title="Open sync queue" secondary onPress={() => router.push('/queue')} />
  </Page>;
}
