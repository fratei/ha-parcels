# Parcels

A Home Assistant integration that tracks your parcels from your shipping
e-mails. It reads Outlook.com and Gmail mailboxes with read-only access, keeps
each parcel once, shows the week's deliveries on a Parcels page and, on
delivery day, puts them on your iPhones as Live Activities and in a persistent
notification in Home Assistant.

Everything runs in Home Assistant. Parcels has no server of its own: it talks
to Microsoft or Google with an app you register yourself, and, only if you
turn them on, to 17TRACK through Home Assistant's 17TRACK integration and to a
local AI model on your Home Assistant host.

- [What it does](#what-it-does)
- [Privacy and safety](#privacy-and-safety)
- [Requirements](#requirements)
- [Install](#install)
- [Set up](#set-up)
- [Options](#options)
- [The Parcels page](#the-parcels-page)
- [Delivery day](#delivery-day)
- [17TRACK](#17track)
- [Local AI](#local-ai)
- [Entities, actions and events](#entities-actions-and-events)
- [Troubleshooting](#troubleshooting)
- [Development](#development)

## What it does

- **Mailboxes**: personal Microsoft accounts (Outlook.com, Hotmail, Live) and
  Gmail, signed in from Home Assistant with OAuth. Add as many as you like.
- **Senders it understands**: Amazon (amazon.es, .com, .co.uk, .de, .fr, .it
  and .nl), Shopify stores, Shop, and the carriers CTT and CTT Expresso, DPD,
  GLS, SEUR, UPS, DHL, Correos Express, MRW, Nacex, Paack, and InPost and
  Vinted Go. In other e-mails a generic detector finds tracking numbers, and
  checks the check digit of UPS (`1Z…`) and postal (`AB123456785PT`) numbers.
- **Languages**: Portuguese, Spanish, English, German, French, Italian and
  Dutch. Delivery dates such as "amanhã, entre as 13:00 e as 14:00" or
  "übermorgen" are read relative to the day the e-mail was sent.
- **Each parcel once**: e-mails about the same order or shipment are merged,
  also across mailboxes, so a parcel appears once however many e-mails you
  get. An order e-mail creates a provisional parcel that the shipping e-mail
  later completes, also when the carrier's e-mail names only the shop. A
  later e-mail about the same order and items updates that order's parcel,
  and a delivery or return e-mail without items updates the order's only open
  parcel. An e-mail that arrives late never moves a parcel back to an earlier
  status. Merges that rely on a guess (same shop, matching dates, only one
  candidate) are marked, and you can undo them. A guess counts only when no
  other open parcel of that shop could be the one, late parcels and those due
  in the next days included, and when the carriers named by the shop and the
  delivery agree. When several parcels could match, Parcels asks in **Needs
  review** instead. Parcels with different tracking numbers are never merged.
- **Parcels without a tracking number**: when a carrier delivers another
  parcel from the same shop around the expected day, and no e-mail says
  otherwise, the parcel is marked as probably delivered, unless that delivery
  belongs to another order or another carrier. You can undo that.
  One with no news a week after its expected day is archived.
- **Parcels that went quiet**: carriers' e-mails and 17TRACK miss some
  deliveries. A parcel with a tracking number that's on its way, with no news
  from e-mails or 17TRACK for three weeks, counted from its last expected day
  when that's later, is marked as probably delivered, on its last expected
  day if it has one. You can undo that or keep it, and news about the parcel
  takes it back.
- **Shipments of several packages**: packages sent together that arrive on the
  same day share one box, which says how many packages it holds. The details
  list every package with its tracking number. Packages that arrive on
  different days get a box each.
- **Shop and carrier apart**: shops such as Amazon often hand their parcels to
  a local carrier. A carrier's e-mail joins the shop's parcel when they share a
  tracking number or an order number, and the details then show the shop and
  who delivers it ("Delivered by"). Until an e-mail names the carrier, or the
  tracking number's format gives it away, the parcel says "Carrier not known
  yet".
- **Paack**: Paack's order IDs, nine letters and digits, `_` and the package
  number (such as `Ab3Cd4Ef5_1`), are kept as written, capitals included. A
  Paack e-mail joins Amazon's parcel when the part of its ID before `_` is,
  letter for letter, the shipment ID in Amazon's **Track package** link, or
  when both give the same label barcode (`5340` and 14 digits), which Amazon
  shows as its tracking ID. Otherwise the usual guesses apply. Paack's
  tracking page asks for the order ID and your postcode, so the carrier link
  opens its search page. Parcels never keeps the postcode, e-mail address or
  phone number in Paack's links, and doesn't add Paack's numbers to
  [17TRACK](#17track), which can't follow them without the postcode.
- **Delivery PINs**: delivery PINs, one-time codes and pickup codes found in
  e-mails are shown on the parcel's box until it's delivered, and in its
  details (see [Privacy and safety](#privacy-and-safety)).
- **A Parcels page** with a Monday-to-Sunday calendar of your deliveries, the
  parcels that don't have a date yet, and the e-mails Parcels wasn't sure
  about.
- **On delivery day**: Live Activities on iPhones, a notification on iPads and
  Android phones, and a persistent notification in Home Assistant.
- **Optional integrations**, both off until you set them up:
  - [17TRACK](#17track), through Home Assistant's 17TRACK integration: the
    carrier's status between e-mails, such as in transit, out for delivery or
    delivered. It adds no delivery dates.
  - A [local AI](#local-ai) model on your Home Assistant host: it reads the
    e-mails no parser understands and fills in what a parser missed.

## Privacy and safety

- **Read-only access.** Outlook.com: the Microsoft Graph permissions
  `Mail.Read` and `User.Read` (plus `offline_access` to stay signed in).
  Gmail: `gmail.readonly`. Parcels can't send, change or delete e-mail.
- **Your own app.** You register the OAuth app in your own Microsoft or Google
  account, so no third party holds a token for your mailbox. Home Assistant
  stores the tokens in its configuration.
- **E-mails aren't kept.** Parcels downloads e-mails that look like shipping
  e-mails, reads them in memory and keeps only what it found (shop, carrier,
  tracking number, dates, status) plus a hash of each e-mail's ID, so it never
  reads one twice. E-mail bodies are never stored or logged.
- **No remote content.** Images, tracking pixels and links in e-mails are
  never loaded. Tracking links are built from each carrier's public URL
  pattern.
- **Verified senders.** Parcels checks the `Authentication-Results` header
  that Microsoft or Google adds: an e-mail counts as coming from Amazon, a
  carrier or a shop only when DKIM or DMARC passes for that sender's domain.
  Gmail's header must be the topmost one. An Outlook.com e-mail must carry
  exactly one, since Microsoft renames those that arrive with the e-mail; one
  with more waits for review, because a sender could have written the others.
  E-mails from other senders never create a parcel on their own; they wait for
  your review on the Parcels page, where you can trust or ignore the sender.
- **Local AI only.** The AI fallback is off by default. Parcels only accepts an
  AI task of the Ollama integration whose model runs on the Home Assistant
  host, and refuses cloud models and remote hosts.
- **Lock screen.** Live Activities and notifications show the shop, carrier,
  status and time window, never item names unless you turn that on. A parcel
  marked private notifies only its owner and is only counted in the shared
  persistent notification.
- **Delivery PINs** are shown only on the Parcels page, to the people who can
  see the parcel: on its box until it's delivered, returned or cancelled, in
  its details, and to administrators in the e-mails waiting for review. They
  never appear in entity states or attributes, the recorder, events, logs,
  diagnostics, notifications or Live Activities. Parcels hides a PIN once
  its parcel is delivered, returned or cancelled, and deletes it at the
  nightly cleanup or when the parcel is archived. A delivery that Parcels only
  inferred keeps its PIN in the details until the parcel is archived, in case
  it hasn't arrived.
- **17TRACK** gets tracking numbers only, under a generic name, never item
  names, shops or the numbers of private parcels.
- **Revoking access.** Delete the mailbox entry in Home Assistant, then remove
  the app in your
  [Microsoft account](https://account.live.com/consent/Manage) or
  [Google account](https://myaccount.google.com/connections). Deleting the
  client secret or the app registration also ends access for every mailbox
  that uses it.

Turn on multi-factor authentication for Home Assistant administrators.
Backups include the mailbox tokens: keep them encrypted, and store the backup
encryption key somewhere safe.

## Requirements

- Home Assistant 2026.11 or later.
- An Outlook.com, Hotmail or Live mailbox, or a Gmail mailbox. Work and school
  Microsoft 365 accounts aren't supported.
- For Live Activities: an iPhone with iOS 17.2 or later and the Home Assistant
  companion app, and remote access to Home Assistant (Home Assistant Cloud or
  your own): the app and Home Assistant exchange the tokens that start and
  update activities, also when you're away from home.
- For the local AI: Home Assistant OS, which runs the Ollama app.
- For 17TRACK: a free [17track.net](https://www.17track.net/) account whose
  password has 16 characters or fewer, and Home Assistant's 17TRACK
  integration.

## Install

Parcels isn't in the Marketplace catalog, so you add it from its link:

1. In Home Assistant, go to **Settings > Marketplace** and select **Add from
   link** in the upper-right corner. If you haven't connected GitHub yet, the
   Marketplace asks you to; custom repositories need that connection.
2. Under **GitHub link**, enter `fratei/ha-parcels` and select **Add**. If it
   asks for the type, choose **Integration**.
3. Open **Parcels** in the list and select **Install**. If Home Assistant asks
   you to restart, in a repair under **Settings > System > Repairs**, restart
   it.

## Set up

### 1. Register an app with Microsoft (Outlook.com)

Registering an app needs a Microsoft Entra directory. If you only have a
personal account, sign up for Azure with it, which creates one; app
registrations cost nothing.

1. Open
   [App registrations](https://portal.azure.com/#view/Microsoft_AAD_RegisteredApps/ApplicationsListBlade)
   in the Azure portal and select **New registration**.
2. Name it, for example "Parcels", and under **Supported account types**
   choose **Personal Microsoft accounts only**.
3. Under **Redirect URI**, choose **Web** and enter
   `https://my.home-assistant.io/redirect/oauth`.
4. In **Certificates & secrets**, create a client secret and copy its
   **Value**. A secret lasts at most 24 months: set a reminder to replace it.
5. In **API permissions**, add the delegated **Microsoft Graph** permissions
   `Mail.Read`, `User.Read` and `offline_access`.
6. Copy the **Application (client) ID** from the **Overview**.

### 2. Register an app with Google (Gmail)

1. In the [Google Cloud console](https://console.cloud.google.com/), create a
   project and enable the
   [Gmail API](https://console.cloud.google.com/apis/library/gmail.googleapis.com).
2. Set up the **Google Auth Platform** (the OAuth consent screen) with the
   audience **External**, and under **Data Access** add the scope
   `https://www.googleapis.com/auth/gmail.readonly`.
3. Google requires an application home page and a privacy policy link before
   you can publish. Under **Branding**, use the values from Home Assistant's
   own [Nest instructions](https://www.home-assistant.io/integrations/nest/)
   and select **Save**:
   - Under **App domain**, enter `https://www.home-assistant.io` as the
     **Application home page** and `https://www.home-assistant.io/privacy` as
     the **Application privacy policy link**.
   - Under **Authorized domains**, add `home-assistant.io`. This also covers
     `www.home-assistant.io` and the redirect URI on `my.home-assistant.io`.
   - Leave the **Application terms of service link** and the **App logo**
     empty, to avoid triggering Google's verification.
4. Under **Clients**, create an OAuth client of type **Web application** with
   the authorized redirect URI `https://my.home-assistant.io/redirect/oauth`,
   and copy its client ID and secret.
5. Publish the app, or Google signs Parcels out every 7 days: under
   **Audience**, select **Publish app**. Google notes that the app needs
   verification; select **Confirm** without submitting it for verification,
   and don't select **Verify branding** either. Your own use needs neither.
   The status changes to **In production**. When you sign in, Google says it
   hasn't verified the app; select **Advanced** and continue.

If Google reports a problem:

- **Branding shows "Issues found from the previous verification attempt".**
  The list under **View issues**, such as "The website of the home page URL is
  not registered to you", comes from Google's optional brand verification.
  That check can't pass with `home-assistant.io`, and personal use doesn't
  need it. As
  [Google's Branding help](https://support.google.com/cloud/answer/15549049)
  says, "Without verification, only your application domain will be visible
  to users." Never select **Verify branding**, **Request re-verification** or
  **Request additional review**. If a verification is in progress, select
  **Cancel** first: Google blocks Branding changes while it runs. The "not
  registered to you" item may stay listed; it's harmless.
- **The Verification Center says the app needs verification.** That's because
  of the `gmail.readonly` scope. An app for personal use, with fewer than 100
  users, may stay unverified, as
  [Google explains](https://support.google.com/cloud/answer/13464323).
- **Sign-in stops at "Access blocked … Error 403: access_denied".** Check
  that **Audience** says **In production**. While the app is in **Testing**,
  only the accounts listed under **Test users** can sign in.

### 3. Add the application credentials

Go to **Settings > Devices & services**, open the ⋮ menu, choose
**Application credentials** and add the credentials for **Parcels**: one for
Microsoft and one for Google, as needed. Parcels tells them apart by the
client ID: a GUID is Microsoft, an ID ending in `.apps.googleusercontent.com`
is Google.

### 4. Add Parcels

Go to **Settings > Devices & services > Add integration > Parcels**. The first
time, this creates the hub entry, **Parcels**, which holds your parcels,
notifications and options.

### 5. Add your mailboxes

Add **Parcels** again for each mailbox: pick the credentials of its provider
and sign in. Each mailbox becomes an entry named after its address. Each
person can sign in to their own mailbox. The first sync
reads the last 30 days of e-mail; after that Parcels checks every 5 minutes.
In each mailbox's options, set its **Owner** (see [Options](#options)).

When a sign-in expires or is revoked, Home Assistant asks you to sign in again
with the same account.

### 6. Create the Parcels page

See [The Parcels page](#the-parcels-page). Then, to get delivery day on your
phones, choose the people to notify in the hub's options and follow
[Delivery day](#delivery-day).

### 7. Optional: 17TRACK and the local AI

- **17TRACK**, for the carrier's status between e-mails: create a free account
  at [17track.net](https://www.17track.net/) and add Home Assistant's
  **17TRACK** integration. **Live status from 17TRACK** is on by default in the
  Parcels options, so Parcels starts using it within 30 minutes, or at once
  when you run the `parcels.refresh` action. See [17TRACK](#17track) for what
  it sends and the limits of a free account.
- **Local AI**, for e-mails no parser understands: install the Ollama app and
  pick its AI task in the Parcels options. See [Local AI](#local-ai).

## Options

Open **Settings > Devices & services > Parcels** and select the cog of an
entry.

### Hub (the Parcels entry)

| Option | Default | What it does |
| --- | --- | --- |
| People to notify | none | The companion app devices of these people get Live Activities and notifications. |
| Excluded devices | none | Devices that never get them, such as a shared tablet. |
| Start time | 08:00 | Live Activities for parcels expected today start at this time. |
| Cut-off time | 22:00 | Remaining Live Activities end at this time. |
| Combine Live Activities above | 3 | With more parcels than this on one day, they share one Live Activity. |
| Show item names on the lock screen | off | When off, the lock screen shows shop, carrier, status and time window only. |
| Live status from 17TRACK | on | Has effect only when the 17TRACK integration is set up. See [17TRACK](#17track). |
| Test mode and Test device | off | Send Live Activities to the test device only. |
| Archive delivered parcels after | 14 days | Archived parcels stay visible in past weeks. |
| Delete delivered parcels after | 90 days | Must be more than the archive period. |
| Local AI task | none | See [Local AI](#local-ai). |
| AI mode | Suggest | Off, Suggest (review every result) or Automatic (known or trusted senders). |

### Mailbox

| Option | Default | What it does |
| --- | --- | --- |
| Owner | none | The person the mailbox belongs to. Their private parcels notify only their devices. |
| Folders to read | Inbox and Junk Email | Outlook.com only. Gmail reads all mail except the trash. |
| Check for new e-mail every | 5 minutes | |
| First sync reads back | 30 days | |

## The Parcels page

Parcels comes with three cards. They load automatically; you don't need to
add a resource.

- **Parcels week** (`custom:parcels-week-card`): a Monday-to-Sunday calendar
  with the week's deliveries. Each box has three lines: the shop; the carrier
  with the time window, package count and PIN; and the items, such as
  "3 items · Lamp, Bin, Mat". Date ranges are drawn as bars and colored by
  status, delivered parcels show ✓ on their delivery day, and parcels found
  by the AI carry an "AI" badge until you confirm them. Packages of one
  shipment that arrive on the same day share a box with a package count.
  Above the week you can show **All** parcels, the **Active** ones (not
  delivered, returned or cancelled), the **Recent** ones (changed or expected
  this week) or the **Completed** ones. Each device remembers the choice, and
  **Parcels without a date** follows it too.
  Select a parcel for its timeline, carrier and carrier link, tracking
  number, the shipment's other packages, pickup point, PIN or pickup code and
  parcel ID, and to mark it delivered, edit it, make it private, merge, split
  or archive it. Merges and deliveries that Parcels guessed are marked there,
  to keep or undo. **Merge** lists the likely matches first (same order or
  shop, still open, close dates), each with its items, order number, carrier,
  tracking number, status and date; older parcels are behind **Show older**
  and the search. For administrators, when a carrier's e-mails don't say
  which of a shop's parcels it's delivering, the box says "Possibly: …" with
  the candidates' items, and the details list them, to merge or rule out with
  one tap. The card also adds parcels by tracking number. Options: `title`
  (an empty string hides it) and `show_archived` (default `true`).
- **Parcels without a date** (`custom:parcels-list-card`): active parcels that
  don't have a delivery date yet. Option: `title`.
- **Parcels review** (`custom:parcels-review-card`): **Needs review** lists the
  e-mails Parcels wasn't sure about, with what it found filled in, to accept,
  edit, dismiss, or trust or ignore the sender. It also lists parcels that may
  be the same one, to merge or keep apart. While e-mails wait for the local AI,
  it says how many and, after the AI's first answer, about how long they'll
  take. **Filtered** lists e-mails that looked like shipping e-mails but
  turned out not to be about a parcel; you can move them back, or clear one or
  all of them. A cleared e-mail isn't read again. Items leave the list as soon
  as you act on them, and come back with the error if the action fails.
  Option: `title`.

Delivery notifications open `/dashboard-parcels/week`. To make them land on
your page, go to **Settings > Dashboards > Add dashboard > New dashboard from
scratch**, name it **Parcels** with the icon `mdi:package-variant-closed`, and
keep the URL `dashboard-parcels`. Open it, choose **Edit dashboard > ⋮ > Raw
configuration editor** and paste:

```yaml
views:
  - title: Week
    path: week
    icon: mdi:calendar-week
    type: sections
    max_columns: 4
    sections:
      - type: grid
        column_span: 4
        cards:
          - type: tile
            entity: sensor.parcels_arriving_today
          - type: tile
            entity: sensor.parcels_in_transit
          - type: tile
            entity: sensor.parcels_ready_for_pickup
          - type: tile
            entity: sensor.parcels_delivered_today
          - type: custom:parcels-week-card
            grid_options:
              columns: full
      - type: grid
        column_span: 2
        cards:
          - type: custom:parcels-list-card
            grid_options:
              columns: full
      - type: grid
        column_span: 2
        cards:
          - type: custom:parcels-review-card
            grid_options:
              columns: full
```

For a month view, add Home Assistant's own calendar card with
`calendar.parcels`. It has no week grid, which is why Parcels brings its own.

Parcels marked private show only to their owner. The review list's actions
need an administrator.

### Trusted and ignored senders

Parcels knows Amazon, Shop, Shopify stores and the carriers above. Their
e-mails are added straight away when DKIM or DMARC passes. An e-mail with
parcel details from any other sender waits in **Needs review**; one with
nothing parcel-like goes to **Filtered**, or is skipped when its sender isn't
authenticated. In **Needs review** you can:

- **Trust the sender**, for a shop that e-mails you itself: its e-mails are
  then treated like a known sender's, and those waiting in review are read
  again. When the e-mail failed the sender checks, Parcels first asks you to
  confirm, since anyone can send e-mail that claims a domain. It then adds
  that sender's e-mails waiting in review, as you have seen them. Later
  e-mails that fail the checks still wait in review, marked as from a trusted
  sender. **Sender check details** on such an e-mail show how many
  authentication headers it had and which servers wrote them, with no
  addresses.
- **Ignore the sender**: Parcels stops reading its e-mails and drops those
  waiting in review.

Both apply to the whole domain, so `mail.shop.example` counts as
`shop.example`. Trusting an ignored sender stops ignoring it, and the other
way round. Free mail domains such as gmail.com can't be trusted or ignored.
Administrators can also use the `parcels.trust_sender` and
`parcels.ignore_sender` actions.

## Delivery day

### Live Activities

[Live Activities](https://companion.home-assistant.io/docs/notifications/live-activities/)
put a parcel on the iPhone's lock screen and in the Dynamic Island, and update
it as the carrier sends news. With watchOS 11 or later, a paired Apple Watch
shows them in its Smart Stack.

To get them:

1. Update the Home Assistant companion app on each iPhone. In the iPhone's
   **Settings > Home Assistant**, allow **Live Activities**, and accept the
   app's one-time prompt when the first one arrives.
2. In the hub options, choose the **People to notify**. Their iPhones get Live
   Activities; their iPads and Android phones get one notification per parcel
   that's replaced on each key change (out for delivery, ready for pickup,
   delivered, delivery attempted, problem).
3. Optional: run the **Test Live Activity** action (see
   [Actions](#actions)) to check an iPhone. The demo ends after a minute.

How they behave:

- At the start time (08:00), each parcel expected today starts an activity:
  one with a single-day date, on the last day of its date range, or announced
  for today. Later in the day a parcel starts one as soon as it's out for
  delivery or ready for pickup.
- With more parcels than the threshold (3) on one iPhone, they share one
  activity, such as "2 of 5 delivered · next: DPD 13–14h", for the rest of the
  day.
- Updates are sent only when something changes, and silently unless the
  status changed. A time window shows a countdown.
- A delivered parcel shows "Delivered ✓" with the time, and its activity ends
  30 minutes later.
- Apple ends activities after 8 hours, so an undelivered parcel's activity is
  restarted after 7.5 hours. The new activity plays the start alert once,
  because iOS doesn't let a new activity start silently.
- At the cut-off (22:00) the remaining activities end. Undelivered parcels stay
  in the persistent notification.
- Apple limits how often activities can start remotely, so a parcel starts
  about once per iPhone and day. Parcels remembers what it sent, so a restart
  of Home Assistant neither ends nor duplicates an activity.

The **Live Activities** switch turns all of this off and on. Turning on **Test
mode** sends them to the **Test device** only, which is useful for the first
days.

### The persistent notification

From the start time until the next morning, a persistent notification in Home
Assistant (`parcels_today`) lists the day's parcels with their shop, carrier,
status and time window, and links to the Parcels page. Packages of one shipment
with the same status share a line, with their count ("4 packages"); delivered
ones keep their own line, with the time. Private parcels are only counted.
Parcels ready for pickup stay in it for up to a week. The **Daily
notification** switch turns it off and on.

## 17TRACK

Optional. Carriers e-mail the main steps only; 17TRACK follows the carrier's
own tracking in between.

- **What it adds**: the carrier's status between e-mails, such as in transit,
  out for delivery, delivered, a failed attempt or ready for pickup, with the
  carrier's own wording in the parcel's history.
- **What it doesn't add**: delivery dates. Home Assistant's 17TRACK integration
  gives no expected date, so a parcel without one stays under **No date yet**.
- **What it leaves out**, so they don't take up places in your account:
  - Amazon Logistics numbers, which 17TRACK can't follow;
  - Paack's numbers, and GLS's when Home Assistant's country is Portugal.
    17TRACK follows them only with the recipient's postcode
    ([17TRACK's list](https://res.17track.net/asset/carrier/info/additional_parameters.json)),
    and Home Assistant's 17TRACK integration sends only the number, so they
    would stay "Not Found";
  - the numbers of parcels without news for three weeks. 17TRACK's
    [API documentation](https://api.17track.net/en/doc?version=v2.4) says
    tracking stops after 30 days without carrier events.
- **What it sends**: tracking numbers only, each under a generic name such as
  `parcels-1a2b3c`. Never item names, shops, or the numbers of private
  parcels, because every Home Assistant user can see the 17TRACK packages.

To set it up:

1. Create an account at [17track.net](https://www.17track.net/). Home
   Assistant's integration only accepts passwords of 16 characters or fewer.
2. Add Home Assistant's **17TRACK** integration.
3. Keep **Live status from 17TRACK** on in the Parcels options. It's on by
   default.

Parcels adds the numbers of active parcels to your 17TRACK account, the
parcels due soonest first and up to 10 at a time, reads their status every 30
minutes (every 10 while one is out for delivery or due that day) and archives
them there once the parcel is done or without news for three weeks, when it's
a number 17TRACK can't follow (added by an earlier version), or when 17TRACK
still can't find a number after two weeks. Numbers you added to 17TRACK
yourself are read but never archived.

**Limits of a free account.** 17TRACK gives free members a tracking quota of
40 numbers, and paid plans 100 or 200
([17TRACK app user manual](https://help.17track.net/hc/en-us/articles/360020938192-17TRACK-APP-user-manual),
[pricing](https://buyer.17track.net/en/pricing)). By 17TRACK's quota rules,
you can add as many numbers as the quota minus the numbers being tracked;
adding or reactivating a number uses quota, and archiving or deleting one
frees it. In practice a free account follows at most 40 numbers at once,
including the ones you add yourself, and Parcels frees its own as parcels are
done.

When the account is full, 17TRACK refuses new numbers, and Parcels can't tell
that refusal from others. It tries a refused number again after 6 and 12
hours, then once a day while its parcel is active, so the number gets in once
a place frees up. The hub's diagnostics show how many numbers are waiting
(`failed`), the last error, with 17TRACK's code when it gives one, and how
many numbers 17TRACK can't find, by carrier (`not_found_by_carrier`).

17TRACK also sells a tracking API for developers, with its own free
allowance. That's a different product, and Parcels doesn't use it.

## Local AI

Some e-mails don't match any parser: a new shop, an unusual carrier e-mail.
Parcels can ask a local model to read them. The model runs on your Home
Assistant host through Ollama; e-mails never leave your network.

1. Install Ollama on the Home Assistant host; apps need Home Assistant OS. The
   [Ollama app](https://github.com/fratei/ha-apps) is a minimal app built from
   Ollama's official image: go to **Settings > Apps > App store**, open the ⋮
   menu, choose **Repositories** and add `https://github.com/fratei/ha-apps`.
   Install **Ollama**, turn on **Start on boot** and **Watchdog**, start it, and
   note the **hostname** on its **Info** tab.
2. Add Home Assistant's **Ollama** integration with the URL
   `http://<hostname>:11434` and no API key. Use the app's hostname, not your
   host's IP address: Parcels only accepts an Ollama server on `localhost` or
   on the apps' internal network.
3. On the Ollama entry, select **Add AI task** and choose the model
   `qwen3:4b-instruct`, a context window of 8192, keep alive 300 and thinking
   off. Home Assistant downloads the model, about 2.5 GB. Set keep alive
   explicitly: the default keeps the model in memory all the time.
4. In the Parcels hub options, choose the AI task as **Local AI task** and the
   **AI mode**:
   - **Suggest** (default): every AI result waits in **Needs review**, marked
     "AI", for you to accept or correct.
   - **Automatic**: results from known or trusted senders that pass every
     check are added straight away, still marked "AI" until you confirm them;
     the rest go to review.

Parcels only sends e-mails from senders whose DKIM or DMARC passes, one at a
time and newest first.

**Filling in what a parser missed**: when a parser reads an e-mail but leaves
out the delivery date, the items, or a shipping e-mail's tracking number or
carrier, Parcels asks the AI for those details only, after the e-mails no
parser read and for up to 20 e-mails a day. The parser's values always stay.
In Suggest mode the details wait in **Needs review** as "The local AI found
details the parser missed"; accept them to add them to the parcel. In
Automatic mode they're added straight away, and the parcel shows "AI" until
you confirm them in its details.

**Check again**: an open parcel without a date has a **Check again** button in
its details, for administrators. Parcels downloads the parcel's newest e-mails
again (up to 5), reads them with the current parsers and asks the AI for what's
still missing, even past the 20 a day. The parcel stays on the page meanwhile,
and the details say what happened. Once, after updating from 0.1.3 or earlier,
Parcels does this by itself when the first mail check ends, for open parcels
that lack a date or items (within the 20 a day). It also reads again the
e-mails held for review with "Authentication results from an unknown server".

**What the AI sees**: the day the e-mail arrived, the sender's name and
domain, the subject and the text a reader sees (text the HTML hides is left
out), with each link reduced to its domain and the numbers in it (or in the
link it forwards to), up to 6,000 characters. It never sees your address, the
other headers, images or attachments. Parcels calls the AI task directly, not
through an action, so the e-mail isn't written to the recorder. Home Assistant
keeps the conversation in memory for up to 10 minutes, where administrators can
watch it, and Parcels removes the e-mail text from the debug and error logs of
the Ollama, AI task and conversation integrations.

Parcels checks every answer: tracking numbers must appear in the e-mail as
written and match their carrier's format, check digit included where there is
one, and dates must fall between 2 days before and 60 days after the e-mail.
A number the model miscopied by one character becomes the e-mail's own when
exactly one number in it is that close, and so does an order number given as
only a part of a hyphen- or slash-joined number. Parcels' own tracking number
detector always runs as well. The kind, the delivery date, the merchant and
the pickup point are checked against the e-mail's own wording: a date to
collect, pay or return by is never taken as a delivery date, and when the
e-mail's words give a kind, a kind they don't support is replaced by it.
[docs/ai-benchmark.md](docs/ai-benchmark.md) lists the checks.

Limits: 5 minutes per e-mail, one retry, 50 e-mails a day, and only the last
14 days during a mailbox's first sync. An e-mail whose retry fails as well
goes to **Needs review**, marked "The local AI took too long on this e-mail"
when the last try ran out of time; so do e-mails still waiting after a day.
Every list and text in an answer has a length cap well above real values, so
an answer that runs away stops at the cap. On a typical Home Assistant host's
CPU, a short e-mail takes several seconds, and a long one about a minute. The
review card shows how many e-mails are waiting and about how long they'll
take, from the average time of the last 14 days' calls.

In Suggest mode, Parcels also gives the AI up to 5 e-mails a day that a parser
already read, and counts how often the two agree; those answers are never
used. The hub's diagnostics show the counts for the last 14 days, a guide
before you choose Automatic.

Parcels refuses an AI task that isn't Ollama, whose Ollama URL isn't the Home
Assistant host, or whose model is a cloud model, and raises a repair issue
instead. After restoring a backup, check the AI task's settings again.

[docs/ai-benchmark.md](docs/ai-benchmark.md) explains how to measure a model
with made-up e-mails before you rely on it.

## Entities, actions and events

### Entities

| Entity | What it shows |
| --- | --- |
| `binary_sensor.parcels_delivery_today` | On when a parcel is expected today. |
| `sensor.parcels_arriving_today` | Parcels expected today. |
| `sensor.parcels_in_transit` | Parcels on their way. |
| `sensor.parcels_ready_for_pickup` | Parcels waiting at a pickup point or locker. |
| `sensor.parcels_delivered_today` | Parcels delivered today. |
| `sensor.parcels_ai_queue` | E-mails waiting for the local AI. |
| `calendar.parcels` | Expected and actual deliveries. |
| `switch.parcels_live_activities` | Live Activities and phone notifications. |
| `switch.parcels_daily_notification` | The persistent notification. |

The count sensors have a `parcels` attribute with each parcel's ID, shop,
carrier, status and dates. Each mailbox has a **Last sync** sensor and a
**Problem** sensor.

### Actions

| Action | What it does |
| --- | --- |
| `parcels.add` | Adds a parcel by tracking number and returns its ID. |
| `parcels.update` | Corrects a parcel's details, confirms what the AI found, or keeps an automatic merge or inferred delivery. |
| `parcels.mark_delivered` | Marks a parcel delivered now. |
| `parcels.archive` | Archives a parcel. |
| `parcels.merge` | Merges parcels that are the same delivery. |
| `parcels.split` | Moves e-mails or entries of a parcel to a new parcel. |
| `parcels.undo_merge` | Splits a parcel that Parcels merged automatically. |
| `parcels.undo_delivery` | Takes back a delivery that Parcels inferred, from another parcel of the same shop or from three weeks without news, and doesn't infer it again. |
| `parcels.refresh` | Checks all mailboxes, and 17TRACK when it's on, now. |
| `parcels.reprocess` | Reads a parcel's or review item's e-mails again with the current parsers, optionally with the AI. Administrators only. |
| `parcels.trust_sender` | Trusts a sender's domain, so its e-mails are read as shipping e-mails. Administrators only. |
| `parcels.ignore_sender` | Stops reading a sender's e-mails. Administrators only. |
| `parcels.test_live_activity` | Sends a one-minute demo Live Activity to an iPhone. Administrators only. |

### Events

`parcels_parcel_added`, `parcels_status_changed` (with `previous_status`) and
`parcels_delivered` carry `parcel_id`, `status`, `carrier`, `eta_start`,
`eta_end`, `private` and `owners`, and for shared parcels also `merchant` and
`tracking_number`. They never carry item names. For example:

```yaml
triggers:
  - trigger: event
    event_type: parcels_delivered
actions:
  - action: persistent_notification.create
    data:
      message: "{{ trigger.event.data.merchant or 'A parcel' }} was delivered."
```

## Troubleshooting

- **A shipping e-mail is missing.** Check **Needs review** and **Filtered** on
  the Parcels page. If the sender isn't known, trust it there, or run
  `parcels.reprocess`.
- **A parcel shows twice.** Check **Needs review** for a merge suggestion, or
  select the parcel and merge it. Packages of one shipment that arrive on
  different days have a box each.
- **A delivery PIN is missing.** Parcels doesn't read the e-mails it read
  before version 0.1.2 again by itself. Select the parcel, copy its
  **Parcel ID** from the details, and run `parcels.reprocess` with that
  `parcel_id`.
- **A parcel shows as delivered but hasn't arrived.** If its details say the
  delivery was inferred, select **Undo**. A parcel without news for three
  weeks shows as delivered on its last expected day, in a past week.
- **Paack's e-mails wait in review.** Earlier versions couldn't read Paack's
  order IDs. After the update, Parcels reads once more the Paack e-mails whose
  local AI reading was rejected, and adds the ones it now understands. Accept
  the others in **Needs review**, where Paack's order IDs can be typed as
  written.
- **A Paack parcel shows apart from its Amazon parcel.** Select one and merge
  them. The hub's diagnostics count Paack's e-mails whose order ID matched an
  Amazon shipment, and those that didn't (`paack_amazon`), without any ID.
- **Repair: "Shipping e-mails from … aren't understood".** A known sender
  changed its e-mails. The e-mails wait in review; check for an update of
  Parcels.
- **Repair: "The local AI isn't available"** or **"The chosen AI task isn't
  local".** Check that the Ollama app and integration are running, and that
  the chosen AI task is an Ollama task on this host.
- **A mailbox needs to sign in again.** Its client secret may have expired
  (Microsoft) or the app may still be in testing (Google).
- **No Live Activity.** Check the iPhone's Live Activities setting for the
  Home Assistant app, remote access, the **Live Activities** switch, test mode
  and the people to notify, then try `parcels.test_live_activity`.
- **Diagnostics.** **Download diagnostics** on the hub or a mailbox gives
  counts and states, without addresses, tokens or parcel details.

## Development

```bash
python3.14 -m venv .venv
.venv/bin/pip install -r requirements_test.txt
.venv/bin/ruff check . && .venv/bin/ruff format --check .
.venv/bin/pytest -q

cd frontend
npm ci && npm run typecheck && npm run lint && npm test && npm run build
```

The cards' sources are in `frontend/`; `npm run build` writes the bundle in
`custom_components/parcels/frontend/`, which is committed. Test e-mails in
`tests/fixtures` are made up. Put real e-mails for local tests only in
`fixtures-private/`, which git ignores.

## License

[MIT](LICENSE)
