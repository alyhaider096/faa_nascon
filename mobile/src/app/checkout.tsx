import { router } from 'expo-router';
import React, { useState } from 'react';
import { Alert, Text, View } from 'react-native';
import { Button, Card, Field, Muted, Page, SectionTitle } from '../components/UI';
import { formatMoney } from '../data/mock';
import { useApp } from '../state/AppContext';
import { C } from '../theme';

export default function Checkout() {
  const { cart, checkout, clearCart } = useApp();
  const [discount, setDiscount] = useState('');
  const [token, setToken] = useState('tok_success');
  const [error, setError] = useState('');
  const [paying, setPaying] = useState(false);
  const subtotal = cart.reduce((n, item) => n + item.unitPriceMinor * item.quantity, 0);
  return <Page eyebrow="Secure mock checkout" title="Your bag" subtitle="Review the order before payment.">
    {cart.length ? cart.map(item => <Card key={item.variantId}><Text style={{ color: C.text, fontSize: 17, fontWeight: '800' }}>{item.name}</Text><Muted>{item.label} · Quantity {item.quantity}</Muted><Text style={{ color: C.accent, marginTop: 8, fontWeight: '800' }}>{formatMoney(item.unitPriceMinor * item.quantity)}</Text></Card>) : <Muted>Your bag is empty. Visit the store to add a product.</Muted>}
    <SectionTitle title="Payment" />
    <Field label="Discount code" value={discount} onChangeText={setDiscount} placeholder="WELCOME10" />
    <Field label="Mock payment token" value={token} onChangeText={setToken} placeholder="tok_success" />
    <Card accent><View style={{ flexDirection: 'row', justifyContent: 'space-between' }}><Muted>Subtotal</Muted><Text style={{ color: C.text, fontWeight: '800' }}>{formatMoney(subtotal)}</Text></View><View style={{ flexDirection: 'row', justifyContent: 'space-between', marginTop: 9 }}><Muted>Total after discount</Muted><Text style={{ color: C.accent, fontWeight: '900', fontSize: 20 }}>{formatMoney(subtotal - (discount.toUpperCase() === 'WELCOME10' ? Math.floor(subtotal / 10) : 0))}</Text></View></Card>
    {error ? <Text style={{ color: C.danger }}>{error}</Text> : null}
    <Button title={paying ? 'Processing payment…' : 'Pay with mock gateway'} disabled={!cart.length || paying} onPress={() => Alert.alert('Confirm purchase', 'Proceed with this mock payment?', [{ text: 'Cancel', style: 'cancel' }, { text: 'Pay', onPress: async () => { setPaying(true); setError(''); const problem = await checkout(token, discount); setPaying(false); if (problem) setError(problem); else router.replace('/receipt'); } }])} />
    <Button title="Clear bag" secondary onPress={() => Alert.alert('Clear your bag?', 'All selected items will be removed.', [{ text: 'Cancel', style: 'cancel' }, { text: 'Clear bag', style: 'destructive', onPress: clearCart }])} />
  </Page>;
}
