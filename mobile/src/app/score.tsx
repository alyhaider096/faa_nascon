import { router, useLocalSearchParams } from 'expo-router';
import React, { useState } from 'react';
import { Pressable, Text, View } from 'react-native';
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
  const [feedbackError, setFeedbackError] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [confirmCorrection, setConfirmCorrection] = useState(false);
  if (!canScore(account?.role)) return <Page title="Scoring"><Muted>Your role cannot record scores.</Muted></Page>;
  async function submit(compensation: boolean) {
    if (submitting) return;
    if (!id || !fixture) { setFeedbackError(true); setFeedback('Open a loaded match before submitting an event.'); return; }
    if (compensation && !compensates.trim()) { setFeedbackError(true); setFeedback('Enter the event ID to correct.'); return; }
    if (!compensation && (!team.trim() || !eventType.trim())) { setFeedbackError(true); setFeedback('Choose a team and event type.'); return; }
    setFeedback(''); setFeedbackError(false);
    const payload = compensation ? { compensates: compensates.trim(), reason: 'Organizer correction' } : { team_id: team.trim(), event_type: eventType.trim() };
    setSubmitting(true);
    try {
      const result = await queueAction({ type: 'score_event', base_version: fixture.version ?? 0, label: compensation ? `Correct ${compensates}` : `${eventType} · ${team}`, payload: { event_id: `evt-${Date.now()}`, match_id: id, type: compensation ? 'compensation' : 'score', payload } });
      setFeedbackError(result.status === 'rejected');
      setFeedback(`${result.status === 'rejected' ? 'Rejected: ' : ''}${result.resolution ?? 'Awaiting server confirmation.'}`);
      setConfirmCorrection(false);
    } catch (error) { setFeedbackError(true); setFeedback(error instanceof Error ? error.message : 'Could not save this event. Please retry.'); }
    finally { setSubmitting(false); }
  }
  return <Page eyebrow="League organizer tools" title="Scoring entry" subtitle={`Match ${id ?? ''} · append-only event log`}>
    <Card accent><Pill text={online ? 'CONNECTED' : 'OFFLINE · QUEUE ACTIVE'} tone={online ? 'mint' : 'gold'} /><Text style={{ color: C.text, fontWeight: '800', marginTop: 12 }}>Every correction creates a new event.</Text><Muted>The backend signs each accepted event with the team salt.</Muted></Card>
    <Text style={{ color: C.text, fontSize: 18, fontWeight: '800', marginBottom: 10 }}>Which team?</Text>
    <View style={{ flexDirection: 'row', gap: 10, marginBottom: 16 }}>
      {fixture ? [{ id: fixture.homeId, label: fixture.home }, { id: fixture.awayId, label: fixture.away }].map(option => <Pressable key={option.id} onPress={() => setTeam(option.id)} accessibilityRole="button" accessibilityState={{ selected: team === option.id }} style={({ pressed }) => ({ flex: 1, minHeight: 54, padding: 10, justifyContent: 'center', borderRadius: 18, backgroundColor: team === option.id ? C.accentDark : C.surface2, opacity: pressed ? .8 : 1 })}><Text numberOfLines={2} style={{ color: team === option.id ? C.accent : C.text, fontWeight: '800', textAlign: 'center' }}>{option.label}</Text></Pressable>) : <Muted>Open a match first to choose its teams.</Muted>}
    </View>
    <Text style={{ color: C.text, fontSize: 18, fontWeight: '800', marginBottom: 10 }}>What happened?</Text>
    <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 8, marginBottom: 15 }}>
      {fixture?.eventTypes.map(value => <Pressable key={value} onPress={() => setEventType(value)} accessibilityRole="button" accessibilityState={{ selected: eventType === value }} style={({ pressed }) => ({ minHeight: 48, paddingHorizontal: 15, borderRadius: 24, backgroundColor: eventType === value ? C.accentDark : C.surface2, justifyContent: 'center', opacity: pressed ? .8 : 1 })}><Text style={{ color: eventType === value ? C.accent : C.text, fontWeight: '700' }}>{value.replaceAll('_', ' ')}</Text></Pressable>)}
    </View>
    {!fixture?.eventTypes.length ? <Field label="Event type from league rules" value={eventType} onChangeText={setEventType} placeholder="Enter a configured event type" /> : null}
    <Button title="Add scoring event" loading={submitting} disabled={!fixture} onPress={() => void submit(false)} />
    <Text style={{ color: C.text, fontSize: 18, fontWeight: '800', marginTop: 23, marginBottom: 10 }}>Correct an event</Text>
    <Field label="Event ID to compensate" value={compensates} onChangeText={setCompensates} placeholder="evt-..." />
    {fixture?.events.filter(event => event.id).map(event => <Card key={event.id} onPress={() => setCompensates(event.id ?? '')}><Text style={{ color: C.text }}>{event.label} · {event.team}{compensates === event.id ? '  ✓' : ''}</Text></Card>)}
    <Button title="Append correction" secondary disabled={submitting || !fixture} onPress={() => setConfirmCorrection(true)} />
    {confirmCorrection ? <Card><Muted>The original event will remain in the audit log. Confirm this correction?</Muted><Button title="Confirm correction" loading={submitting} onPress={() => void submit(true)} /><Button title="Cancel correction" secondary disabled={submitting} onPress={() => setConfirmCorrection(false)} /></Card> : null}
    {feedback ? <Text accessibilityRole="alert" style={{ color: feedbackError ? C.danger : C.accent, marginTop: 10 }}>{feedback}</Text> : null}
    <Button title="Open sync queue" secondary onPress={() => router.push('/queue')} />
  </Page>;
}
