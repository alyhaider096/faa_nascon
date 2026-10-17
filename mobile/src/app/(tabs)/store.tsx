import { router } from 'expo-router';
import React from 'react';
import { Text, View } from 'react-native';
import { Button, Card, Muted, Page, SectionTitle } from '../../components/UI';
import { formatMoney } from '../../data/mock';
import { useApp } from '../../state/AppContext';
import { C, DISPLAY_FONT } from '../../theme';

export default function Store() {
  const { cart, products: PRODUCTS } = useApp();
  const catalogue = PRODUCTS;
  return <Page eyebrow="Club merchandise" title="Store" subtitle="Official club products and matchday items.">
    {PRODUCTS[0] ? <Card accent><Text style={{ color: C.accent, fontSize: 11, fontWeight: '900', letterSpacing: 1 }}>MATCHDAY PICK  /  OFFICIAL STORE</Text><Text style={{ color: C.text, fontFamily: DISPLAY_FONT, fontSize: 30, fontWeight: '900', marginTop: 14 }}>{PRODUCTS[0].name}</Text><Text style={{ color: C.text, fontFamily: DISPLAY_FONT, fontSize: 29, fontWeight: '900', marginTop: 5 }}>{formatMoney(PRODUCTS[0].priceMinor)}</Text><Button title="Shop this item  →" onPress={() => router.push({ pathname: '/product/[id]', params: { id: PRODUCTS[0].id } })} /></Card> : null}
    <SectionTitle title="Catalogue" action={`${catalogue.length} products`} />
    {catalogue.length ? catalogue.map(p => <Card key={p.id} onPress={() => router.push({ pathname: '/product/[id]', params: { id: p.id } })}><Text style={{ color: C.muted, fontSize: 10, fontWeight: '900', letterSpacing: 1 }}>{p.category.toUpperCase()}</Text><Text style={{ color: C.text, fontSize: 18, fontWeight: '800', marginTop: 8 }}>{p.name}</Text><View style={{ flexDirection: 'row', justifyContent: 'space-between', marginTop: 13 }}><Text style={{ color: C.accent, fontWeight: '900' }}>{formatMoney(p.priceMinor)}</Text><Text style={{ color: C.muted, fontSize: 12, fontWeight: '800' }}>VIEW ITEM  →</Text></View></Card>) : <Muted>No merchandise is available yet.</Muted>}
    {cart.length ? <Button title={`Checkout · ${cart.reduce((n, x) => n + x.quantity, 0)} in cart`} onPress={() => router.push('/checkout')} /> : <Muted>Your cart is empty. Choose a product to start.</Muted>}
  </Page>;
}
