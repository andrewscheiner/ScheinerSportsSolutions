# Scheiner Sports Solutions — Test Credentials

This app uses **Emergent-managed Google OAuth** for sign-in. There are no app-managed
passwords (Google OAuth handles credentials).

## Seeded test sessions (in MongoDB, db = `sss_db`)

The following test sessions are pre-seeded by `/app/auth_testing.md` and the testing
playbook. They are NOT real Google accounts — they short-circuit the OAuth flow by
inserting a `user_sessions` row directly.

| Purpose | Email | session_token (Bearer) | Subscribed? |
|---|---|---|---|
| Non-subscriber | `test.user.nosub@example.com` | `test_session_noSub_abc` | ❌ |
| Subscriber (Pro) | `test.user.subscribed@example.com` | `test_session_withSub_xyz` | ✅ |

## Quick test URL
- Paywall: `<APP_URL>/?session_token=test_session_noSub_abc`
- Dashboard: `<APP_URL>/?session_token=test_session_withSub_xyz`
- Login: `<APP_URL>/`

## Seed command (re-run if cleaned)
See `/app/auth_testing.md`.

## RBAC / allowlist
- No role-based access. Single tier subscription gate only.
