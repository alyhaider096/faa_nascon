import React, { useState } from 'react';
import { Alert, Text } from 'react-native';
import { Button, Card, Muted, Page, Pill, SectionTitle } from '../components/UI';
import { useApp } from '../state/AppContext';
import { C } from '../theme';

export default function Queue() {
  const { queue, online, syncing, syncQueue, clearResolved, demoMode } = useApp();
  const [error, setError] = useState('');
  const pending = queue.filter(a => a.status === 'pending');
  return <Page eyebrow="Offline first" title="Sync queue" subtitle="Actions stay on this device across restarts until the server processes them.">
    <Card accent><Pill text={online ? 'NETWORK AVAILABLE' : 'OFFLINE'} tone={online ? 'mint' : 'red'} /><Text style={{ color: C.text, fontSize: 26, fontWeight: '800', marginTop: 12 }}>{pending.length} pending</Text><Muted>Score and roster changes are sent in the order they were created.</Muted></Card>
    {demoMode ? <Muted>Demo data is on. Turn it off in Settings to send pending actions to your backend.</Muted> : null}
    <Button title={syncing ? 'Syncing…' : 'Sync now'} disabled={!online || syncing || !pending.length || demoMode} onPress={() => void syncQueue().catch(() => setError('Could not reach the server. Your actions are still safely queued.'))} />
    {error ? <Text style={{ color: C.danger }}>{error}</Text> : null}
    <SectionTitle title="Actions" />
    {queue.length ? [...queue].reverse().map(action => <Card key={action.action_id}><Pill text={action.status.toUpperCase()} tone={action.status === 'rejected' ? 'red' : action.status === 'applied' ? 'mint' : 'gold'} /><Text style={{ color: C.text, fontWeight: '800', marginTop: 10 }}>{action.label}</Text><Muted>{action.type === 'score_event' ? 'Score event' : 'Roster change'} · {new Date(action.queued_at).toLocaleString()}</Muted>{action.resolution ? <Muted>{action.resolution}</Muted> : null}</Card>) : <Muted>No actions yet. Offline scoring and roster changes will appear here.</Muted>}
    {queue.some(action => action.status !== 'pending') ? <Button title="Clear completed results" secondary onPress={() => Alert.alert('Clear completed results?', 'Pending actions will be kept on this device.', [{ text: 'Cancel', style: 'cancel' }, { text: 'Clear', onPress: () => void clearResolved() }])} /> : null}
  </Page>;
}
