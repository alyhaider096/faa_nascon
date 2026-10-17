import { router } from 'expo-router';
import React, { useState } from 'react';
import { Pressable, Text, View } from 'react-native';
import { AppMark, Button, Card, Field, Muted, Page, Pill } from '../components/UI';
import { ACCOUNTS, DEMO_PASSWORD } from '../data/mock';
import { useApp } from '../state/AppContext';
import { C } from '../theme';

export default function Login() {
  const { login, demoMode } = useApp();
  const [email, setEmail] = useState('organizer@nascon.test');
  const [password, setPassword] = useState(DEMO_PASSWORD);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  async function submit() { if (busy) return; setBusy(true); setError(''); try { const problem = await login(email, password); if (problem) setError(problem); else router.replace('/(tabs)/fixtures'); } finally { setBusy(false); } }
  return <Page eyebrow="LeagueOps" title="Sign in" subtitle="Fixtures, standings, club roster, and merchandise.">
    <Card accent><AppMark /><Pill text={demoMode ? 'DEMO MODE' : 'LIVE DATA MODE'} /><Text style={{ color: C.text, fontWeight: '800', fontSize: 18, marginTop: 15 }}>Every league. One match centre.</Text><Muted>Sign in to manage fixtures, squads and matchday commerce.</Muted></Card>
    <Field label="Email" value={email} onChangeText={setEmail} keyboardType="email-address" />
    <Field label="Password" value={password} onChangeText={setPassword} secureTextEntry />
    {error ? <Text style={{ color: C.danger, marginBottom: 8 }}>{error}</Text> : null}
    <Button title={busy ? 'Signing in…' : 'Sign in'} loading={busy} onPress={() => void submit()} />
    <Button title="Server settings" secondary onPress={() => router.push('/settings')} />
    <View style={{ marginTop: 22 }}><Text style={{ color: C.text, fontSize: 17, fontWeight: '800', marginBottom: 5 }}>Test accounts</Text><Muted>Tap a role to fill its sign-in details. All five roles use the same test password.</Muted>
      {ACCOUNTS.map(a => <Pressable key={a.email} onPress={() => { setEmail(a.email); setPassword(DEMO_PASSWORD); setError(''); }} style={({ pressed }) => ({ minHeight: 58, padding: 14, marginBottom: 8, borderRadius: 15, backgroundColor: C.surface2, opacity: pressed ? .8 : 1 })}><Text style={{ color: C.accent, fontWeight: '700' }}>{a.label}</Text><Text style={{ color: C.muted, fontSize: 12 }}>{a.email}</Text></Pressable>)}
    </View>
  </Page>;
}
