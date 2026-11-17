# Parcels cards

The Lovelace cards of the Parcels integration, written in TypeScript with
[Lit](https://lit.dev) 3. esbuild bundles them into
`custom_components/parcels/frontend/parcels-cards.js`. That file is committed:
the integration serves it at `/parcels_static/parcels-cards.js` and loads it on
every dashboard, so you don't add any dashboard resources.

## Cards

| Card | Options | Shows |
| --- | --- | --- |
| `custom:parcels-week-card` | `title`, `show_archived` (default `true`) | A Monday to Sunday calendar of deliveries, with details, actions and "Add parcel". |
| `custom:parcels-list-card` | `title` | Active parcels that don't have a delivery date yet. |
| `custom:parcels-review-card` | `title` | E-mails that need a decision ("Needs review") and the e-mails filtered out ("Filtered"). Only administrators see it. |

```yaml
type: custom:parcels-week-card
title: Deliveries      # "" hides the title
show_archived: false
```

The cards share one `parcels/subscribe` WebSocket subscription per connection.
They make no other network requests and load no fonts, images or scripts from
elsewhere. All English text is in `src/strings.ts`, ready to be translated.

## Development

Node 24 or later. Run these from this folder:

```sh
npm ci             # install the pinned dependencies
npm run typecheck  # tsc --noEmit (strict)
npm test           # node --test, unit tests of the pure logic in src/
npm run build      # writes ../custom_components/parcels/frontend/parcels-cards.js
```

Commit the rebuilt bundle with your source changes. CI builds it again and
fails if the committed file differs. The build is deterministic, so the same
sources always produce the same bytes.

The tests run the TypeScript sources directly through Node's type stripping.
That is why the code uses only erasable syntax (no enums, namespaces,
parameter properties or decorators) and imports with `.ts` extensions.
