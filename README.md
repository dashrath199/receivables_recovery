# Receivables & Collections App (receivables_recovery)

**Multi-channel collections automation for ERPNext v15** — WhatsApp/SMS reminders, escalation cadence, and dispute tracking built on top of the native Dunning DocType.

## Overview

ERPNext v15 ships with a native `Dunning` DocType that tracks overdue payments. This app builds an **active collections automation layer** on top of it:

- **Scheduled cadence engine** — daily job evaluates overdue invoices against configurable rules (1-30 / 31-60 / 61-90 / 90+ days) and triggers the appropriate action
- **Real WhatsApp & SMS sending** via Gupshup (WhatsApp Business API) and MSG91
- **Delivery webhooks** — reconcile sent vs. delivered vs. read vs. failed via provider callbacks
- **Escalation ladder** — Reminder 1 → Reminder 2 → Final Notice → Legal Referral
- **Dispute tracking** — flag disputed invoices so they're never auto-messaged
- **Promise-to-Pay tracking** — record promised payment dates and detect broken promises
- **5 reports** — Aging Bucket Summary, Promise-to-Pay Reliability, Cadence Effectiveness, Dispute Register, Message Delivery Report
- **Role-based access** — Collections Manager (full access), Sales Rep (read-only on own customers)
- **Demo data** — 5 customers, 15 invoices, 4 cadence rules, 3 templates, pre-seeded Dunning and Communication Log records

## Installation

```bash
cd ~/frappe-bench
bench get-app https://github.com/your-org/receivables_recovery
bench --site yoursite.local install-app receivables_recovery
```

### Dependencies

- ERPNext v15+
- `requests` library (included in Frappe)

## Configuration

### Site Config (do not commit real keys)

Add the following to your site's `site_config.json`:

```json
{
  "whatsapp_provider": "gupshup",
  "gupshup_api_key": "YOUR_KEY_HERE",
  "gupshup_source_number": "YOUR_APPROVED_WA_BUSINESS_NUMBER",
  "gupshup_app_name": "YOUR_APP_NAME",
  "sms_provider": "msg91",
  "msg91_auth_key": "YOUR_KEY_HERE",
  "msg91_sender_id": "YOUR_SENDER_ID"
}
```

### WhatsApp Template Approval

**Important:** WhatsApp Business API requires all outbound business-initiated templates to be pre-approved by Meta before they can be sent. This cannot be automated.

1. Create your message templates in the Gupshup dashboard (or your WhatsApp Business API provider)
2. Submit them for Meta approval (typically takes 24-48 hours)
3. Once approved, copy the template ID into the **Message Template** DocType → `whatsapp_template_id` field
4. The `variables_order` field must match the positional placeholders in the approved template exactly

The demo data includes placeholder `whatsapp_template_id` values. `send_via_gupshup` calls will fail and log errors to `Communication Log.error_log` until real approved template IDs are configured — this is expected in a demo environment.

### Webhook / Callback URLs

Register these URLs in your provider dashboards:

| Provider | Endpoint | Purpose |
|---|---|---|
| Gupshup | `https://yoursite.local/api/method/receivables_recovery.api.gupshup_webhook` | Delivery status callbacks |
| MSG91 | `https://yoursite.local/api/method/receivables_recovery.api.msg91_webhook` | SMS delivery reports |

## DocTypes

| DocType | Purpose |
|---|---|
| **Dunning** (extended) | Now has `escalation_stage`, `dispute_flag`, `dispute_reason`, `last_contact_channel`, `promised_payment_date` |
| **Customer** (extended) | `whatsapp_number`, `sms_number`, `preferred_language`, `preferred_channel` |
| **Message Template** | Multi-language, multi-channel message templates with WhatsApp template ID linking |
| **Collections Cadence Rule** | Defines what action to take based on days overdue |
| **Communication Log** | Tracks every sent message with delivery status from provider webhooks |

## Reports

1. **Aging Bucket Summary** — Query Report, 0-30 / 31-60 / 61-90 / 90+ buckets (stacked bar chart)
2. **Promise-to-Pay Reliability** — Script Report comparing promised vs. actual payment dates per customer
3. **Collections Cadence Effectiveness** — Script Report showing % resolved per escalation stage
4. **Dispute Register** — Query Report filtering disputed dunning records
5. **Message Delivery Report** — Query Report on Communication Log with Sent/Delivered/Read/Failed counts

## Roles

| Role | Permissions |
|---|---|
| **Collections Manager** | Full CRUD on all DocTypes; can change escalation stage; API config visibility |
| **Sales Rep** | Read-only on own customers' Dunning; can update `last_contact_channel` and `promised_payment_date`; cannot change `escalation_stage` |

## Workspace

Desk → Workspace → **"Receivables & Collections"** delivers:
- Shortcuts to Dunning (open only), Sales Invoice (overdue filter), all custom DocTypes
- Charts: Aging Bucket Summary (stacked bar), Cadence Effectiveness (bar), Message Delivery (donut)
- Number Cards: Total Overdue, 90+ Days Overdue, Disputed Amount, Messages Sent This Week, Failed Sends This Week

## Known Gaps (Out of Scope)

- This tooling helps chase payment; it does nothing for the underlying credit gap (factoring/invoice discounting against receivables) — that's a separate fintech/lending product
- Legal escalation stage should link out to an actual recovery/legal service, not be modeled as a DocType workflow terminus
- Real WhatsApp template approval is a manual step on Meta/Gupshup's side that cannot be automated by this app
