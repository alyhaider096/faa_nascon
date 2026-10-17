import { router } from 'expo-router';
import React, { useState } from 'react';
import { Switch, Text, View } from 'react-native';
import { Button, Card, Field, Muted, Page, Pill, SectionTitle } from '../components/UI';
import { useApp } from '../state/AppContext';
import { C } from '../theme';

export default function Settings() {
  const { account, demoMode, serverUrl, setServerUrl, setDemoMode, logout, refreshCache } = useApp();
  const [draft, setDraft] = useState(serverUrl);
  const [feedback, setFeedback] = useState('');
  const [feedbackError, setFeedbackError] = useState(false);
  async function save() {
    if (!/^https?:\/\/[^\s/]+:\d{2,5}$/.test(draft.trim())) { setFeedbackError(true); setFeedback('Enter http://<laptop-IP>:8080'); return; }
    await setServerUrl(draft); setFeedbackError(false); setFeedback('Server address saved on this device.');
  }
  return <Page eyebrow="App preferences" title="Settings" subtitle="Connect this phone to the backend laptop over your team hotspot.">
    <SectionTitle title="Server connection" />
    <Field label="Backend address" value={draft} onChangeText={setDraft} keyboardType="url" placeholder="http://192.168.1.10:8080" />
    <Button title="Save server address" onPress={() => void save()} />
    <Muted>Use the backend laptop’s hotspot IP. The API port is 8080.</Muted>
    <SectionTitle title="Data source" />
    <Card><View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' }}><View style={{ flex: 1 }}><Text style={{ color: C.text, fontWeight: '800' }}>Demo data</Text><Muted>Preview screens without the backend</Muted></View><Switch value={demoMode} onValueChange={value => void setDemoMode(value)} trackColor={{ true: C.accentDark }} thumbColor={C.accent} /></View></Card>
    <Button title="Refresh and cache server data" secondary onPress={() => void refreshCache().then(() => { setFeedbackError(false); setFeedback('Refresh finished. See any connection warning above.'); })} />
    {feedback ? <Text accessibilityRole="alert" style={{ color: feedbackError ? C.danger : C.accent, marginTop: 10 }}>{feedback}</Text> : null}
    <SectionTitle title="Account" />
    <Card><Pill text={account?.label ?? 'SIGNED OUT'} /><Text style={{ color: C.text, fontWeight: '800', marginTop: 10 }}>{account?.email ?? 'Sign in to continue'}</Text></Card>
    {account ? <Button title="Log out" secondary onPress={() => void logout().then(() => router.replace('/login'))} /> : <Button title="Back to login" secondary onPress={() => router.replace('/login')} />}
  </Page>;
}
