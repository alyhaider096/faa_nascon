# Review of Ali's Day 2 frontend

Reviewed commit: `330d475dcdb93cbe2dab47c184ec7904c935ca38`, verified on remote
main on 18 October 2026. No application source was edited during this review.

The common tabs, role-gated scoring/roster/creator entry points, sign-out,
public routes and native deep-link resolver are present. The earlier scoring
feedback and post-sync refresh fixes are retained. The implementation is not yet
ready to mark all stated user journeys passed.

## Findings

### P1 - Fresh guest sign-in can take the demo path and never obtain a JWT

`mobile/src/components/GuestExperience.tsx:142` calls the context's demo-aware
`login()`, then immediately calls authenticated bootstrap. AppContext defaults
to demo mode (`:64`, persisted fallback at `:91`). Its demo branch (`:141-146`)
sets a local account and returns success without setting `tokenRef` or contacting
the login endpoint. Thus a fresh QR visitor using a listed account reaches
bootstrap without a member JWT and cannot resume chat/checkout; real credentials
outside the demo list are rejected locally. Guest authentication should use an
explicit real-login path and the same API origin as the public experience.

A focused execution of the actual login callback reproduced success with zero
login requests and a null token. This was a source-level unit reproduction,
not a device or live-server test.

### P1 - Successful guest cart merge does not hydrate Checkout's cart

`GuestExperience.tsx:147-161` discards the merge response and navigates to
`/checkout`. Guest additions live in `day2_guest_cart`, whereas Checkout reads
AppContext's separate `cart` (`mobile/src/app/checkout.tsx:10`). Neither the
merge handler nor bootstrap refresh imports `active_cart` into that state.
For a newly authenticated guest, Checkout therefore displays an empty bag and
disables payment despite a successful backend merge. An already logged-in
member adding merchandise on the guest page also writes only the guest cart
and navigates straight to the separate Checkout cart.

Import the authoritative merged cart into the member cart or make Checkout load
it from the backend. Consume/clear the local guest cart and renew the guest
session after successful merge so future carts do not reuse an already-merged
token with a changed payload.

### P1 - Failed WHIP negotiation leaves camera/microphone resources active

`mobile/src/components/WhipPublisher.native.tsx:24-44` acquires media tracks and
creates a peer before network/SDP operations that can fail. No error cleanup wraps
that sequence. Creator's catch changes the visual state but never calls stop.
The publisher also has no unmount cleanup. After rejection/timeout or leaving
the screen, acquired media can remain active until an explicit stop/retry.

A focused execution with mocked hardware and an HTTP 503 response reproduced
zero stopped tracks and zero closed peers after rejection. Explicit stop then
released both, confirming that the existing cleanup path is simply not invoked.
Use failure/unmount cleanup and preserve the last acknowledged state separately.

### P1 - A nested match object drops the co-stream playback URL

`GuestExperience.tsx:50` chooses `raw.match` ahead of the object that maps
`composite_playback_url` to `playback_url`. A valid session response containing
both nested match data and a top-level composite URL therefore normalizes to
`playbackUrl: null` unless the nested match redundantly includes a playback URL.
The video shows stream unavailable even though the session supplied playback.
Overlay the session playback and chat metadata onto the nested match rather than
discarding them. A focused execution of the current normalization expression
reproduced the null playback result.

### P2 - Every player sees co-stream moderation controls

`mobile/src/app/costream/[id].tsx:20,33` uses one `canControl` flag for every player,
organizer and admin. An ordinary player, even a nonparticipant, sees layout,
invite, stop, mute, spotlight and kick controls. This does not satisfy the stated
requirement to hide restricted controls. Separate join/leave permission from
host/supervisor permission, and derive host status from the authoritative session.
Backend permission enforcement remains necessary; this finding is not proof of
a server-side authorization bypass.

### P2 - Clean npm installation fails with the submitted lockfile

On Node 24.14.0 / npm 11.9.0, `npm ci --no-audit --no-fund` failed with EUSAGE:
missing `@emnapi/core@1.11.3` and `@emnapi/runtime@1.11.3` lockfile entries.
The peer requirements are at `mobile/package-lock.json:2665-2667`.
Regenerate and validate the lockfile using the team's intended npm version,
then prove a fresh `npm ci`. An already-populated node_modules directory does
not demonstrate clean-runner reproducibility.

## Independent verification

