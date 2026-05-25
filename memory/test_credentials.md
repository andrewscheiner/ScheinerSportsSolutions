# Scheiner Sports Solutions — Test Credentials

This app uses **Emergent-managed Google OAuth** for sign-in. There are no app-managed
passwords (Google OAuth handles credentials).

## Seeded test sessions (in MongoDB, db = `sss_db`)

| Purpose | Email | session_token (Bearer) | Plan |
|---|---|---|---|
| Non-subscriber | `test.user.nosub@example.com` | `test_session_noSub_abc` | — |
| Monthly subscriber | `test.user.subscribed@example.com` | `test_session_withSub_xyz` | `monthly` ($1.99/mo) |
| Lifetime subscriber | `test.user.lifetime@example.com` | `test_session_lifetime_lf1` | `lifetime` ($20 once) |

## Quick test URLs
- Free dashboard (5 tools available, 3 locked): `<APP_URL>/?session_token=test_session_noSub_abc`
- Monthly subscriber (all 8 tools): `<APP_URL>/?session_token=test_session_withSub_xyz`
- Lifetime subscriber (all 8 tools): `<APP_URL>/?session_token=test_session_lifetime_lf1`
- Generic login: `<APP_URL>/`

## Seed command (re-run if cleaned)
See `/app/auth_testing.md`. Lifetime seed example:
```js
db.users.insertOne({user_id:"test-user-lifetime", email:"test.user.lifetime@example.com", name:"Test Lifetime", picture:"https://via.placeholder.com/100", created_at:new Date()});
db.user_sessions.insertOne({user_id:"test-user-lifetime", session_token:"test_session_lifetime_lf1", expires_at:new Date(Date.now()+7*86400000), created_at:new Date()});
db.subscriptions.insertOne({user_id:"test-user-lifetime", status:"active", plan_type:"lifetime", current_period_start:new Date(), current_period_end:null});
```

## RBAC / allowlist
- No role-based access.
- Three Pro tools paywalled: NRFI Report, NBA Daily Insights, Slump Detector.
- Five free tools (no auth required beyond Google sign-in): NBA Betting Systems, Laddering Tool, Tango Tracker, NFL Power Rankings, MLB Reverse RYP.
