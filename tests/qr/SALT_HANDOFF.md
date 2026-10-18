# Release blocker: Day 2 signing configuration

Current status at QR preparation: **NOT COMPLETE**. Private values are available
on Fatima's workstation, but Day 2 runtime/CI wiring and live verification are
not established. A pushed test oracle cannot configure the backend's key.

The real keys were supplied in the private handbook. A Git-ignored
`.env.day2.local` containing both exact values has now been preserved in the local
checkout. It is not a Git artifact and will not appear in a teammate's clone.
Fatima also has a private output copy for transfer to the intended teammates.
Share that configuration through the team's private channel; do not put it into
source, APKs, reports, issue comments or public logs.

## Abdullah's integration checklist

- [ ] Add an empty `DAY2_SALT=` entry to `.env.example`.
- [ ] Forward `DAY2_SALT` to API and worker in root Compose, alongside DAY1_SALT.
- [ ] Read DAY2_SALT from the runtime environment; keep it out of object repr/logs.
- [ ] Fail clearly when Day 2 signing is requested without a configured key.
- [ ] Explicitly select the Day 2 key for stream, co-stream, QR, cart merge and
  moderation signatures. `sign_record()` currently defaults to DAY1_SALT.
- [ ] Preserve Day 1 event/receipt signatures and JWT behavior using DAY1_SALT.
- [ ] Transfer the real values privately to the deployed backend runtime. A local
  `.env` file alone is insufficient unless the chosen launch mechanism loads it.
- [ ] Set repository Actions secrets `DAY1_SALT` and `DAY2_SALT` if CI uses them,
  and map them explicitly into the workflow environment and containers. Secret
  presence and environment forwarding are separate checks.
- [ ] Commit and push the non-secret wiring and tests to the integrated branch.
- [ ] Restart/rebuild the intended service and verify a real QR signature using
  Fatima's independent oracle, without fetching or printing the key through APIs.

For Compose environment blocks the required forwarding is structurally:

```yaml
environment:
  DAY1_SALT: ${DAY1_SALT}
  DAY2_SALT: ${DAY2_SALT}
```

Actual values belong in the private environment, not this YAML. An env file with
DAY2_SALT does not inject it into a container whose environment is never wired.
CI secrets also do not configure Abdullah's laptop automatically.

## Verification without revealing the key

```powershell
python tests/qr/check_salt_readiness.py --env-file .env.day2.local
```

The script reports only supplied/missing flags and static wiring checks. At
preparation it reports both private values supplied and all three Day 2 wiring
checks blocked. It does not prove CI secrets exist or that a running service
loaded the values. Do not use resolved Compose/environment dumps as public
evidence. Load DAY2_SALT privately into the QA process and run QR acceptance once
the service is available; never pass the literal key as a CLI argument.

## If Fatima's session or usage ends

The hourly checkpoint prompt names this blocker and this file. Keep the blocker
open until non-secret wiring is pushed and a deployed independent signature
passes. The local secret copy and original private handbook survive this chat;
they do not depend on the assistant recalling the value. No GitHub secret or
teammate runtime configuration has been set by this QA preparation.
