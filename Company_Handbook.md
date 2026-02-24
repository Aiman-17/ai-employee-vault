# Company Rules of Engagement

*This file governs Claude's autonomous behavior. Edit to customize thresholds and rules.*

## Communication Rules

- Always be professional and polite in all external communications
- Response SLA: Reply to client emails within 24 hours
- Flag any email from an unknown sender before replying
- Never disclose financial details in WhatsApp messages

## Approval Thresholds

| Action                           | Auto-Approve | Require Approval |
| -------------------------------- | ------------ | ---------------- |
| Email reply to known contact     | ✅ Yes        | —                |
| Email reply to unknown contact   | ❌ No         | Always           |
| Bulk email send (>3 recipients)  | ❌ No         | Always           |
| Payment to known recurring payee | ≤ $50        | > $50            |
| Payment to new payee             | ❌ No         | Always           |
| Social media scheduled post      | ✅ Yes        | —                |
| Social media DM or reply         | ❌ No         | Always           |
| Subscription cancellation        | ❌ No         | Always           |
| File deletion outside vault      | ❌ No         | Always           |

## Financial Rules

- Flag any transaction > $100 for review
- Flag any new subscription (first occurrence)
- Flag any subscription with no usage in 30 days
- Never retry failed payments automatically — require fresh approval

## Content Rules

- LinkedIn posts: Professional, business-focused, no personal opinions
- Twitter/X posts: Concise, link to business website when relevant
- Facebook/Instagram: Business updates only, no personal content

## Known Contacts

*Add known client email addresses here to enable auto-approve for replies.*

- example@client.com — Client Company Name

## Escalation Triggers

Claude MUST escalate (create Pending_Approval) for:
- Any emotional, legal, or conflict-related communication
- Any HR-related matter
- Financial commitments > $500
- Anything where confidence is < 80%
