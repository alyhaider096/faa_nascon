import { router } from 'expo-router';
import * as FileSystem from 'expo-file-system/legacy';
import * as Sharing from 'expo-sharing';
import React, { useState } from 'react';
import { Platform, Text, View } from 'react-native';
import { Button, Card, Muted, Page, Pill } from '../components/UI';
import { formatMoney } from '../data/mock';
import { useApp } from '../state/AppContext';
import { C, DISPLAY_FONT } from '../theme';

export default function Receipt() {
  const { receipt } = useApp();
  const [pdfError, setPdfError] = useState('');
  const [saving, setSaving] = useState(false);
  async function sharePdf() {
    if (!receipt?.pdfBase64 || saving) return;
    setPdfError(''); setSaving(true);
    try {
      const filename = `${receipt.orderId.replace(/[^a-zA-Z0-9_-]/g, '_')}.pdf`;
      if (Platform.OS === 'web') {
        const binary = atob(receipt.pdfBase64);
        if (!binary.startsWith('%PDF-')) throw new Error('Invalid PDF');
        const bytes = Uint8Array.from(binary, character => character.charCodeAt(0));
        const url = URL.createObjectURL(new Blob([bytes], { type: 'application/pdf' }));
        const link = document.createElement('a'); link.href = url; link.download = filename;
        document.body.appendChild(link); link.click(); link.remove();
        setTimeout(() => URL.revokeObjectURL(url), 60000);
        return;
      }
      if (!FileSystem.documentDirectory || !(await Sharing.isAvailableAsync())) throw new Error('Sharing unavailable');
      const path = `${FileSystem.documentDirectory}${filename}`;
      await FileSystem.writeAsStringAsync(path, receipt.pdfBase64, { encoding: FileSystem.EncodingType.Base64 });
      await Sharing.shareAsync(path, { mimeType: 'application/pdf', dialogTitle: 'Save or share receipt' });
    } catch { setPdfError('The PDF could not be saved. Your order is unchanged. Please retry or contact the team with your order number.'); }
    finally { setSaving(false); }
  }
  return <Page eyebrow="Payment complete" title="Receipt" subtitle="Your matchday purchase is confirmed.">
    {receipt ? <Card accent><Pill text="PAID" /><Text style={{ color: C.text, fontSize: 19, fontWeight: '800', marginTop: 18 }}>{receipt.orderId}</Text><Muted>{new Date(receipt.paidAt).toLocaleString()}</Muted>{receipt.items.map(item => <Text key={item.variantId} style={{ color: C.text, marginTop: 12 }}>{item.name} · {item.label} × {item.quantity}</Text>)}<Text style={{ color: C.muted, fontSize: 11, fontWeight: '900', letterSpacing: 1, marginTop: 24 }}>TOTAL PAID</Text><Text numberOfLines={1} adjustsFontSizeToFit style={{ color: C.accent, fontFamily: DISPLAY_FONT, fontSize: 40, fontWeight: '900' }}>{formatMoney(receipt.totalMinor)}</Text><Muted>Discount: {formatMoney(receipt.discountMinor)}</Muted></Card> : <Muted>No receipt yet. Complete a purchase in the store.</Muted>}
    {receipt ? <View style={{ marginVertical: 14 }}><Muted>{receipt.signature ? `Server signature: ${receipt.signature.slice(0, 16)}…` : 'Demo purchase - no payment was collected.'}</Muted>{!receipt.pdfBase64 ? <Muted>{receipt.signature ? 'The server confirmed this order but did not include a PDF. Contact the team with your order number.' : 'PDF export is available after a connected checkout. This demo purchase has no PDF attachment.'}</Muted> : null}</View> : null}
    {pdfError ? <Text accessibilityRole="alert" style={{ color: C.danger, marginVertical: 10 }}>{pdfError}</Text> : null}
    {receipt?.pdfBase64 ? <Button title={Platform.OS === 'web' ? 'Download PDF receipt' : 'Save or share PDF receipt'} secondary loading={saving} onPress={() => void sharePdf()} /> : null}
    <Button title="Return to store" onPress={() => router.replace('/(tabs)/store')} />
  </Page>;
}
