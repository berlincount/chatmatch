# ChatMatch — Project Status Report

**Date:** 28 Oct 2026 · **Audience:** project owner / PM (you wrote `spec.md`, so this maps directly onto it) · **Scope:** where the current code stands versus the spec. Technical internals are translated to plain language; a short glossary is at the end.

---

## 1. Bottom line

- **The core idea works.** Someone can sign up, pick a topic and available times, and once three people share a slot the app automatically forms a group (up to five) and emails them each other's nicknames. The privacy requirement (nicknames only, no visible email addresses) is fully met.
- **It cannot be used "as-is" right now.** The calendar of meeting times is hard-coded in the program for **27–30 December 2025 — a date that has already passed**. Because past meeting times are deliberately ignored, the app would form **zero** matches until its schedule is updated. This is the single biggest blocker to any live use.
- **The participant-facing experience is incomplete** against your spec: there are **no accept/decline links in emails**, **no calendar (.ics) file**, and a cancellation can only happen by re-filling the whole form — there is no self-service "my meetings" page.
- **A few safety/operations gaps** need decisions: one un-protected web address that forces a re-match of everyone *and* mass-emails them, an organizer view that doesn't actually exist yet, and a dependency on the server's clock being set to Berlin time.

---

## 2. How ChatMatch works today (plain version)

The app is one self-contained website: a single web form and a small database file. No logins or accounts (as your spec intended). The flow:

1. **Sign up** — a person enters a nickname, their email, picks **one topic**, and ticks any number of 30-minute time slots across the four days.
2. **Saved** — each ticked slot becomes a "I'm available here" entry for that person. Submitting again with a box *unticked* removes it (that is also the only way to cancel).
3. **Auto-matching** — at the moment three people share a topic + slot, the app groups them and fills up to five first-come-first-served. It re-checks each time someone submits.
4. **Notify** — matched people get a plain-text email with the topic, one meeting time, and the list of nicknames in their group.
5. **Privacy** — only nicknames are ever shown; emails stay internal and there is a GDPR note on every page.

It runs as a small container (Docker) and stores data in a lightweight file database — comfortable for your 100–200 person target, single-server, not designed to be scaled out across many machines.

---

## 3. Status versus your spec (`spec.md`, features F1–F10)

| # | Feature (your spec) | Status | Gaps / notes |
| :-- | :-- | :-: | :-- |
| F1 | Registration form (nickname, email, topic, availability) | ✅ Done | Single page, no account. Email address is only validated as a valid *format*, not that it's real. |
| F2 | One topic per registration from a fixed list | ✅ Done | 6 real topics are pre-loaded (e.g. "Poly with (planned) kids", "Jealousy", "Cohabitation"…) plus a hidden "Default". One topic per form, as specified. |
| F3 | Availability selection (per-day tabs + "select all" suggested) | 🟡 Partial | Works as one checkbox table across all four days for the chosen topic — usable, but **not** the per-day tabs / select-all you proposed, so it's less comfortable with many slots. The available-time list is also pinned to a default topic internally (harmless today because every topic shows the same times). |
| F4 | Auto-match groups of 3–5; overflow into next slot | 🟡 Partial | "Group starts at 3, fills to 5 first-come-first-served" **works**. **Missing:** your rule that a *seventh/further* person at the same slot should spawn a new group at the next slot. Currently any person beyond five simply **waits indefinitely** and only matches if someone later cancels. Past meeting times are (correctly) never matched. |
| F5 | Email with topic, time, nicknames + confirm/cancel | 🟡 Partial | A plain-text email goes out on match with the topic, one meeting time, and all group nicknames. **Missing:** no accept/decline link in the mail, no calendar attachment, only *one* slot shown (and a bug where the wrong time can be reported when several groups form at once), and the meeting **place is only loosely referenced** ("at the assembly") with no concrete room/address. |
| F6 | Self-service links (optional fallback) | ❌ Not started | Marked optional in your spec, so acceptable to defer. Each person *does* get a private key generated, but there's no self-service page using it — so there's currently **no easy way to see status or cancel** apart from re-submitting the whole form with the same nickname and email. |
| F7 | Calendar (.ics) file / subscription link | ❌ Not started | **No calendar file is produced at all.** Participants have no way to add the meeting to their phone/work calendar — only to read the email. This was your suggested "subscribe by URL" idea too; it isn't implemented. |
| F8 | Cancellation & group-size handling (keep ≥3, cancel <3, return pool) | 🟡 Partial | A confirmed group **stays** active while three or more remain — and a confirmed match is never re-sent. **Missing:** when a group drops below three there is **no automatic "your meeting is cancelled" notice**, and leftover availability is only re-considered if someone submits again — there is no continuous automatic re-matching in the background. |
| F9 | Privacy (nicknames only, emails internal) | ✅ Done | Met. Nicknames only are visible; email addresses are never shown to participants; GDPR text on every page. |
| F10 | Notify a group when a match fails | ❌ Not started | There is no message of any kind when a group fails or falls below the minimum. |

