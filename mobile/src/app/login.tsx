import { Ionicons } from '@expo/vector-icons';
import { router } from 'expo-router';
import React, { useState } from 'react';
import { ImageBackground, KeyboardAvoidingView, Platform, Pressable, ScrollView, StyleSheet, Text, TextInput, View, useWindowDimensions } from 'react-native';
import { AppMark, Button, Pill } from '../components/UI';
import { ACCOUNTS, DEMO_PASSWORD } from '../data/mock';
import { useApp } from '../state/AppContext';
import { C } from '../theme';

export default function Login() {
  const { login, demoMode } = useApp();
  const wide = useWindowDimensions().width >= 900;
  const [email, setEmail] = useState(demoMode ? 'organizer@nascon.test' : '');
  const [password, setPassword] = useState(demoMode ? DEMO_PASSWORD : '');
  const [visible, setVisible] = useState(false);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  async function submit() {
    if (busy) return;
    if (!email.trim() || !password) { setError('Enter your email and password to continue.'); return; }
    setBusy(true); setError('');
    try { const problem = await login(email.trim(), password); if (problem) setError(problem); else router.replace('/(tabs)/fixtures'); }
    catch { setError('We could not sign you in. Check your connection and try again.'); }
    finally { setBusy(false); }
  }
  return <KeyboardAvoidingView style={s.screen} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
    <ScrollView keyboardShouldPersistTaps="handled" contentContainerStyle={s.scroll}>
      <View style={[s.shell, wide && s.shellWide]}>
        <ImageBackground source={require('../../assets/football-matchday.png')} style={[s.hero, wide && s.heroWide]} imageStyle={{ borderRadius: 24 }}>
          <View style={[s.heroShade, wide && { minHeight: 590 }]}>
            <View style={s.brand}><AppMark size={42} /><Text style={s.wordmark}>LEAGUEOPS</Text></View>
            <View style={s.heroCopy}><Text style={s.eyebrow}>YOUR MATCHDAY WORKSPACE</Text><Text style={[s.heroTitle, wide && { fontSize: 48, lineHeight: 53 }]}>Every league.{'\n'}Every moment.</Text><Text style={s.heroBody}>Follow the action. Manage your team. Be part of the game.</Text></View>
            <View style={s.heroFooter}><Ionicons name="football-outline" size={17} color="#FFFFFF" /><Text style={s.heroFooterText}>Fixtures  /  Teams  /  Live matchday</Text></View>
          </View>
        </ImageBackground>
        <View style={[s.form, wide && s.formWide]}>
          <View style={s.formTop}><Text style={s.eyebrow}>WELCOME BACK</Text><Pill tone={demoMode ? 'gold' : 'mint'} text={demoMode ? 'Demo preview' : 'Server mode'} /></View>
          <Text accessibilityRole="header" style={s.title}>Sign in to your{wide ? '\n' : ' '}workspace</Text>
          <Text style={s.description}>{demoMode ? 'Choose a role below or use a demo account to explore.' : 'Use your team account to access your matchday tools.'}</Text>
          <Text style={s.label}>EMAIL ADDRESS</Text>
          <View style={s.inputRow}><Ionicons name="mail-outline" size={20} color={C.muted} /><TextInput accessibilityLabel="Email" autoComplete="email" textContentType="emailAddress" autoCapitalize="none" autoCorrect={false} keyboardType="email-address" placeholder="you@yourteam.com" placeholderTextColor="#A6B6CA" value={email} onChangeText={setEmail} style={s.input} returnKeyType="next" /></View>
          <Text style={s.label}>PASSWORD</Text>
          <View style={s.inputRow}><Ionicons name="lock-closed-outline" size={20} color={C.muted} /><TextInput accessibilityLabel="Password" autoComplete="current-password" textContentType="password" autoCapitalize="none" secureTextEntry={!visible} placeholder="Enter your password" placeholderTextColor="#A6B6CA" value={password} onChangeText={setPassword} style={s.input} onSubmitEditing={() => void submit()} returnKeyType="go" /><Pressable accessibilityRole="button" accessibilityLabel={visible ? 'Hide password' : 'Show password'} onPress={() => setVisible(!visible)} style={s.eye}><Ionicons name={visible ? 'eye-off-outline' : 'eye-outline'} size={21} color={C.muted} /></Pressable></View>
          {error ? <View style={s.error}><Ionicons name="alert-circle-outline" size={18} color={C.danger} /><Text accessibilityRole="alert" style={s.errorText}>{error}</Text></View> : null}
          <View style={{ marginTop: 16 }}><Button title={busy ? 'Signing in…' : 'Sign in'} loading={busy} onPress={() => void submit()} /></View>
          <Pressable accessibilityRole="button" onPress={() => router.push('/settings')} style={s.settings}><Ionicons name="settings-outline" size={17} color={C.muted} /><Text style={s.settingsText}>Connection settings</Text><Ionicons name="arrow-forward" size={16} color={C.accent} /></Pressable>
          {demoMode ? <View style={s.roles}><Text style={s.roleHeading}>EXPLORE A ROLE</Text><View style={s.roleGrid}>{ACCOUNTS.map(a => <Pressable accessibilityRole="button" accessibilityLabel={`Use ${a.label} demo account`} accessibilityState={{ selected: email === a.email }} key={a.email} onPress={() => { setEmail(a.email); setPassword(DEMO_PASSWORD); setError(''); }} style={[s.role, email === a.email && s.roleSelected]}><Text style={[s.roleText, email === a.email && { color: C.accent }]}>{a.label}</Text></Pressable>)}</View><Text style={s.note}>Sample data only. Demo changes stay on this device.</Text></View> : <View style={s.secureNote}><Ionicons name="shield-checkmark-outline" size={16} color={C.muted} /><Text style={s.note}>Your role determines the tools you can access.</Text></View>}
        </View>
      </View>
    </ScrollView>
  </KeyboardAvoidingView>;
}
const s = StyleSheet.create({
  screen: { flex: 1, backgroundColor: C.bg }, scroll: { flexGrow: 1, justifyContent: 'center', padding: 16, paddingBottom: 32 },
  shell: { width: '100%', maxWidth: 1120, alignSelf: 'center', gap: 24 }, shellWide: { flexDirection: 'row', gap: 0, borderWidth: 1, borderColor: C.line, borderRadius: 26, overflow: 'hidden', backgroundColor: C.surface },
  hero: { borderRadius: 24, overflow: 'hidden' }, heroWide: { flex: 1 }, heroShade: { padding: 24, minHeight: 235, justifyContent: 'space-between', backgroundColor: 'rgba(5,15,28,.72)' },
  brand: { flexDirection: 'row', alignItems: 'center', gap: 12 }, wordmark: { color: '#FFFFFF', fontWeight: '900', fontSize: 16, letterSpacing: 2, marginBottom: 14 },
  heroCopy: { marginVertical: 16 }, eyebrow: { color: C.accent, fontWeight: '800', fontSize: 10, letterSpacing: 1.6 }, heroTitle: { color: '#FFFFFF', fontWeight: '900', fontSize: 33, lineHeight: 37, letterSpacing: -.8, marginTop: 10 }, heroBody: { color: '#E0E9F5', fontSize: 14, lineHeight: 22, maxWidth: 300, marginTop: 12 }, heroFooter: { flexDirection: 'row', alignItems: 'center', gap: 8 }, heroFooterText: { color: '#E0E9F5', fontSize: 11, fontWeight: '700' },
  form: { paddingHorizontal: 4 }, formWide: { flex: 1, padding: 36 }, formTop: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', gap: 8 },
  title: { color: C.text, fontSize: 29, lineHeight: 35, fontWeight: '900', letterSpacing: -.7, marginTop: 16 }, description: { color: C.muted, fontSize: 14, lineHeight: 22, marginTop: 9, marginBottom: 20 }, label: { color: C.muted, fontSize: 10, letterSpacing: 1.1, fontWeight: '800', marginTop: 14, marginBottom: 9 },
  inputRow: { flexDirection: 'row', alignItems: 'center', gap: 12, paddingLeft: 15, backgroundColor: C.surface2, borderWidth: 1, borderColor: C.line, borderRadius: 14, minHeight: 54 }, input: { flex: 1, minWidth: 0, color: C.text, fontSize: 16, minHeight: 52, paddingVertical: 12, paddingRight: 12 }, eye: { width: 48, minHeight: 52, alignItems: 'center', justifyContent: 'center' },
  error: { flexDirection: 'row', gap: 8, padding: 12, borderRadius: 12, backgroundColor: '#382332', marginTop: 14 }, errorText: { flex: 1, color: C.danger, lineHeight: 20, fontSize: 13 }, settings: { minHeight: 48, flexDirection: 'row', gap: 9, alignItems: 'center', justifyContent: 'center' }, settingsText: { color: C.muted, fontSize: 13, fontWeight: '600' },
  roles: { borderTopWidth: 1, borderTopColor: C.line, marginTop: 18, paddingTop: 22 }, roleHeading: { color: C.muted, fontSize: 10, letterSpacing: 1.3, fontWeight: '800', marginBottom: 12 }, roleGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 }, role: { minHeight: 44, justifyContent: 'center', borderRadius: 12, borderWidth: 1, borderColor: C.line, backgroundColor: C.surface, paddingHorizontal: 13 }, roleSelected: { borderColor: C.accent, backgroundColor: '#342B2A' }, roleText: { color: C.text, fontSize: 12, fontWeight: '700' }, note: { color: C.muted, fontSize: 11, lineHeight: 17, marginTop: 12 }, secureNote: { flexDirection: 'row', gap: 8, alignItems: 'center', justifyContent: 'center', marginTop: 14 },
});