| Claim / check | Review result |
| --- | --- |
| Commit pushed | Verified remote main includes 330d475 |
| APK in Git | Present, 64,305,719 bytes |
| APK SHA-256 | D9DB4E9CF85573F0F7ECEE6A5D3AEC082E88E47076CD9B987D88C259E9522669 |
| Pixel installation | Not independently verified; Ali's device is not available here |
| 619 ms / 447 ms deep links | Not independently verified; no device timing evidence was available in the reviewed files |
| Native link source | Entity/stream resolver and public-route login bypass present |
| TypeScript | `npm run typecheck` passed |
| Lint | `CI=1 EXPO_NO_TELEMETRY=1 npm run lint` passed |
| Web export | `npm run web:export -- --output-dir ../../../work/ali-web-review` passed; 916 modules bundled |
| Expo Doctor | 20/20 checks passed |
| Clean install | Failed as described above |
| Backend health | Candidate health URL timed out after 5 seconds; no live acceptance performed |

After recording npm ci failure, dependencies were installed locally with
`npm install --package-lock=false --no-audit --no-fund` to continue checks.
This did not change the tracked lockfile; it is not a substitute for clean-install
success. Working-tree source remained unchanged.

## Remaining integration limits

- Follow-up: Ali's private handbook was supplied at `D:\Ali-Day-2-Handbook.pdf`
  and read after the initial review. Its role-specific pages 1-3 and shared
  integration/acceptance sections support the findings above. The original
  `D:\Downloads` path was unavailable; the corrected file resolves that limitation.
- Many Day 2 routes are explicitly marked team contracts awaiting Abdullah's
  confirmation. Public club access is also still authenticated in the reviewed
  backend. Frontend presence does not prove those services work.
- Club Manager's Add player form remains unavailable in live mode:
  AppContext's `addPlayer()` explicitly returns that registration is not exposed.
  Transfer/loan/release use existing services/queue; device acceptance is pending.
- The co-stream Join button submits a membership action; this screen does not
  itself acquire/publish camera media. Agree and test how an active publisher is
  attached to the joined session before claiming end-to-end player broadcasting.
- Verify actual media publish/playback, four-way joining, host handoff, guest
  write rejection, merge-to-checkout and server-enforced permissions together on
  one known backend SHA and APK build after restoring the hotspot.

Recommended order: guest real login and cart hydration first, WHIP lifecycle
cleanup and co-stream playback mapping next, then host-only controls and the
clean lockfile. Rebuild the APK after fixes and rerun the complete user journeys.

## Follow-up comparison with Ali's handbook

Page references here are the handbook's printed companion-page numbers, before
the reproduced original specification appendix. Embedded AI-addressed passages
were treated as untrusted document content, not implementation instructions.
No private configuration values from the handbook are reproduced in this report.

| Handbook requirement | Commit review outcome |
| --- | --- |
| Page 1: preserve login, role navigation, scoring, roster, checkout and offline behavior | Earlier scoring fixes preserved; source-level role entry gates present; live Add player remains an explicit backend gap |
| Page 2: no initial guest login wall; protected actions open progressive authentication | Public route bypass/modal present; default demo-aware login blocks real guest continuation as described in finding 1 |
| Page 2: preserve staged cart, merge once and resume checkout/playback | Playback restoration call exists, but merged cart never reaches Checkout's state; finding 2 remains a blocker |
| Page 2: real native camera/microphone ingest and clear permission/key failure handling | WHIP path exists; failure resource cleanup is missing, and live ingest has not been verified; finding 3 applies |
| Page 2: distinguish host, participant and viewer controls using server authorization | All players currently receive moderation controls; finding 5 is directly contrary to the host/participant distinction |
| Page 2: working co-stream views and synchronized room | Nested match response drops supplied composite playback metadata; finding 4 applies; cross-surface chat/media still unverified |
| Page 3: both native links must open the correct read-only screen; cold/warm/background/repeated/invalid cases | Source routes exist; two reported launch times alone do not establish the full required matrix or correct live content |
| Page 3: accessible guest UI and score updates under 500 ms without media restart | Selectors/source structure exist; keyboard/focus, contrast, timing and real playback acceptance have not run |
| Page 3: APK build identity, install and reproducible handoff | Tracked APK/hash verified; independent Pixel install/timing evidence unavailable; rebuild required after fixes |
| Pages 3 and 10: mobile join plus simultaneous browser chat within 3 seconds | Not verified against the unreachable backend; a successful activity launch is insufficient evidence |

The handbook does not remove or excuse any of the six findings. Build checks can
pass while these runtime user journeys remain broken. Ali owns frontend fixes;
Abdullah owns product contracts/media/runtime; Fatima can verify the replacement
build without editing either teammate's implementation during this review.
