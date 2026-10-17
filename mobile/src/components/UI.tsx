import React, { useState } from 'react';
import { ActivityIndicator, Image, Platform, Pressable, ScrollView, StyleSheet, Text, TextInput, View } from 'react-native';
import { C, DISPLAY_FONT, TENANT } from '../theme';
import { useApp } from '../state/AppContext';

export function BrandMark() {
  const { tenant } = useApp();
  const name = tenant?.branding.display_name ?? tenant?.name ?? TENANT.name;
  return <View accessibilityLabel={`${name} logo`} style={{ width: 54, height: 54, borderRadius: 12, backgroundColor: tenant?.branding.primary_color ?? C.accent, alignItems: 'center', justifyContent: 'center', marginBottom: 14 }}>{tenant?.branding.logo_url ? <Image source={{ uri: tenant.branding.logo_url }} style={{ width: 48, height: 48 }} resizeMode="contain" /> : <Text style={{ color: tenant ? '#FFFFFF' : C.bg, fontSize: 29, fontWeight: '900' }}>{name[0]}</Text>}</View>;
}

export function AppMark({ size = 64 }: { size?: number }) {
  return <Image source={require('../../assets/leagueops-icon.png')} accessibilityLabel="LeagueOps mark" style={{ width: size, height: size, borderRadius: Math.round(size * .22), marginBottom: 14 }} />;
}

export function Page({ children, title, eyebrow, subtitle }: { children: React.ReactNode; title: string; eyebrow?: string; subtitle?: string }) {
  const { tenant, loading, dataError, account, refreshCache } = useApp();
  const tenantName = tenant?.branding.display_name ?? tenant?.name ?? TENANT.name;
  return <ScrollView contentContainerStyle={styles.page} keyboardShouldPersistTaps="handled">
    {eyebrow ? <View style={styles.pageTop}><Text style={styles.eyebrow}>{eyebrow.toUpperCase()}</Text><View style={styles.tenantBadge} accessibilityLabel={`${tenantName} tenant`}><Text style={[styles.tenantInitial, tenant?.branding.primary_color ? { backgroundColor: tenant.branding.primary_color, color: '#FFFFFF' } : {}]}>{tenantName[0]}</Text><Text numberOfLines={1} style={styles.tenantName}>{tenantName.toUpperCase()}</Text></View></View> : null}
    <Text style={styles.title}>{title}</Text>
    {subtitle ? <Text style={styles.subtitle}>{subtitle}</Text> : null}
    {loading ? <ActivityIndicator color={C.accent} accessibilityLabel="Refreshing server data" style={{ marginBottom: 12 }} /> : null}
    {dataError && account ? <View style={{ marginBottom: 14 }}><Text accessibilityRole="alert" style={{ color: C.danger }}>{dataError}</Text><Button title="Retry connection" secondary loading={loading} onPress={() => void refreshCache()} /></View> : null}
    {children}
  </ScrollView>;
}
export function Card({ children, onPress, accent }: { children: React.ReactNode; onPress?: () => void; accent?: boolean }) {
  const inside = <View style={[styles.card, accent && styles.accentCard]}>{children}</View>;
  return onPress ? <Pressable onPress={onPress} accessibilityRole="button" style={({ pressed }) => ({ opacity: pressed ? .78 : 1 })}>{inside}</Pressable> : inside;
}
export function Button({ title, onPress, secondary, disabled, danger, loading }: { title: string; onPress: () => void; secondary?: boolean; disabled?: boolean; danger?: boolean; loading?: boolean }) {
  const [hovered, setHovered] = useState(false);
  return <Pressable onPress={onPress} onHoverIn={() => setHovered(true)} onHoverOut={() => setHovered(false)} disabled={disabled || loading} style={({ pressed }) => [styles.button, secondary && styles.secondaryButton, danger && styles.dangerButton, disabled && { opacity: .45 }, hovered && Platform.OS === 'web' && !disabled && { opacity: .9, transform: [{ scale: 1.01 }] }, pressed && !disabled && { opacity: .8, transform: [{ scale: .985 }] }]} accessibilityRole="button" accessibilityLabel={title}>
    {loading ? <ActivityIndicator color={secondary ? C.text : C.bg} style={{ marginRight: 8 }} /> : null}
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
  page: { flexGrow: 1, backgroundColor: C.bg, paddingHorizontal: 20, paddingTop: 25, paddingBottom: 110 },
  pageTop: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10, gap: 8 },
  eyebrow: { color: C.accent, letterSpacing: 1.5, fontWeight: '800', fontSize: 11, flexShrink: 1 },
  tenantBadge: { flexDirection: 'row', alignItems: 'center', gap: 5, maxWidth: '48%', flexShrink: 1 },
  tenantInitial: { color: C.bg, backgroundColor: C.accent, width: 19, height: 19, borderRadius: 5, textAlign: 'center', textAlignVertical: 'center', fontWeight: '900', fontSize: 12 },
  tenantName: { color: C.muted, fontSize: 10, fontWeight: '800', letterSpacing: .6, flexShrink: 1 },
  title: { color: C.text, fontSize: 36, fontWeight: '900', fontFamily: DISPLAY_FONT, letterSpacing: -.7, marginBottom: 6, textTransform: 'uppercase' },
  subtitle: { color: C.muted, fontSize: 15, lineHeight: 22, marginBottom: 24 },
  card: { backgroundColor: C.surface, borderRadius: 18, padding: 17, marginBottom: 11 },
  accentCard: { backgroundColor: C.surface2 },
  button: { backgroundColor: C.accent, minHeight: 52, paddingHorizontal: 20, borderRadius: 28, alignItems: 'center', justifyContent: 'center', flexDirection: 'row', marginVertical: 7, elevation: 2, shadowColor: '#000000', shadowOpacity: .18, shadowRadius: 7, shadowOffset: { width: 0, height: 3 } },
  secondaryButton: { backgroundColor: C.surface2 },
  dangerButton: { backgroundColor: C.danger },
  buttonText: { color: C.bg, fontSize: 15, fontWeight: '800' },
  label: { color: C.muted, fontSize: 12, fontWeight: '700', marginBottom: 7, textTransform: 'uppercase', letterSpacing: .8 },
  input: { backgroundColor: C.surface2, borderRadius: 16, color: C.text, minHeight: 50, paddingHorizontal: 16, fontSize: 16 },
  pill: { alignSelf: 'flex-start', paddingHorizontal: 10, paddingVertical: 6, borderRadius: 50 },
  sectionRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginTop: 19, marginBottom: 12 },
  sectionTitle: { color: C.text, fontSize: 21, fontWeight: '900', fontFamily: DISPLAY_FONT, textTransform: 'uppercase' }, sectionAction: { color: C.accent, fontSize: 12, fontWeight: '700' },
  muted: { color: C.muted, fontSize: 14, lineHeight: 21 },
});
