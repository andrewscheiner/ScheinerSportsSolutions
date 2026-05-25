# Scheiner Sports Solutions — Auth Testing Playbook

This app uses Emergent-managed Google OAuth. The Streamlit app at `/` is auth-gated
and subscription-gated via FastAPI at `/api`.

## How to bypass OAuth for automated testing

1. Insert a test user + session_token directly into MongoDB:

```bash
mongosh --eval "
use('sss_db');
var userId = 'test-user-' + Date.now();
var sessionToken = 'test_session_' + Date.now();
db.users.insertOne({
  user_id: userId,
  email: 'test.user.' + Date.now() + '@example.com',
  name: 'Test User',
  picture: 'https://via.placeholder.com/150',
  created_at: new Date()
});
db.user_sessions.insertOne({
  user_id: userId,
  session_token: sessionToken,
  expires_at: new Date(Date.now() + 7*24*60*60*1000),
  created_at: new Date()
});
print('Session token: ' + sessionToken);
print('User ID: ' + userId);
"
```

2. Activate subscription for the test user (optional, to skip paywall):
```bash
mongosh --eval "
use('sss_db');
db.subscriptions.insertOne({
  user_id: 'YOUR_USER_ID',
  status: 'active',
  current_period_start: new Date(),
  current_period_end: new Date(Date.now() + 30*24*60*60*1000)
});
"
```

3. Test the backend APIs:
```bash
BASE=https://253ad5b4-47ea-4f2c-b013-088e23901dc9.preview.emergentagent.com
TOKEN=YOUR_SESSION_TOKEN

curl -s "$BASE/api/auth/me" -H "Authorization: Bearer $TOKEN"
curl -s "$BASE/api/subscription/plan"
curl -s -X POST "$BASE/api/subscription/checkout" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"origin_url":"'"$BASE"'"}'
```

4. To test the gated dashboard in a browser, append the token as a query param:
```
https://253ad5b4-47ea-4f2c-b013-088e23901dc9.preview.emergentagent.com/?session_token=YOUR_SESSION_TOKEN
```

## Key endpoints
- `GET  /api/health` — service health
- `POST /api/auth/session` — body `{"session_id": "..."}` (Emergent OAuth fragment exchange)
- `GET  /api/auth/me` — header `Authorization: Bearer <session_token>`
- `POST /api/auth/logout` — header `Authorization: Bearer <session_token>`
- `GET  /api/subscription/plan` — public
- `POST /api/subscription/checkout` — auth required, body `{"origin_url": "..."}`
- `GET  /api/subscription/status/{checkout_session_id}` — auth required, polled by frontend
- `POST /api/webhook/stripe` — Stripe webhook

## DB collections
- `users` (`user_id`, `email`, `name`, `picture`, `created_at`)
- `user_sessions` (`user_id`, `session_token`, `expires_at`, `created_at`)
- `subscriptions` (`user_id`, `status`, `current_period_start`, `current_period_end`)
- `payment_transactions` (`user_id`, `session_id`, `amount`, `currency`, `payment_status`, ...)

## Success criteria
- ✅ Unauthenticated visit shows the gold/green login screen with "Sign in with Google".
- ✅ With a valid `session_token` query param but no subscription → paywall screen with Stripe button.
- ✅ With a valid `session_token` + active subscription → dashboard with 8 tool cards.
- ✅ Webhook idempotently activates subscription.
