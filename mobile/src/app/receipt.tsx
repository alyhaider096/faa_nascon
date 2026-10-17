import { router } from 'expo-router';
import * as FileSystem from 'expo-file-system/legacy';
import * as Sharing from 'expo-sharing';
import React from 'react';
import { Alert, Text } from 'react-native';
import { Button, Card, Muted, Page, Pill } from '../components/UI';
import { formatMoney } from '../data/mock';
import { useApp } from '../state/AppContext';
import { C } from '../theme';

export default function Receipt() {
  const { receipt } = useApp();
  async function sharePdf() {
    if (!receipt?.pdfBase64 || !FileSystem.documentDirectory) return;
    try {
      const path = `${FileSystem.documentDirectory}${receipt.orderId}.pdf`;
      await FileSystem.writeAsStringAsync(path, receipt.pdfBase64, { encoding: FileSystem.EncodingType.Base64 });
      await Sharing.shareAsync(path, { mimeType: 'application/pdf', dialogTitle: 'Save or share receipt' });
    } catch { Alert.alert('Receipt unavailable', 'The PDF could not be opened. Please ask the team to check the server receipt.'); }
  }
  return <Page eyebrow="Payment complete" title="Receipt" subtitle="Your matchday purchase is confirmed.">
    {receipt ? <Card accent><Pill text="PAID" /><Text style={{ color: C.text, fontSize: 22, fontWeight: '800', marginTop: 18 }}>{receipt.orderId}</Text><Muted>{new Date(receipt.paidAt).toLocaleString()}</Muted>{receipt.items.map(item => <Text key={item.variantId} style={{ color: C.text, marginTop: 12 }}>{item.name} · {item.label} × {item.quantity}</Text>)}<Text style={{ color: C.accent, fontSize: 29, fontWeight: '900', marginTop: 24 }}>{formatMoney(receipt.totalMinor)}</Text><Muted>Discount: {formatMoney(receipt.discountMinor)}</Muted></Card> : <Muted>No receipt yet. Complete a purchase in the store.</Muted>}
    {receipt?.signature ? <Muted>Signed server receipt: {receipt.signature.slice(0, 16)}…</Muted> : <Muted>Demo receipt only. Live checkout supplies the signed PDF receipt.</Muted>}
    {receipt?.pdfBase64 ? <Button title="Open or save PDF receipt" secondary onPress={() => void sharePdf()} /> : null}
    <Button title="Return to store" onPress={() => router.replace('/(tabs)/store')} />
  </Page>;
}
