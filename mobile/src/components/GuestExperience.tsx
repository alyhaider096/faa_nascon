import { Ionicons } from '@expo/vector-icons';
import { router } from 'expo-router';
import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { ActivityIndicator, Modal, Platform, Pressable, ScrollView, StyleSheet, Text, TextInput, View, useWindowDimensions } from 'react-native';
import { ApiError, Bootstrap } from '../data/api';
import { ChatMessage, PublicMatch, day2Request, getGuestToken, loadPublicMatch, normalizeMatch, normalizeMessage, normalizeProduct, readGuestCart, realtimeUrls, writeGuestCart } from '../data/day2';
import { useApp } from '../state/AppContext';
import { C, DISPLAY_FONT } from '../theme';
import { LiveVideo, LiveVideoHandle } from './LiveVideo';

type PendingIntent = 'chat' | 'checkout' | null;
type Props = { id: string; mode: 'preview' | 'live' | 'vod' | 'notice' | 'costream'; noticeState?: string };

const money = (minor: number, currency = 'PKR') => `${currency} ${(minor / 100).toLocaleString(undefined, { minimumFractionDigits: 2 })}`;
const eventType = (raw: any) => String(raw?.type ?? raw?.event_type ?? raw?.kind ?? '');
const eventPayload = (raw: any) => raw?.payload ?? raw?.data ?? raw;

