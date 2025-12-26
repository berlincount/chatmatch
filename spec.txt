# Specification Sheet: Networking Matching Web App for C3

## 1. Overview

A web application will connect participants of 39C3 with similar interests in small groups. Participants complete a form, select a topic and multiple time slots; the system automatically forms groups and notifies participants, who can then accept or decline. Minimum group size: 3, maximum: 5. Communication is by email, alternatively (if email is technically not feasible) via individual, passwordless self-service links.

***

## 2. Goals

- Automatic matching by topic and time slot for groups of 3–5 participants
- Simple participation via web form
- Email notification (alternatively: self-service link)
- Calendar integration via .ics file
- Privacy-compliant (nicknames visible only)

***

## 3. User Flow

1. **Complete Registration Form**
    - Nickname (text field, free choice)
    - Email address (validation required)
    - Topic selection (one topic per form; predefined list)
    - Date selection: Participants can indicate all their availabilities
        - Day 1 (27.12.2025): Slots 1:00pm–7:30pm, selectable every 30 minutes
        - Days 2/3 (28./29.12.): 11:00am–7:00pm, every 30 minutes
        - Day 4 (30.12.2025): 11:00am–3:00pm, every 30 minutes

**UI proposal for Availability:**
For each day, show a table or button grid with selectable time slots. Use checkboxes per slot, separate tabs for each day. “Select all slots for this day” button is recommended for ease of use.
2. **Matching Logic**
    - Immediate matching as soon as three people are available for a given slot and topic.
    - Up to 2 additional participants are added by the "first come, first served" principle (max 5 per group).
    - If more than 5 register for the same slot/topic, a new group is formed using the next available slot.
    - If several slots are indicated, the earliest available slot is chosen first for a match. Any additional slots remain for later matches until a match is made.
3. **Notification**
    - On successful match: Email with information about the topic, slot, place, and the nicknames of other participants, plus confirmation/cancellation link (HTML button and/or plaintext link).
    - The .ics calendar file is automatically generated and provided for download in the email.

**Note:** If email is not technically feasible, individual self-service links will be generated and displayed upon registration/separately; these allow participants to check their match status, download the calendar file, and confirm or cancel.
4. **Confirmation/Cancellation**
    - Link in the email or in the self-service area opens a confirmation page (accept/decline).
    - After acceptance: Download of the .ics file.
    - After cancellation:
        - The group remains active if there are ≥ 3 participants
        - The group is cancelled if there are < 3 participants (all receive an info email/link)
        - Participants who still have available slots (that haven't expired) are returned to the matching pool.
    - Deadline for cancellations is 30 minutes prior to the meeting (communicated, but not enforced technically).

***

## 4. Functional Requirements

| ID | Function | Description |
| :-- | :-- | :-- |
| F1 | Participant Registration | Web form, validation, data storage |
| F2 | Topic Selection | Single-topic selection per registration (from predefined list) |
| F3 | Availability Selection | Time slots selectable per day, visual feedback, tab/table layout per day |
| F4 | Matching Algorithm | Immediate grouping (3–5), slot prioritization, remaining slots usable, overflow handling |
| F5 | Notification | Email with all required info, accept/decline, calendar file (.ics) download/link, nicknames |
| F6 | Self-Service Fallback | (Optional) Individual links for confirmation/cancellation, status, and calendar—without email |
| F7 | Calendar File (.ics) | Generation with topic, slot, fixed location, participant nicknames, Berlin timezone |
| F8 | Group Size/Cancellation Handling | Group remains for ≥ 3, group cancellation logic for < 3, re-matching for remaining availabilities |
| F9 | Data Privacy | Only nicknames visible, emails internal, not shown to participants |
| F10 | Error Management | Group notification on failure |


***

## 5. Non-functional Requirements

- Scalable for 100–200 participants
- Web-based, responsive layout
- Time zone fixed: Europe/Berlin
- No login required
- GDPR compliant (nickname only, privacy notice in UI)

***

## 6. Example UI Concept

- **Registration \& Availability Form:**
Tabs for days, table (rows for times, checkbox for each slot) per tab.
- **Match Confirmation Page:**
Overview of scheduled meeting, accept/decline buttons, status indicator.
- **Self-Service Fallback:**
Participants receive an individual link after registration (suggested for bookmarking or QR for convenience).

***

## 7. Notes \& Risks

- If email communication is technically not feasible, the self-service link approach is a practical alternative for all status changes and calendar entries.
- Cancellation or change of a .ics calendar file already downloaded cannot be implemented technically; users are requested to remove the event manually from their personal calendar after cancelling.
    - Common workaround: You can "subscribe" to a calendar by pointing the calendar app directly to the download link of the ics file. The calendar app will then regularly download the file and keep the user's calendar in sync with the system. Adding a token to the calendar URL that is sent via email to the user, will ensure that every user receives only their own events. [Tutorial for adding an external calendar via URL in Proton Calendar](https://proton.me/support/subscribe-to-external-calendar)
- The 30-minute cancellation deadline is only communicated for organization, but not technically enforced.

