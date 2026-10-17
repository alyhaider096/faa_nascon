import React from 'react';
import { Pressable, ScrollView, StyleSheet, Text, TextInput, View } from 'react-native';
import { C, TENANT } from '../theme';

export function BrandMark() {
  return <View accessibilityLabel={`${TENANT.name} logo`} style={{ width: 54, height: 54, borderRadius: 16, backgroundColor: C.accent, alignItems: 'center', justifyContent: 'center', marginBottom: 14 }}><Text style={{ color: C.bg, fontSize: 29, fontWeight: '900' }}>{TENANT.logoText}</Text></View>;
}

export function Page({ children, title, eyebrow, subtitle }: { children: React.ReactNode; title: string; eyebrow?: string; subtitle?: string }) {
  return <ScrollView contentContainerStyle={styles.page} keyboardShouldPersistTaps="handled">
    {eyebrow ? <Text style={styles.eyebrow}>{eyebrow.toUpperCase()}</Text> : null}
    <Text style={styles.title}>{title}</Text>
    {subtitle ? <Text style={styles.subtitle}>{subtitle}</Text> : null}
    {children}
  </ScrollView>;
}
export function Card({ children, onPress, accent }: { children: React.ReactNode; onPress?: () => void; accent?: boolean }) {
  const inside = <View style={[styles.card, accent && styles.accentCard]}>{children}</View>;
  return onPress ? <Pressable onPress={onPress} accessibilityRole="button">{inside}</Pressable> : inside;
}
export function Button({ title, onPress, secondary, disabled, danger }: { title: string; onPress: () => void; secondary?: boolean; disabled?: boolean; danger?: boolean }) {
  return <Pressable onPress={onPress} disabled={disabled} style={[styles.button, secondary && styles.secondaryButton, danger && styles.dangerButton, disabled && { opacity: .45 }]} accessibilityRole="button" accessibilityLabel={title}>
    <Text style={[styles.buttonText, secondary && { color: C.text }]}>{title}</Text>
  </Pressable>;
}
export function Field({ label, value, onChangeText, placeholder, secureTextEntry, keyboardType, multiline }: { label: string; value: string; onChangeText: (value: string) => void; placeholder?: string; secureTextEntry?: boolean; keyboardType?: 'default' | 'email-address' | 'numeric' | 'url'; multiline?: boolean }) {
  return <View style={{ marginBottom: 14 }}><Text style={styles.label}>{label}</Text><TextInput style={[styles.input, multiline && { minHeight: 90, textAlignVertical: 'top' }]} value={value} onChangeText={onChangeText} placeholder={placeholder} placeholderTextColor="#71879C" secureTextEntry={secureTextEntry} keyboardType={keyboardType} multiline={multiline} autoCapitalize="none" accessibilityLabel={label} /></View>;
}
export function Pill({ text, tone = 'mint' }: { text: string; tone?: 'mint' | 'gold' | 'red' | 'blue' }) {
  const bg = tone === 'gold' ? '#58442A' : tone === 'red' ? '#582E38' : tone === 'blue' ? '#254961' : '#184A43';
  const fg = tone === 'gold' ? C.gold : tone === 'red' ? C.danger : tone === 'blue' ? C.blue : C.accent;
  return <View style={[styles.pill, { backgroundColor: bg }]}><Text style={{ color: fg, fontWeight: '700', fontSize: 11 }}>{text}</Text></View>;
}
export function SectionTitle({ title, action }: { title: string; action?: string }) { return <View style={styles.sectionRow}><Text style={styles.sectionTitle}>{title}</Text>{action ? <Text style={styles.sectionAction}>{action}</Text> : null}</View>; }
export function Muted({ children }: { children: React.ReactNode }) { return <Text style={styles.muted}>{children}</Text>; }

const styles = StyleSheet.create({
  page: { flexGrow: 1, backgroundColor: C.bg, paddingHorizontal: 20, paddingTop: 24, paddingBottom: 40 },
  eyebrow: { color: C.accent, letterSpacing: 2, fontWeight: '800', fontSize: 11, marginBottom: 8 },
  title: { color: C.text, fontSize: 29, fontWeight: '800', letterSpacing: -.5, marginBottom: 8 },
  subtitle: { color: C.muted, fontSize: 15, lineHeight: 22, marginBottom: 24 },
  card: { backgroundColor: C.surface, borderColor: C.line, borderWidth: 1, borderRadius: 13, padding: 16, marginBottom: 10 },
  accentCard: { backgroundColor: C.surface2, borderColor: C.accentDark },
  button: { backgroundColor: C.accent, minHeight: 50, paddingHorizontal: 18, borderRadius: 11, alignItems: 'center', justifyContent: 'center', marginVertical: 6 },
  secondaryButton: { backgroundColor: C.surface2, borderWidth: 1, borderColor: C.line },
  dangerButton: { backgroundColor: C.danger },
  buttonText: { color: C.bg, fontSize: 15, fontWeight: '800' },
  label: { color: C.muted, fontSize: 12, fontWeight: '700', marginBottom: 7, textTransform: 'uppercase', letterSpacing: .8 },
  input: { backgroundColor: C.surface, borderColor: C.line, borderWidth: 1, borderRadius: 11, color: C.text, minHeight: 50, paddingHorizontal: 14, fontSize: 16 },
  pill: { alignSelf: 'flex-start', paddingHorizontal: 10, paddingVertical: 6, borderRadius: 50 },
  sectionRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginTop: 19, marginBottom: 12 },
  sectionTitle: { color: C.text, fontSize: 19, fontWeight: '800' }, sectionAction: { color: C.accent, fontSize: 12, fontWeight: '700' },
  muted: { color: C.muted, fontSize: 14, lineHeight: 21 },
});
