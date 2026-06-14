# Auth: Invert Registration Flow (Redis-first, no ghost accounts)

**Priority:** Before production

**Problem:** The current registration creates a `User` row in PostgreSQL immediately with `status=pending_verification`, before the user has proven they own the email/phone. OTPs expire in Redis but the DB row lives forever. This causes:
- Ghost accounts that permanently "occupy" an email/phone
- Users who abandon OTP verification get stuck — can't verify (OTP expired), can't log in (account blocked), can't register (gets "account already created")
- Password mismatch when re-registering with a different password

**Fix:** Invert the flow — store registration data in Redis under the OTP key (with TTL), only create the `User` row in PostgreSQL upon successful OTP verification.

```
Current:  Register → User row created (pending_verification) → OTP in Redis (expires)
Target:   Register → OTP + payload in Redis (TTL) → Verify OTP → User row created
```

**What changes:**
- `POST /auth/register` — hash the password, store `{full_name, email, phone, password_hash, role, tenant_id}` in Redis as JSON alongside the OTP. Do NOT insert into `users` table. Return same response as today.
- `POST /auth/verify-email` and `POST /auth/verify-phone` — on OTP success, read the payload from Redis, create the User row (status=active), issue tokens, delete the Redis key.
- Duplicate check at registration still queries the `users` table (only active/suspended accounts block re-registration — no more pending_verification rows to collide with).
- The `pending_verification` enum value in `AccountStatus` can be removed, or kept for other future uses.

**Current workaround in place:** Re-registration of a pending account now updates the password + resends OTP, and login with an unverified account redirects to the verify screen. This is a patch — the Redis-first rewrite is the permanent fix.
