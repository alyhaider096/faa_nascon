# Day 2 frontend integration contract

This file records the frontend calls implemented by Ali. Abdullah owns the backend implementation and must confirm any route marked **team contract** before final integration. Fatima owns automated QA and evidence.

No signing salt belongs in the frontend. Member JWTs are sent with `Authorization: Bearer <token>`. Anonymous guest requests use the short-lived backend guest token. Errors use `{"error":{"code","message","details"}}`.

## Public experience

| Purpose | Method and path | Authentication | Frontend expectation |
| --- | --- | --- | --- |
| Match experience | `GET /api/v1/public/matches/{match_id}` **team contract** | Guest allowed | Match identity/status, teams and scores, `playback_url`, timeline, `chat_room_id`, pinned product and variants. The client temporarily accepts the existing `GET /api/v1/matches/{id}` shape as a compatibility fallback. |
| Co-stream experience | `GET /api/v1/public/costream/{session_id}` **team contract** | Guest allowed | Session status, match/teams when available, `composite_playback_url`, room ID, layout, host and participants. |
| Player profile | `GET /api/v1/players/{player_id}` **team contract** | Guest allowed | Identity, affiliation, career matches, upcoming fixtures, followers and VOD archive. |
| Club profile | `GET /api/v1/public/clubs/{club_id}` | Guest allowed | Club identity, roster/affiliation, fixtures and VOD archive. The Day 1 `/api/v1/clubs/{club_id}` route remains authenticated and tenant-scoped. |
| Follow profile | `POST /api/v1/follows` **team contract** | Member body `{entity_type,entity_id,action}`; response `{following,followers}` is authoritative. |
| QR metadata | `GET /audit/v1/qr/{entity_id}?inspect=true` | Guest allowed | Exact `target_route`; frontend does not infer state. |
| Stable QR redirect | `GET /q/{short_code}` | Guest allowed | HTTP 302 to the current `/web/...` route. |
| QR exports | `GET /audit/v1/qr/{entity_id}/export.{svg,png,pdf}` | Organizer/admin UI | Real downloadable asset and correct MIME type. |

Web production is exported with `npm run web:export`. Abdullah serves the generated SPA on the API origin at port 8080 and returns its index for `/web/*` client routes. On that origin the frontend uses same-origin requests. During Expo development it uses the configured server address.

## Guest cart and progressive authentication

| Purpose | Method and path | Request/response notes |
| --- | --- | --- |
| Guest session | `POST /api/v1/guest/session` **team contract** | Returns `{guest_token}`. Until available, the deterministic audit reset token is used only for the seeded test environment. |
| Cart staging | `POST /api/v1/guest/cart` **team contract** | `{items:[{variant_id,quantity}]}`; guest cart also persists locally so navigation and login do not lose it. Prices are never submitted as authoritative. |
| Member login | `POST /api/v1/auth/login` | Existing Day 1 `{email,password}` contract. |
| Atomic merge | `POST /audit/v1/guest/cart-merge` | Official payload and idempotency rules. The authenticated member must match `registered_user_id`. |
| Checkout | Existing `/api/v1/checkout` for members; `/audit/v1/checkout` remains the audit guest-rejection probe. | Guest receives exact `403 GUEST_WRITE_FORBIDDEN`. |

The client stores route, playback time, play/pause state, cart and pending intent before opening authentication. After login it merges once, restores playback and resumes chat or checkout.

## Chat and realtime

- `GET /api/v1/chat/{chat_room_id}` is the optional **team contract** for history.
- `POST /api/v1/chat` is the shared write route. Guests must receive exact `403 GUEST_WRITE_FORBIDDEN`; members receive normal acceptance/moderation responses.
- `WS /ws/matches/{match_id}?token=<guest-or-member-token>` is the required realtime path. During integration the client falls back to the existing authenticated `/ws/v1/matches/{match_id}` path. Its current `score_updated` notification contains only IDs/version, so the client refreshes the authoritative public projection rather than inventing a score. Abdullah still needs to expose the official guest-readable socket contract.
- Clients deduplicate by sequence and never append a rejected chat message. Score delivery must reach the DOM within 500 ms without replacing the media element.

## Creator and co-stream controls

| Purpose | Method and path | Expected response |
| --- | --- | --- |
| Stream key lifecycle | `POST /api/v1/stream/key` **team contract**, with `/audit/v1/stream/key` compatibility fallback | `stream_key`, status, RTMP and WebRTC/WHIP ingest endpoints, playback URL. |
| Co-stream public state | `GET /api/v1/public/costream/{session_id}` **team contract** | Host, participants, participant count, layout, chat room and composite playback URL. |
| Co-stream command | `POST /api/v1/costream/sessions/{session_id}/actions` **team contract** | Body `{action,...}` for `set_layout`, `mute`, `spotlight`, `kick`, invite, join, leave and stop; response is authoritative updated session. |

Native WHIP publication sends an SDP offer to the backend-provided endpoint, applies the SDP answer, retains the returned session `Location`, and deletes that resource when stopping. The complete stream key is not rendered in the UI.

## Routes and selectors

Public routes are `/web/matches/{id}/{preview|live|vod|notice}`, `/web/costream/{id}`, `/web/players/{id}` and `/web/clubs/{id}`. Native links `nascon://entity/match-m1` and `nascon://stream/cs-session-101` bypass login for read-only viewing.

Both match-live and co-stream experiences expose exactly one interactive/container instance of:

`guest-video-player`, `live-score-banner`, `pinned-merch-card`, `add-to-guest-cart-btn`, `guest-cart-count`, `chat-message-list`, `chat-input-field`, `chat-send-btn`, `progressive-auth-modal`.
