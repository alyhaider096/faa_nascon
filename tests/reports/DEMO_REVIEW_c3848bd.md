# Ali's interactive demo role review

Reviewed remote-main commit `c3848bd` on 18 October 2026. The advertised local
demo actions are largely implemented, with three reproducible state defects.
No application source was edited during this review.

## Findings to fix

1. **Roster identity collision:** `AppContext.tsx` adds demo players without IDs,
   then uses `(player.id ?? player.name)` for selection/removal. Add two players
   called Alex with different free shirt numbers, then transfer either Alex:
   both disappear. Give every added demo player a stable unique ID and persist it.
2. **Invalid layout:** DemoStudio accepts `grid_2` with four active participants.
   A rehearsal should reject that choice or clearly show the effective layout
   that can contain all participants. The backend contract must still enforce
   capacity in connected mode.
3. **Empty session stays active:** start the demo broadcast, then disconnect all
   hosts one by one. The final state has zero participants but still says demo
   broadcast active. Sole-host termination should stop the demo and clear stale
   mute/spotlight/layout state as appropriate.

## What was checked

| Advertised role behavior | Review result |
| --- | --- |
| Organizer scoring | Actual demo callback changed live score from 2:1 to 3:1; source appends timeline entry and persists demo fixtures |
| Organizer correction | Actual callback reversed new goal to 2:1 and rejected a second correction of that goal |
| Manager add | Actual add callback accepted new players with free shirt numbers; unique-ID defect above remains |
| Manager transfer/loan/release | Each actual callback removed the selected existing roster member and rejected disallowed roles |
| Player studio | Component handlers changed local start, mute, spotlight and first host-handoff state; layout/terminal-state defects above remain |
| Viewer shop/receipt | Actual checkout callback created a demo receipt with the expected total and cleared its cart |
| Viewer restrictions | Demo score/roster callbacks rejected viewer; source hides management shortcuts |
| Admin | Demo callbacks permit score/roster; source exposes scoring, roster and Creator Studio entry points |
| TypeScript / lint | Both passed independently after this commit |

The tests execute the current TypeScript callbacks and DemoStudio handlers with
in-memory storage and hook/network substitutes. They do not constitute browser,
Pixel, camera, live-backend, or persistence-after-process-restart acceptance.
The source writes `demo_fixtures`/`demo_club`, and demo login reads them back;
actual device persistence should still be checked after reinstall/force-close.

## Relationship to the handbook and earlier review

The demo is explicitly labeled local rehearsal/no media published, and its
documentation correctly separates connected acceptance. That is appropriate
for practicing role differences while the backend is unreachable. It cannot
satisfy the handbook's real ingest, guest 403, cart merge, live QR, latency,
host-handoff media continuity or cross-device chat requirements.

This commit does not change the earlier GuestExperience, WHIP cleanup, co-stream
response mapping, live co-stream permission controls or dependency lockfile.
The previous connected-mode review therefore remains open. Fixing the demo does
not resolve the fresh guest JWT/cart-continuation problems or prove that the
rebuilt APK's connected paths work.

Suggested handoff to Ali: keep the interactive demo, assign stable demo player
IDs, enforce a valid effective layout, and end an empty session. Then finish the
separate connected-mode fixes and provide a new identified APK for device QA.
