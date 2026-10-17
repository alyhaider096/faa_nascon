import { router } from 'expo-router';
import React, { useState } from 'react';
import { Alert, Pressable, Text, View } from 'react-native';
import { Button, Card, Field, Muted, Page, Pill } from '../components/UI';
import { canManageRoster, useApp } from '../state/AppContext';
import { C } from '../theme';

export default function Roster() {
  const { account, club, queueAction, addPlayer, online, demoMode } = useApp();
  const [action, setAction] = useState<'add' | 'transfer' | 'loan' | 'release'>('transfer');
  const [name, setName] = useState('');
  const [position, setPosition] = useState('');
  const [number, setNumber] = useState('');
  const [player, setPlayer] = useState('player-alpha-1');
  const [destination, setDestination] = useState('squad-alpha-2');
  const [reason, setReason] = useState('Squad rotation');
  const [feedback, setFeedback] = useState('');
  const [feedbackError, setFeedbackError] = useState(false);
  const actions = [
    { id: 'add', title: 'Add player', detail: 'Register a new squad member' },
    { id: 'transfer', title: 'Transfer', detail: 'Move to another squad' },
    { id: 'loan', title: 'Loan', detail: 'Temporary move' },
    { id: 'release', title: 'Release', detail: 'Remove from squad' },
  ] as const;
  if (!canManageRoster(account?.role)) return <Page title="Roster management"><Muted>Your role cannot change the roster.</Muted></Page>;
  async function submit() {
    if (action === 'add') {
      const shirtNumber = Number(number);
      if (!name.trim() || !position.trim() || !Number.isInteger(shirtNumber) || shirtNumber < 1 || shirtNumber > 99) { setFeedbackError(true); setFeedback('Enter a name, position and shirt number from 1 to 99.'); return; }
      const problem = await addPlayer({ name: name.trim(), position: position.trim(), number: shirtNumber });
      setFeedbackError(Boolean(problem));
      setFeedback(problem ?? (demoMode ? 'Demo player added to the club roster on this device.' : 'Player registered with the server.'));
      if (!problem) { setName(''); setPosition(''); setNumber(''); }
      return;
    }
    if (!player.trim() || !reason.trim() || (action !== 'release' && !destination.trim())) { setFeedbackError(true); setFeedback('Enter the player, destination and reason.'); return; }
    await queueAction({ type: 'roster_transfer', base_version: 0, label: `${action} · ${player}`, payload: { request_id: `req-${Date.now()}`, league_id: 'league-alpha-1', player_id: player.trim(), type: action, from_squad_id: 'squad-alpha-1', to_squad_id: action === 'release' ? null : destination.trim(), effective_date: new Date().toISOString().slice(0, 10), loan_end_date: action === 'loan' ? '2026-11-01' : null, reason: reason.trim(), requested_by: account?.email } });
    setFeedbackError(false); setFeedback(online ? 'Action saved. Open the sync queue to review its result.' : 'Saved offline. It will sync after reconnection.');
  }
  return <Page eyebrow="Club manager tools" title="Manage roster" subtitle="Changes are recorded in the offline action queue until confirmed by the server.">
    <Card accent><Pill text={online ? 'CONNECTED' : 'OFFLINE · QUEUE ACTIVE'} tone={online ? 'mint' : 'gold'} /><Text style={{ color: C.text, fontWeight: '800', fontSize: 17, marginTop: 12 }}>{club.name}</Text><Muted>Squad changes keep a dated audit trail.</Muted></Card>
    <Text style={{ color: C.text, fontSize: 18, fontWeight: '800', marginBottom: 10 }}>Choose action</Text>
    <View style={{ flexDirection: 'row', flexWrap: 'wrap', justifyContent: 'space-between', marginBottom: 14 }}>
      {actions.map(item => <Pressable key={item.id} onPress={() => { setAction(item.id); setFeedback(''); setFeedbackError(false); }} accessibilityRole="button" accessibilityState={{ selected: action === item.id }} style={{ width: '48%', minHeight: 82, backgroundColor: action === item.id ? C.surface2 : C.surface, borderColor: action === item.id ? C.accent : C.line, borderWidth: 1, borderRadius: 13, padding: 12, marginBottom: 9, justifyContent: 'center' }}>
        <Text style={{ color: action === item.id ? C.accent : C.text, fontSize: 15, fontWeight: '800' }}>{item.title}</Text>
        <Text style={{ color: C.muted, fontSize: 12, marginTop: 4 }}>{item.detail}</Text>
      </Pressable>)}
    </View>
    {action === 'add' ? <><Field label="Player name" value={name} onChangeText={setName} /><Field label="Position" value={position} onChangeText={setPosition} placeholder="e.g. Defender" /><Field label="Shirt number" value={number} onChangeText={setNumber} keyboardType="numeric" /></> : <><Field label="Player ID" value={player} onChangeText={setPlayer} />{action !== 'release' ? <Field label="Destination squad ID" value={destination} onChangeText={setDestination} /> : null}<Field label="Reason" value={reason} onChangeText={setReason} multiline /></>}
    {feedback ? <Text accessibilityRole="alert" style={{ color: feedbackError ? C.danger : C.accent, marginBottom: 8 }}>{feedback}</Text> : null}
    <Button title={`Confirm ${action}`} danger={action === 'release'} onPress={() => Alert.alert(`Confirm ${action}`, action === 'add' ? `Register ${name || 'this player'}?` : `Queue this ${action} action for ${player}?`, [{ text: 'Cancel', style: 'cancel' }, { text: 'Confirm', onPress: () => void submit() }])} />
    <Button title="View pending actions" secondary onPress={() => router.push('/queue')} />
    <Muted>New player registration requires a connection in live mode. Transfer, loan and release use the persistent offline queue.</Muted>
  </Page>;
}
