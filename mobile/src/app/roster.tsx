import { router } from 'expo-router';
import React, { useState } from 'react';
import { Alert, Text } from 'react-native';
import { Button, Card, Field, Muted, Page, Pill } from '../components/UI';
import { canManageRoster, useApp } from '../state/AppContext';
import { C } from '../theme';

export default function Roster() {
  const { account, club, queueAction, online } = useApp();
  const [action, setAction] = useState<'add' | 'transfer' | 'loan' | 'release'>('transfer');
  const [player, setPlayer] = useState('player-alpha-1');
  const [destination, setDestination] = useState('squad-alpha-2');
  const [reason, setReason] = useState('Squad rotation');
  const [feedback, setFeedback] = useState('');
  if (!canManageRoster(account?.role)) return <Page title="Roster management"><Muted>Your role cannot change the roster.</Muted></Page>;
  async function submit() {
    if (action === 'add') { setFeedback('Adding a new player needs the roster registration API. Use transfer, loan or release for offline queueing.'); return; }
    if (!player.trim() || !reason.trim() || (action !== 'release' && !destination.trim())) { setFeedback('Enter the player, destination and reason.'); return; }
    await queueAction({ type: 'roster_transfer', base_version: 0, label: `${action} · ${player}`, payload: { request_id: `req-${Date.now()}`, league_id: 'league-alpha-1', player_id: player.trim(), type: action, from_squad_id: 'squad-alpha-1', to_squad_id: action === 'release' ? null : destination.trim(), effective_date: new Date().toISOString().slice(0, 10), loan_end_date: action === 'loan' ? '2026-11-01' : null, reason: reason.trim(), requested_by: account?.email } });
    setFeedback(online ? 'Action saved. Open the sync queue to review its result.' : 'Saved offline. It will sync after reconnection.');
  }
  return <Page eyebrow="Club manager tools" title="Manage roster" subtitle="Changes are recorded in the offline action queue until confirmed by the server.">
    <Card accent><Pill text={online ? 'CONNECTED' : 'OFFLINE · QUEUE ACTIVE'} tone={online ? 'mint' : 'gold'} /><Text style={{ color: C.text, fontWeight: '800', fontSize: 17, marginTop: 12 }}>{club.name}</Text><Muted>Squad changes keep a dated audit trail.</Muted></Card>
    <Text style={{ color: C.text, fontSize: 18, fontWeight: '800', marginBottom: 10 }}>Choose action</Text>
    {(['add', 'transfer', 'loan', 'release'] as const).map(value => <Card key={value} accent={action === value} onPress={() => setAction(value)}><Text style={{ color: action === value ? C.accent : C.text, fontWeight: '800', textTransform: 'capitalize' }}>{value}</Text></Card>)}
    <Field label="Player ID" value={player} onChangeText={setPlayer} />
    {action !== 'release' ? <Field label="Destination squad ID" value={destination} onChangeText={setDestination} /> : null}
    <Field label="Reason" value={reason} onChangeText={setReason} multiline />
    {feedback ? <Text style={{ color: C.accent, marginBottom: 8 }}>{feedback}</Text> : null}
    <Button title={`Confirm ${action}`} danger={action === 'release'} onPress={() => Alert.alert(`Confirm ${action}`, `Queue this ${action} action for ${player}?`, [{ text: 'Cancel', style: 'cancel' }, { text: 'Confirm', onPress: () => void submit() }])} />
    <Button title="View pending actions" secondary onPress={() => router.push('/queue')} />
    <Muted>Add-player details and transfer rules will be validated by the backend when its mobile API is connected.</Muted>
  </Page>;
}
