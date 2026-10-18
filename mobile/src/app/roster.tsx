import { router } from 'expo-router';
import React, { useEffect, useState } from 'react';
import { Alert, Pressable, Text, View } from 'react-native';
import { Button, Card, Field, Muted, Page, Pill } from '../components/UI';
import { canManageRoster, useApp } from '../state/AppContext';
import { C } from '../theme';

export default function Roster() {
  const { account, club, queueAction, addPlayer, online, demoMode, rosterHistory, rosterDestinations } = useApp();
  const [action, setAction] = useState<'add' | 'transfer' | 'loan' | 'release'>('transfer');
  const [name, setName] = useState('');
  const [position, setPosition] = useState('');
  const [number, setNumber] = useState('');
  const [player, setPlayer] = useState('');
  const [destination, setDestination] = useState('');
  const [destinations, setDestinations] = useState<{ id: string; clubName: string; leagueId: string }[]>([]);
  const [reason, setReason] = useState('Squad rotation');
  const [feedback, setFeedback] = useState('');
  const [feedbackError, setFeedbackError] = useState(false);
  const actions = [
    { id: 'add', title: 'Add player', detail: 'Register a new squad member' },
    { id: 'transfer', title: 'Transfer', detail: 'Move to another squad' },
    { id: 'loan', title: 'Loan', detail: 'Temporary move' },
    { id: 'release', title: 'Release', detail: 'Remove from squad' },
  ] as const;
  useEffect(() => {
    if (demoMode) { setPlayer(current => club.roster.some(p => (p.id ?? p.name) === current) ? current : (club.roster[0]?.id ?? club.roster[0]?.name ?? '')); setDestination('squad-alpha-2'); setDestinations([{ id: 'squad-alpha-2', clubName: 'North Stars', leagueId: 'league-alpha-1' }]); return; }
    if (club.roster[0]?.id) setPlayer(current => club.roster.some(p => p.id === current) ? current : club.roster[0].id ?? '');
    void rosterDestinations().then(result => { setDestinations(result); setDestination(current => result.some(d => d.id === current) ? current : result[0]?.id ?? ''); }).catch(error => { setFeedbackError(true); setFeedback(error instanceof Error ? error.message : 'Destinations could not be loaded.'); });
  }, [club.roster, demoMode, rosterDestinations]);
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
    if (!player || !reason.trim() || (action !== 'release' && !destination)) { setFeedbackError(true); setFeedback('Choose a player and destination, then enter a reason.'); return; }
    try {
      const history = demoMode ? { league_id: 'league-alpha-1', current_squad_id: 'squad-alpha-1', history: [] } : await rosterHistory(player);
      if (!history.current_squad_id) throw new Error('This player is not in a squad. Refresh the roster and try again.');
      if (!demoMode && action !== 'release' && !destinations.some(d => d.id === destination && d.leagueId === history.league_id)) throw new Error('Choose a destination squad in this league.');
      const loanEnd = new Date(Date.now() + 30 * 86400000).toISOString().slice(0, 10);
      const result = await queueAction({ type: 'roster_transfer', base_version: history.history.length, label: `${action} · ${club.roster.find(p => p.id === player)?.name ?? player}`, payload: { request_id: `req-${Date.now()}`, league_id: history.league_id, player_id: player, type: action, from_squad_id: history.current_squad_id, to_squad_id: action === 'release' ? null : destination, effective_date: new Date().toISOString().slice(0, 10), loan_end_date: action === 'loan' ? loanEnd : null, reason: reason.trim(), requested_by: account?.user_id ?? account?.email } });
      setFeedbackError(result.status === 'rejected'); setFeedback(result.resolution ?? 'Awaiting server confirmation.');
    } catch (error) { setFeedbackError(true); setFeedback(error instanceof Error ? error.message : 'Could not save this roster action.'); }
  }
  return <Page eyebrow="Club manager tools" title="Manage roster" subtitle="Changes are recorded in the offline action queue until confirmed by the server.">
    <Card accent><Pill text={online ? 'CONNECTED' : 'OFFLINE · QUEUE ACTIVE'} tone={online ? 'mint' : 'gold'} /><Text style={{ color: C.text, fontWeight: '800', fontSize: 17, marginTop: 12 }}>{club.name}</Text><Muted>Squad changes keep a dated audit trail.</Muted></Card>
    <Text style={{ color: C.text, fontSize: 18, fontWeight: '800', marginBottom: 10 }}>Choose action</Text>
    <View style={{ flexDirection: 'row', flexWrap: 'wrap', justifyContent: 'space-between', marginBottom: 14 }}>
      {actions.map(item => <Pressable key={item.id} onPress={() => { setAction(item.id); setFeedback(''); setFeedbackError(false); }} accessibilityRole="button" accessibilityState={{ selected: action === item.id }} style={({ pressed }) => ({ width: '48%', minHeight: 82, backgroundColor: action === item.id ? C.accentDark : C.surface2, borderRadius: 18, padding: 13, marginBottom: 9, justifyContent: 'center', opacity: pressed ? .8 : 1 })}>
        <Text style={{ color: action === item.id ? C.accent : C.text, fontSize: 15, fontWeight: '800' }}>{item.title}</Text>
        <Text style={{ color: C.muted, fontSize: 12, marginTop: 4 }}>{item.detail}</Text>
      </Pressable>)}
    </View>
    {action === 'add' ? <><Field label="Player name" value={name} onChangeText={setName} /><Field label="Position" value={position} onChangeText={setPosition} placeholder="e.g. Defender" /><Field label="Shirt number" value={number} onChangeText={setNumber} keyboardType="numeric" /></> : <>
      <Text style={{ color: C.text, fontWeight: '800', marginBottom: 8 }}>Player</Text>
      {club.roster.filter(p => demoMode || Boolean(p.id)).map(p => <Card key={p.id ?? p.name} accent={player === (p.id ?? p.name)} onPress={() => setPlayer(p.id ?? p.name)}><Text style={{ color: C.text, fontWeight: '700' }}>{p.name}{player === (p.id ?? p.name) ? '  ✓' : ''}</Text></Card>)}
      {!club.roster.some(p => p.id) && demoMode ? <Field label="Demo player ID" value={player} onChangeText={setPlayer} /> : null}
      {!club.roster.length && !demoMode ? <Muted>No players were returned for this club.</Muted> : null}
      {action !== 'release' ? <><Text style={{ color: C.text, fontWeight: '800', marginVertical: 8 }}>Destination club</Text>{destinations.map(d => <Card key={d.id} accent={destination === d.id} onPress={() => setDestination(d.id)}><Text style={{ color: C.text, fontWeight: '700' }}>{d.clubName}{destination === d.id ? '  ✓' : ''}</Text></Card>)}{!destinations.length ? <Muted>No destination squads were returned. Connect and refresh the roster.</Muted> : null}</> : null}
      <Field label="Reason" value={reason} onChangeText={setReason} multiline /></>}
    {feedback ? <Text accessibilityRole="alert" style={{ color: feedbackError ? C.danger : C.accent, marginBottom: 8 }}>{feedback}</Text> : null}
    <Button title={`Confirm ${action}`} danger={action === 'release'} onPress={() => Alert.alert(`Confirm ${action}`, action === 'add' ? `Register ${name || 'this player'}?` : `Queue this ${action} action for ${player}?`, [{ text: 'Cancel', style: 'cancel' }, { text: 'Confirm', onPress: () => void submit() }])} />
    <Button title="View pending actions" secondary onPress={() => router.push('/queue')} />
    <Muted>New player registration requires a connection in live mode. Transfer, loan and release use the persistent offline queue.</Muted>
  </Page>;
}
