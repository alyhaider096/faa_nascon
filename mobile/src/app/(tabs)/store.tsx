import { router } from 'expo-router';
import React from 'react';
import { Text, View } from 'react-native';
import { Button, Card, Muted, Page, Pill, SectionTitle } from '../../components/UI';
import { PRODUCTS, formatMoney } from '../../data/mock';
import { useApp } from '../../state/AppContext';
import { C } from '../../theme';

export default function Store() {
  const { cart } = useApp();
  return <Page eyebrow="Club merchandise" title="Store" subtitle="Official club products and matchday items.">
    {PRODUCTS[0] ? <Card accent><Pill text="MATCHDAY PICK" /><Text style={{ color: C.text, fontSize: 23, fontWeight: '800', marginTop: 14 }}>{PRODUCTS[0].name}</Text><Text style={{ color: C.accent, fontSize: 19, fontWeight: '800', marginTop: 5 }}>{formatMoney(PRODUCTS[0].priceMinor)}</Text><Button title="Shop this item  →" onPress={() => router.push({ pathname: '/product/[id]', params: { id: PRODUCTS[0].id } })} /></Card> : null}
    <SectionTitle title="Catalogue" action={`${PRODUCTS.length} products`} />
    {PRODUCTS.length ? PRODUCTS.map(p => <Card key={p.id} onPress={() => router.push({ pathname: '/product/[id]', params: { id: p.id } })}><View style={{ flexDirection: 'row', justifyContent: 'space-between' }}><View style={{ flex: 1 }}><Text style={{ color: C.muted, fontSize: 11, fontWeight: '800' }}>{p.category}</Text><Text style={{ color: C.text, fontSize: 18, fontWeight: '800', marginTop: 5 }}>{p.name}</Text></View><Text style={{ color: C.accent, fontWeight: '800' }}>{formatMoney(p.priceMinor)}</Text></View></Card>) : <Muted>No merchandise is available yet.</Muted>}
    {cart.length ? <Button title={`Checkout · ${cart.reduce((n, x) => n + x.quantity, 0)} in cart`} onPress={() => router.push('/checkout')} /> : <Muted>Your cart is empty. Choose a product to start.</Muted>}
  </Page>;
}
