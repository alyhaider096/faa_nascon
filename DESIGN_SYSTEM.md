# Mobile design language

LeagueOps uses a restrained dark interface: ink background, one mint action color, warm gold only for secondary highlights, and red only for errors. There is no decorative gradient, generated mascot, or copied sports-app artwork. Until the team supplies a real tenant logo, the app uses a simple in-app letter badge as a clearly temporary identity. Its launcher and splash assets are reproducible typography drawn by `mobile/scripts/generate-brand-assets.ps1`, not AI imagery.

## Product references

- [Sofascore's official app listing](https://play.google.com/store/apps/details?id=com.sofascore.results): matches, scores, results, and standings are the primary information; the LeagueOps match screen likewise leads with the score and puts events immediately below it.
- [TeamSnap's member toolkit](https://www.teamsnap.com/teams/member-toolkit): schedules and rosters are obvious task areas; LeagueOps keeps Fixtures and Club as first-level navigation and exposes manager controls from the club screen.
- [Android accessibility guidance](https://developer.android.com/guide/topics/ui/accessibility/views/apps-views): interactive areas should be at least 48 dp; LeagueOps buttons, fields, sync bar and navigation targets aim for that size.

These are interaction references, not templates to copy. All layouts, copy, mock teams and app branding are original to this project.

## Rules

| Element | Rule |
| --- | --- |
| Main navigation | Four labeled tabs: Fixtures, Standings, Store, Club. Role-only controls appear inside relevant details, not as tabs for everyone. |
| Screen hierarchy | Page title → key score/status or action → detail list → optional secondary information. |
| Color | `#071522` background, `#102439` surface, `#F4F8FC` main text, `#A9BAC9` secondary text, `#8EE6C2` primary action. Status always has a text label as well as color. |
| Shape and spacing | 11–13 dp corner radius, 16–20 dp outer spacing, compact cards, no decorative hero blocks that crowd 360×640 dp. |
| Type | 29 dp page heading, 16–18 dp body/section labels, large 39 dp match score. Avoid small text for essential information. |
| Feedback | Persistent Online/Offline/Syncing bar, pending count, explicit payment confirmation, clear server errors, visible rejected-action reasons. |
| Empty states | State what is empty and what to do next; never render a blank page. |

## Brand replacement

When the backend tenant API provides `name`, `logo_url`, and theme colors, replace the mock tenant values in `mobile/src/theme.ts` and the code badge in `mobile/src/components/UI.tsx`. Do not embed a third-party logo without the team owning its rights.