export function GuestExperience({ id, mode, noticeState }: Props) {
  const { width } = useWindowDimensions();
  const { account, serverUrl, login, authorizedRequest } = useApp();
  const [match, setMatch] = useState<PublicMatch | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [connection, setConnection] = useState<'connecting' | 'live' | 'reconnecting'>('connecting');
  const [guestToken, setGuestToken] = useState('');
  const [cartCount, setCartCount] = useState(0);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [chatText, setChatText] = useState('');
  const [modalVisible, setModalVisible] = useState(false);
  const [pendingIntent, setPendingIntent] = useState<PendingIntent>(null);
  const [email, setEmail] = useState('viewer@nascon.test');
  const [password, setPassword] = useState('Nascon@26');
  const [authError, setAuthError] = useState('');
  const [busy, setBusy] = useState(false);
  const [notification, setNotification] = useState('');
  const videoRef = useRef<LiveVideoHandle>(null);
  const resumeRef = useRef({ time: 0, playing: false });
  const seenSequences = useRef(new Set<number>());
  const socketCandidate = useRef(0);
  const activeMatchId = match?.matchId;
  const wide = width >= 900;

  const load = useCallback(async () => {
    setLoading(true); setError('');
    try {
      const token = await getGuestToken(serverUrl); setGuestToken(token);
      const cart = await readGuestCart(); setCartCount(cart.reduce((sum, item) => sum + item.quantity, 0));
      if (mode === 'costream') {
        const raw = await day2Request<any>(serverUrl, `/api/v1/public/costream/${encodeURIComponent(id)}`);
        setMatch(normalizeMatch(raw?.match ?? { ...raw, match_id: raw?.match_id ?? id, playback_url: raw?.composite_playback_url, chat_room_id: raw?.chat_room_id }, id));
      } else {
        setMatch(await loadPublicMatch(serverUrl, id));
      }
      try {
        const chat = await day2Request<any>(serverUrl, `/api/v1/chat/${encodeURIComponent(mode === 'costream' ? `chat-${id}` : `chat-${id}`)}`, { token });
        const list = Array.isArray(chat?.messages) ? chat.messages : [];
        setMessages(list.map((item: any, index: number) => normalizeMessage(item, index + 1)));
      } catch { /* Chat history is optional; realtime remains active. */ }
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'This experience could not be loaded.');
    } finally { setLoading(false); }
  }, [id, mode, serverUrl]);

  useEffect(() => { void load(); }, [load]);

  useEffect(() => {
    if (!activeMatchId || !guestToken || mode === 'preview' || mode === 'notice') return;
    let socket: WebSocket | null = null;
    let stopped = false;
    let retry: ReturnType<typeof setTimeout> | null = null;
    const candidates = realtimeUrls(serverUrl, mode === 'costream' ? id : activeMatchId, guestToken);
    socketCandidate.current = 0;
    const connect = () => {
      if (stopped) return;
      setConnection(socket ? 'reconnecting' : 'connecting');
      socket = new WebSocket(candidates[Math.min(socketCandidate.current, candidates.length - 1)]);
      socket.onopen = () => setConnection('live');
      socket.onmessage = event => {
        try {
          const raw = JSON.parse(String(event.data));
          const payload = eventPayload(raw);
          const sequence = Number(raw?.sequence ?? payload?.sequence ?? 0);
          if (sequence && seenSequences.current.has(sequence)) return;
          if (sequence) seenSequences.current.add(sequence);
          const type = eventType(raw) || eventType(payload);
          if (type.includes('score') || payload?.home_score !== undefined) {
            if (payload?.home_score === undefined && payload?.home?.score === undefined && mode !== 'costream') {
              void loadPublicMatch(serverUrl, activeMatchId).then(setMatch).catch(() => setError('A score update arrived, but the latest projection could not be loaded.'));
            } else setMatch(current => current ? { ...current, homeScore: payload?.home_score ?? payload?.home?.score ?? current.homeScore, awayScore: payload?.away_score ?? payload?.away?.score ?? current.awayScore } : current);
            setNotification('Score updated live');
          } else if (type.includes('product') || payload?.pinned_product) {
            setMatch(current => current ? { ...current, pinnedProduct: normalizeProduct(payload?.product ?? payload?.pinned_product ?? payload) } : current);
          } else if (type.includes('chat') || payload?.message?.text) {
            const next = normalizeMessage(payload?.message ?? payload, sequence);
            setMessages(current => current.some(item => item.id === next.id || (next.sequence && item.sequence === next.sequence)) ? current : [...current, next]);
          } else if (type.includes('state') || payload?.status) {
            setMatch(current => current ? { ...current, status: payload?.status ?? current.status, playbackUrl: payload?.playback_url ?? current.playbackUrl } : current);
          } else if (type.includes('invitation') || type.includes('order')) {
            setNotification(String(payload?.message ?? (type.includes('invitation') ? 'New co-stream invitation' : 'Order status updated')));
          }
        } catch { /* Ignore malformed realtime frames, keep the stream alive. */ }
      };
      socket.onerror = () => socket?.close();
      socket.onclose = () => { if (!stopped) { setConnection('reconnecting'); if (socketCandidate.current < candidates.length - 1) socketCandidate.current += 1; retry = setTimeout(connect, 1200); } };
    };
    connect();
    return () => { stopped = true; if (retry) clearTimeout(retry); socket?.close(); };
  }, [activeMatchId, guestToken, id, mode, serverUrl]);

  const product = match?.pinnedProduct;
  const addProduct = useCallback(async () => {
    if (!product) return;
    const cart = await readGuestCart();
    const existing = cart.find(item => item.variantId === product.variantId);
    const updated = existing ? cart.map(item => item.variantId === product.variantId ? { ...item, quantity: item.quantity + 1 } : item) : [...cart, { variantId: product.variantId, quantity: 1 }];
    await writeGuestCart(updated); setCartCount(updated.reduce((sum, item) => sum + item.quantity, 0));
    void day2Request(serverUrl, '/api/v1/guest/cart', { method: 'POST', token: guestToken, body: { items: updated.map(item => ({ variant_id: item.variantId, quantity: item.quantity })) } }).catch(() => undefined);
  }, [guestToken, product, serverUrl]);

  const rememberAndAuthenticate = useCallback((intent: PendingIntent) => {
    resumeRef.current = { time: videoRef.current?.currentTime() ?? 0, playing: videoRef.current?.isPlaying() ?? false };
    setPendingIntent(intent); setAuthError(''); setModalVisible(true);
  }, []);

  const sendChat = useCallback(async () => {
    const text = chatText.trim(); if (!text || busy) return;
    setBusy(true); setError('');
    const body = { chat_room_id: match?.chatRoomId ?? `chat-${id}`, message_id: `mobile-${Date.now()}`, text };
    try {
      if (account) await authorizedRequest('/api/v1/chat', body);
      else await day2Request(serverUrl, '/api/v1/chat', { method: 'POST', token: guestToken, body });
      setChatText('');
    } catch (cause) {
      if (cause instanceof ApiError && cause.status === 403 && (cause.code === 'GUEST_WRITE_FORBIDDEN' || !account)) rememberAndAuthenticate('chat');
      else setError(cause instanceof Error ? cause.message : 'Message could not be sent.');
    } finally { setBusy(false); }
  }, [account, authorizedRequest, busy, chatText, guestToken, id, match?.chatRoomId, rememberAndAuthenticate, serverUrl]);

  const completeAuthentication = useCallback(async () => {
    if (busy) return; setBusy(true); setAuthError('');
    try {
      const problem = await login(email, password);
      if (problem) { setAuthError(problem); return; }
      const bootstrap = await authorizedRequest<Bootstrap>('/api/v1/bootstrap');
      const cart = await readGuestCart();
      if (cart.length) {
        await authorizedRequest('/audit/v1/guest/cart-merge', {
          guest_token: guestToken,
          registered_user_id: bootstrap.user.user_id,
          guest_cart: cart.map(item => ({ variant_id: item.variantId, quantity: item.quantity })),
          test_write_block: true,
        });
      }
      setModalVisible(false);
      requestAnimationFrame(() => videoRef.current?.restore(resumeRef.current.time, resumeRef.current.playing));
      const action = pendingIntent; setPendingIntent(null);
      if (action === 'chat' && chatText.trim()) {
        await authorizedRequest('/api/v1/chat', { chat_room_id: match?.chatRoomId ?? `chat-${id}`, message_id: `mobile-${Date.now()}`, text: chatText.trim() });
        setChatText('');
      }
      if (action === 'checkout') router.push('/checkout');
    } catch (cause) {
      const code = cause instanceof ApiError ? cause.code : undefined;
      setAuthError(code === 'GUEST_TOKEN_ALREADY_MERGED' ? 'This guest cart was already merged into another account.' : code === 'OUT_OF_STOCK' ? 'The selected item sold out. Your cart is unchanged.' : cause instanceof Error ? cause.message : 'Sign in could not be completed.');
    } finally { setBusy(false); }
  }, [authorizedRequest, busy, chatText, email, guestToken, id, login, match?.chatRoomId, password, pendingIntent]);

  const stateLabel = mode === 'notice' ? (noticeState ?? match?.status ?? 'unavailable').replaceAll('_', ' ') : match?.status ?? mode;
  const scoreLabel = match ? `${match.homeScore} - ${match.awayScore}` : '— - —';
  const timeline = useMemo(() => match?.timeline.slice().sort((a, b) => b.sequence - a.sequence) ?? [], [match?.timeline]);

  return <View style={styles.screen}>
    <View style={styles.topbar}>
      <Pressable accessibilityRole="button" accessibilityLabel="Back" onPress={() => router.canGoBack() ? router.back() : router.replace('/login')} style={styles.iconButton}><Ionicons name="arrow-back" color={C.text} size={22} /></Pressable>
      <View style={{ flex: 1 }}><Text style={styles.brand}>LEAGUEOPS LIVE</Text><Text style={[styles.connection, error ? { color: C.danger } : {}]}>{error ? 'CONNECTION UNAVAILABLE' : connection === 'live' ? '● LIVE CONNECTION' : connection.toUpperCase()}</Text></View>
      <Pressable accessibilityRole="button" accessibilityLabel="Scan another QR" onPress={() => router.push('/scanner')} style={styles.iconButton}><Ionicons name="qr-code-outline" color={C.text} size={22} /></Pressable>
    </View>
    <ScrollView contentContainerStyle={styles.content} keyboardShouldPersistTaps="handled">
      {notification ? <Pressable accessibilityRole="button" accessibilityLabel={`${notification}. Dismiss`} onPress={() => setNotification('')} style={styles.notification}><Ionicons name="notifications" color={C.bg} size={18} /><Text style={styles.notificationText}>{notification}</Text><Ionicons name="close" color={C.bg} size={17} /></Pressable> : null}
      {loading ? <View style={styles.center}><ActivityIndicator size="large" color={C.accent} /><Text style={styles.muted}>Connecting to the live match…</Text></View> : null}
      {error ? <View accessibilityRole="alert" style={styles.error}><Ionicons name="alert-circle" color={C.danger} size={22} /><Text style={styles.errorText}>{error}</Text><Pressable accessibilityRole="button" onPress={() => void load()} style={styles.smallButton}><Text style={styles.smallButtonText}>Retry</Text></Pressable></View> : null}
      {match ? <>
        <View style={styles.heroRow}>
          <View style={{ flex: 1 }}><Text style={styles.eyebrow}>{mode === 'costream' ? 'FOUR-WAY CO-STREAM' : match.competition.toUpperCase()}</Text><Text style={styles.title}>{match.title}</Text></View>
          <View style={styles.statePill}><Text style={styles.stateText}>{stateLabel.toUpperCase()}</Text></View>
        </View>
        <View style={[styles.mainGrid, wide && styles.mainGridWide]}>
          <View style={styles.mediaColumn}>
            <LiveVideo ref={videoRef} uri={mode === 'preview' || mode === 'notice' ? null : match.playbackUrl} label={match.title} />
            <View testID="live-score-banner" accessibilityLabel={`Live score ${match.homeName} ${match.homeScore}, ${match.awayName} ${match.awayScore}`} style={styles.scoreBanner}>
              <View style={styles.team}><Text numberOfLines={1} style={styles.teamName}>{match.homeName}</Text></View>
              <Text style={styles.score}>{scoreLabel}</Text>
              <View style={styles.team}><Text numberOfLines={1} style={styles.teamName}>{match.awayName}</Text></View>
            </View>
            <Text style={styles.sectionTitle}>Match timeline</Text>
            {timeline.length ? timeline.map(item => <View key={item.id} style={styles.timelineRow}><Text style={styles.sequence}>#{item.sequence}</Text><Text style={styles.timelineText}>{item.label}</Text></View>) : <Text style={styles.muted}>No match events yet. Live updates will appear here.</Text>}
          </View>
          <View style={styles.sideColumn}>
            <View testID="pinned-merch-card" style={styles.merchCard}>
              <Text style={styles.merchKicker}>PINNED MATCHDAY DROP</Text>
              <Text style={styles.productName}>{product?.name ?? 'No product pinned'}</Text>
              {product ? <><Text style={styles.productMeta}>{product.variant} · {money(product.priceMinor, product.currency)}</Text><Pressable testID="add-to-guest-cart-btn" accessibilityRole="button" accessibilityLabel={`Add ${product.name}, ${product.variant}, to guest cart`} onPress={() => void addProduct()} style={styles.primaryButton}><Ionicons name="bag-add-outline" size={20} color={C.bg} /><Text style={styles.primaryText}>Add to cart</Text></Pressable></> : <Text style={styles.merchMuted}>The organizer has not pinned merchandise.</Text>}
              <View style={styles.cartRow}><Text style={styles.merchMuted}>Guest cart</Text><Text testID="guest-cart-count" accessibilityLabel={`${cartCount} items in guest cart`} style={styles.cartCount}>{cartCount}</Text></View>
              <Pressable accessibilityRole="button" onPress={() => account ? router.push('/checkout') : rememberAndAuthenticate('checkout')} style={styles.checkoutButton}><Text style={styles.checkoutText}>Checkout securely</Text></Pressable>
            </View>
            <View style={styles.chatCard}>
              <View style={styles.chatHeading}><View><Text style={styles.cardKicker}>LIVE ROOM</Text><Text style={styles.chatTitle}>Match chat</Text></View><Ionicons name="people-outline" color={C.muted} size={22} /></View>
              <ScrollView testID="chat-message-list" accessibilityLabel="Live chat messages" style={styles.messageList} nestedScrollEnabled>
                {messages.length ? messages.map(message => <View key={message.id} style={styles.message}><Text style={styles.sender}>{message.sender}</Text><Text style={styles.messageText}>{message.text}</Text></View>) : <Text style={styles.muted}>No messages yet. Be the first member to join the conversation.</Text>}
              </ScrollView>
              <View style={styles.composeRow}>
                <TextInput testID="chat-input-field" accessibilityLabel="Chat message" value={chatText} onChangeText={setChatText} placeholder="Write a message" placeholderTextColor="#BAC9DB" style={styles.chatInput} onSubmitEditing={() => void sendChat()} returnKeyType="send" />
                <Pressable testID="chat-send-btn" accessibilityRole="button" accessibilityLabel="Send chat message" disabled={!chatText.trim() || busy} onPress={() => void sendChat()} style={({ pressed }) => [styles.sendButton, (!chatText.trim() || busy) && { opacity: .45 }, pressed && { transform: [{ scale: .96 }] }]}><Ionicons name="send" color={C.bg} size={19} /></Pressable>
              </View>
            </View>
          </View>
        </View>
      </> : null}
    </ScrollView>
    <Modal visible={modalVisible} transparent animationType="fade" onRequestClose={() => setModalVisible(false)}>
      <View testID="progressive-auth-modal" accessibilityViewIsModal accessibilityLabel="Sign in to continue" style={styles.modalBackdrop}>
        <View style={styles.modalCard}>
          <Pressable accessibilityRole="button" accessibilityLabel="Close sign in" onPress={() => setModalVisible(false)} style={[styles.iconButton, { alignSelf: 'flex-end' }]}><Ionicons name="close" color={C.text} size={22} /></Pressable>
          <Text style={styles.modalEyebrow}>YOUR MATCH STAYS OPEN</Text><Text style={styles.modalTitle}>Sign in to continue</Text>
          <Text style={styles.modalCopy}>Guests can watch and shop. Sign in to send messages or checkout; your cart and playback position will be restored.</Text>
          <TextInput accessibilityLabel="Email" value={email} onChangeText={setEmail} autoCapitalize="none" keyboardType="email-address" placeholder="Email" placeholderTextColor="#BAC9DB" style={styles.modalInput} />
          <TextInput accessibilityLabel="Password" value={password} onChangeText={setPassword} secureTextEntry placeholder="Password" placeholderTextColor="#BAC9DB" style={styles.modalInput} />
          {authError ? <Text accessibilityRole="alert" style={styles.authError}>{authError}</Text> : null}
          <Pressable accessibilityRole="button" disabled={busy} onPress={() => void completeAuthentication()} style={styles.primaryButton}>{busy ? <ActivityIndicator color={C.bg} /> : <Text style={styles.primaryText}>Sign in and resume</Text>}</Pressable>
        </View>
      </View>
    </Modal>
  </View>;
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: C.bg },
  topbar: { minHeight: 72, paddingHorizontal: 18, flexDirection: 'row', alignItems: 'center', gap: 14, backgroundColor: C.surface },
  iconButton: { width: 48, height: 48, borderRadius: 24, alignItems: 'center', justifyContent: 'center', backgroundColor: '#222B31' },
  brand: { color: C.text, fontWeight: '900', fontSize: 15, letterSpacing: 1.2 },
  connection: { color: '#7FE1BA', fontSize: 10, fontWeight: '900', letterSpacing: 1.1, marginTop: 3 },
  content: { width: '100%', maxWidth: 1280, alignSelf: 'center', padding: 20, paddingBottom: 80 },
  center: { minHeight: 420, alignItems: 'center', justifyContent: 'center', gap: 14 },
  heroRow: { flexDirection: 'row', alignItems: 'flex-start', gap: 16, marginBottom: 20 },
  eyebrow: { color: C.accent, fontWeight: '900', fontSize: 11, letterSpacing: 1.6, marginBottom: 7 },
  title: { color: C.text, fontSize: 28, lineHeight: 34, fontWeight: '900', fontFamily: DISPLAY_FONT, textTransform: 'uppercase' },
  statePill: { backgroundColor: '#22352D', borderRadius: 18, paddingVertical: 8, paddingHorizontal: 12 },
  stateText: { color: '#8CE8C2', fontWeight: '900', fontSize: 10, letterSpacing: 1 },
  mainGrid: { gap: 18 }, mainGridWide: { flexDirection: 'row', alignItems: 'flex-start' }, mediaColumn: { flex: 1.55, minWidth: 0 }, sideColumn: { flex: 1, minWidth: 0, gap: 16 },
  scoreBanner: { minHeight: 96, backgroundColor: C.surface, marginTop: 12, borderRadius: 22, padding: 16, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 18 },
  team: { flex: 1 }, teamName: { color: C.text, textAlign: 'center', fontWeight: '800', fontSize: 15 }, score: { color: '#FFFFFF', fontSize: 34, fontWeight: '900', letterSpacing: 1.5 },
  sectionTitle: { color: C.text, fontSize: 19, fontWeight: '900', marginTop: 24, marginBottom: 12 },
  timelineRow: { minHeight: 54, flexDirection: 'row', alignItems: 'center', backgroundColor: '#151B20', borderRadius: 16, paddingHorizontal: 15, marginBottom: 8 },
  sequence: { color: C.accent, width: 48, fontWeight: '900' }, timelineText: { color: C.text, flex: 1, fontSize: 14 },
  merchCard: { backgroundColor: '#F2E6C9', borderRadius: 24, padding: 20 }, merchMuted: { color: '#51483C', fontSize: 14, lineHeight: 21 }, merchKicker: { color: '#6D4A1E', fontWeight: '900', fontSize: 10, letterSpacing: 1.3 }, cardKicker: { color: C.gold, fontWeight: '900', fontSize: 10, letterSpacing: 1.3 },
  productName: { color: '#141516', fontSize: 24, lineHeight: 28, fontWeight: '900', marginTop: 10 }, productMeta: { color: '#56504A', marginTop: 7, marginBottom: 10, fontWeight: '700' },
  primaryButton: { minHeight: 50, borderRadius: 25, backgroundColor: C.accent, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 9, paddingHorizontal: 18, marginTop: 12 }, primaryText: { color: C.bg, fontWeight: '900', fontSize: 15 },
  cartRow: { minHeight: 48, flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginTop: 8 }, cartCount: { minWidth: 34, height: 34, borderRadius: 17, textAlign: 'center', textAlignVertical: 'center', paddingTop: Platform.OS === 'web' ? 8 : 0, backgroundColor: '#15191C', color: '#FFFFFF', fontWeight: '900' },
  checkoutButton: { minHeight: 48, borderRadius: 24, alignItems: 'center', justifyContent: 'center', backgroundColor: '#272C2E' }, checkoutText: { color: '#FFFFFF', fontWeight: '800' },
  chatCard: { backgroundColor: C.surface, borderRadius: 24, padding: 18 }, chatHeading: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' }, chatTitle: { color: C.text, fontSize: 21, fontWeight: '900', marginTop: 4 },
  messageList: { maxHeight: 270, minHeight: 150, marginVertical: 14 }, message: { backgroundColor: '#222B31', borderRadius: 14, padding: 12, marginBottom: 8 }, sender: { color: C.accent, fontSize: 11, fontWeight: '900', marginBottom: 4 }, messageText: { color: C.text, lineHeight: 20 },
  composeRow: { flexDirection: 'row', gap: 9, alignItems: 'center' }, chatInput: { minHeight: 50, flex: 1, borderRadius: 25, backgroundColor: '#29333B', color: C.text, paddingHorizontal: 17, fontSize: 16 }, sendButton: { width: 50, height: 50, borderRadius: 25, alignItems: 'center', justifyContent: 'center', backgroundColor: C.accent },
  muted: { color: C.muted, fontSize: 14, lineHeight: 21 }, error: { backgroundColor: '#3C2428', borderRadius: 18, padding: 14, flexDirection: 'row', alignItems: 'center', gap: 10, marginBottom: 18 }, errorText: { color: C.text, flex: 1 }, smallButton: { minHeight: 44, paddingHorizontal: 15, borderRadius: 22, backgroundColor: C.danger, justifyContent: 'center' }, smallButtonText: { color: '#221114', fontWeight: '900' },
  notification: { minHeight: 48, borderRadius: 24, backgroundColor: C.accent, flexDirection: 'row', alignItems: 'center', gap: 9, paddingHorizontal: 16, marginBottom: 14 }, notificationText: { color: C.bg, fontWeight: '900', flex: 1 },
  modalBackdrop: { flex: 1, backgroundColor: 'rgba(0,0,0,.78)', alignItems: 'center', justifyContent: 'center', padding: 18 }, modalCard: { width: '100%', maxWidth: 460, borderRadius: 28, backgroundColor: C.surface, padding: 22 }, modalEyebrow: { color: C.accent, fontSize: 10, fontWeight: '900', letterSpacing: 1.4 }, modalTitle: { color: C.text, fontSize: 29, fontWeight: '900', marginTop: 7 }, modalCopy: { color: C.muted, lineHeight: 21, marginVertical: 12 }, modalInput: { minHeight: 52, borderRadius: 16, backgroundColor: '#29333B', color: C.text, paddingHorizontal: 16, fontSize: 16, marginTop: 10 }, authError: { color: C.danger, marginTop: 10 },
});

