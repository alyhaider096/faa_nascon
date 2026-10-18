# Interactive role demo checks

Enable Demo data in Settings. All demo accounts use `Nascon@26`.

1. Sign in as `organizer@nascon.test`. Home shows **Record match event**. Select the live fixture, add its configured event, return to match detail, and confirm the score and timeline changed. Select that new event and append a correction; verify the score is reversed once. Upcoming matches must reject scoring.
2. Switch accounts from Club and sign in as `manager@nascon.test`. Home shows **Manage club roster**. Add a player with a free shirt number. Transfer, loan or release a listed player; return to Club and verify that player leaves the active roster. Switch accounts and back; the changed roster persists.
3. Sign in as `player@nascon.test`. Home shows **Open creator studio**. Start/stop the demo broadcast; change layouts, mute, spotlight and remove participants. Simulate host disconnect and verify the next participant becomes the demo host. Invites cannot exceed four participants. This is explicitly a local rehearsal with no media published.
4. Sign in as `viewer@nascon.test`. Confirm management shortcuts are absent. Fixtures, standings, merchandise checkout and the demo receipt remain available.
5. Sign in as `admin@nascon.test`. Confirm scoring, roster and Creator Studio shortcuts are all available.

Demo scoring and roster updates are local simulations, never submitted as backend events. Demo fixtures and roster changes persist in device storage. The public `/web/*` player does not fall back to demo data.

Connected acceptance remains separate: real 403 guest rejection, atomic cart merge, score latency, camera publication, media composition, cross-client chat, QR state resolution and offline server synchronization require a reachable configured backend. Local static checks and successful APK compilation do not prove these contracts.
