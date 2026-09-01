# EBL Genesis — Public Beta Infrastructure

## Required environment
- Persistent volume mounted at `/data`
- `EBL_DB_PATH=/data/ebl.db`
- `EBL_BACKUP_DIR=/data/backups`
- `PUBLIC_BASE_URL=https://<your-domain>`
- SMTP relay credentials for verified email and password recovery

## Email
The app now supports SMTP-based:
- registration verification links (60-minute expiry)
- verified-email password reset links (30-minute expiry)
- generic reset responses to avoid email-account enumeration

Use a transactional email provider/SMTP relay and configure SPF, DKIM, and DMARC for the sending domain before opening registration.

## Sessions
Sessions are stored in SQLite instead of process memory and expire after 30 days. Password reset and account suspension invalidate sessions.

## Rate limits
- registrations: 5/IP/hour
- logins: 20/IP/15 min
- password-reset requests: 8/IP/hour
- chat: 12 messages/user/minute
- DMs: 20 messages/user/minute

For larger scale, move counters to Redis or another shared rate-limit store.

## Backups
- commissioner can create an immediate SQLite backup
- automatic backup hook runs every 7 league days
- newest 30 backups are retained by the helper
- production hosting should additionally snapshot the persistent volume off-service

## Moderation
- user block/report
- commissioner report queue
- 24h or custom-duration mute/suspension infrastructure
- suspension invalidates sessions
- chat/DM posting is blocked while muted

## Before charging money
Obtain legal review of Terms/Privacy/Community Rules, add payment-provider terms/refund disclosures, and perform a dedicated security review.