**Non-functional requirements:** responsive layout ✅ (Bootstrap, works on phones). No login ✅. Target 100–200 users ✅ *in terms of size*, with a caveat in §5. **Timezone Europe/Berlin — at risk** (see §5, item 4). GDPR compliance mostly ✅.

---

## 4. What's solid (no action needed)

- End-to-end flow is demonstrable locally: sign up → auto-match → email fires once three gather.
- A built-in **"debug" mode suppresses emails**, so the whole app can be tested on a machine with no mail server configured.
- **Privacy requirement fully met.**
- Reproducible build: every commit to `main` automatically builds and publishes a container image (to GitHub's registry), so packaging is reliable and repeatable.

---

## 5. Risks & decisions needed from you

1. **The schedule points at the past — it is a blocker now.** The built-in meeting times are hard-coded for 27–30 Dec 2025, which has already happened, so a live run today would match nothing. *(a)* When is the next target event? *(b)* Should dates/times be editable configuration instead of baked into code? — this decides whether each new event is a one-line setting or a code change + rebuild.
2. **The participant experience has no confirm/decline and no calendar.** Even when matches *do* form, people can't accept via a link and get no .ics to put in their calendars — two of the things you explicitly asked for (F5, F7). This is the biggest remaining user-facing gap.
3. **Overflow beyond five is unhandled.** More than five people wanting one slot leaves the extras unmatched forever (they never spill to the next slot). Decide: implement the "next available slot" rule from your spec, or consciously accept a hard cap of one group per slot.
4. **Timezone relies on the server clock.** All times are only correct if the machine hosting the app is set to **Europe/Berlin**. If it's hosted elsewhere, emails and meeting times shift and "past/future" logic misbehaves. Also note: the repo defines how to *build* the image but not *where/what actually runs it* — worth confirming the hosting so we can pin the timezone correctly.
5. **An un-protected, powerful endpoint exists.** There is a web address that forces a re-match of **everyone** and mass-emails them, with **no login or password**. It's also the only "organizer tool" — because no real admin view exists yet. At minimum this needs protection; ideally we build a simple organizer dashboard (view groups, safely re-match).
6. **Nothing guards the matching logic.** There are no automated tests, and CI publishes an image on every push with no test step. For a time-critical event that's a reliability risk: a careless change could break matching without anything catching it.
7. **Scale ceiling is fine but single-box.** Good for ≤200 on one instance; the database does not tolerate many machines writing at once, so keep it single-instance (or we add safeguards if you expect more).

---

## 6. Suggested next steps (prioritized)

1. **Confirm the next event date and make the schedule configurable** — unblocks *everything* else. *(Blocker)*
2. **Wire up real email + add accept/decline links and an .ics attachment** to the match email. *(Highest user value)*
3. **Lock down operations:** password-protect (or properly build) the organizer/re-match function; confirm hosting + Berlin timezone.
4. **Decide and implement the overflow rule** for >5 people on one slot (or document the cap).
5. **Add a self-service page** (uses the existing per-person key) for status, cancel, and calendar download — makes cancellation robust without depending on people re-filling the form. *(Your optional F6)*
6. **Add a small automated test around the matching logic + a CI test step** before publishing images.
7. **Group-failure messaging** (F10) and the below-minimum "your meeting was cancelled" notice (F8) once the above are in place.

---

### Small glossary

- **Container / Docker:** a self-contained package of the app and everything it needs to run; makes deployment portable and repeatable.
- **.ics / calendar subscription:** a standard file/link that lets a phone or work calendar add (or keep in sync) an event automatically.
- **SMTP / mail server:** the service the app hands emails to for delivery; must be configured with real credentials before actual emails will send.
- **CI / GitHub Actions:** the automated pipeline that builds and publishes the container image on every change to `main`.

*Prepared from a direct review of the current code against `spec.md`; no code was changed by this report.*
