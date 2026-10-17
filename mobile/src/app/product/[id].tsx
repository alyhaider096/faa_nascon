import { router, useLocalSearchParams } from 'expo-router';
import React, { useState } from 'react';
import { Pressable, Text, View } from 'react-native';
import { Button, Card, Muted, Page, Pill } from '../../components/UI';
import { PRODUCTS, formatMoney } from '../../data/mock';
import { useApp } from '../../state/AppContext';
import { C } from '../../theme';

export default function ProductDetail() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const { addToCart } = useApp();
  const product = PRODUCTS.find(p => p.id === id);
  const [variantId, setVariantId] = useState(product?.variants[0]?.id ?? '');
  const [quantity, setQuantity] = useState(1);
  if (!product) return <Page title="Product not found"><Muted>This item is unavailable.</Muted></Page>;
  const variant = product.variants.find(v => v.id === variantId)!;
  return <Page eyebrow={product.category} title={product.name} subtitle="Official Alpha Sports club merchandise">
    <Card accent><Text style={{ color: C.accent, fontSize: 36, fontWeight: '900' }}>{formatMoney(product.priceMinor)}</Text><Muted>Mock payment · PKR · signed receipt when connected to backend</Muted></Card>
    <Text style={{ color: C.text, fontSize: 19, fontWeight: '800', marginVertical: 15 }}>Choose a variant</Text>
    {product.variants.map(v => <Card key={v.id} onPress={() => { setVariantId(v.id); setQuantity(1); }} accent={v.id === variantId}><View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}><Text style={{ color: C.text, fontWeight: '800', fontSize: 16 }}>{v.id === variantId ? '●  ' : '○  '}{v.label}</Text><Pill text={`${v.stock} in stock`} tone={v.stock < 2 ? 'gold' : 'mint'} /></View></Card>)}
    <Text style={{ color: C.text, fontSize: 19, fontWeight: '800', marginTop: 18, marginBottom: 12 }}>Quantity</Text>
    <View style={{ flexDirection: 'row', alignItems: 'center', gap: 16, marginBottom: 17 }}>
      <Pressable accessibilityRole="button" accessibilityLabel="Decrease quantity" onPress={() => setQuantity(Math.max(1, quantity - 1))} style={{ width: 48, height: 48, alignItems: 'center', justifyContent: 'center', backgroundColor: C.surface2, borderRadius: 10 }}><Text style={{ color: C.text, fontSize: 25 }}>−</Text></Pressable>
      <Text style={{ color: C.text, fontSize: 20, fontWeight: '900', minWidth: 22, textAlign: 'center' }}>{quantity}</Text>
      <Pressable accessibilityRole="button" accessibilityLabel="Increase quantity" disabled={!variant.stock} onPress={() => setQuantity(Math.max(1, Math.min(variant.stock, quantity + 1)))} style={{ width: 48, height: 48, alignItems: 'center', justifyContent: 'center', backgroundColor: C.surface2, borderRadius: 10 }}><Text style={{ color: C.text, fontSize: 25 }}>+</Text></Pressable>
      <Text style={{ color: C.muted, marginLeft: 'auto' }}>Total  {formatMoney(product.priceMinor * quantity)}</Text>
    </View>
    <Button title={variant.stock ? `Add ${quantity} to bag  →` : 'Out of stock'} disabled={!variant.stock} onPress={() => { addToCart({ variantId: variant.id, name: product.name, label: variant.label, unitPriceMinor: product.priceMinor, quantity }); router.push('/checkout'); }} />
    <Muted>Price, stock and purchase rules are preview data. Backend inventory is authoritative in live mode.</Muted>
  </Page>;
}
