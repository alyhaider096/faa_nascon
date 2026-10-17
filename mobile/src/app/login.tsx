import { router } from 'expo-router';
import React, { useState } from 'react';
import { Pressable, Text, View } from 'react-native';
import { BrandMark, Button, Card, Field, Muted, Page, Pill } from '../components/UI';
import { ACCOUNTS, DEMO_PASSWORD } from '../data/mock';
import { useApp } from '../state/AppContext';
import { C } from '../theme';

export default function Login() {
  const { login, demoMode } = useApp();
  const [email, setEmail] = useState('organizer@nascon.test');
  const [password, setPassword] = useState(DEMO_PASSWORD);
  const [error, setError] = useState('');
  async function submit() { const problem = await login(email, password); if (problem) setError(problem); else router.replace('/(tabs)/fixtures'); }
  return <Page eyebrow="LeagueOps" title="Sign in" subtitle="Fixtures, standings, club roster, and merchandise.">
    <Card accent><BrandMark /><Pill text={demoMode ? 'DEMO MODE' : 'LIVE DATA MODE'} /><Text style={{ color: C.text, fontWeight: '800', fontSize: 18, marginTop: 15 }}>Multi-sport league operations</Text><Muted>Choose a demo role below. The backend remains responsible for authorizing live changes.</Muted></Card>
    <Field label="Email" value={email} onChangeText={setEmail} keyboardType="email-address" />
    <Field label="Password" value={password} onChangeText={setPassword} secureTextEntry />
    {error ? <Text style={{ color: C.danger, marginBottom: 8 }}>{error}</Text> : null}
    <Button title="Sign in" onPress={() => void submit()} />
    <Button title="Server settings" secondary onPress={() => router.push('/settings')} />
    <View style={{ marginTop: 22 }}><Text style={{ color: C.text, fontSize: 17, fontWeight: '800', marginBottom: 12 }}>Demo accounts</Text>
      {ACCOUNTS.map(a => <Pressable key={a.email} onPress={() => { setEmail(a.email); setPassword(DEMO_PASSWORD); setError(''); }} style={{ paddingVertical: 10, borderBottomWidth: 1, borderColor: C.line }}><Text style={{ color: C.accent, fontWeight: '700' }}>{a.label}</Text><Text style={{ color: C.muted, fontSize: 12 }}>{a.email}</Text></Pressable>)}
    </View>
  </Page>;
}
