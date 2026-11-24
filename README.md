# SecureDove

An end-to-end encrypted one-on-one chat app. Messages are encrypted in the browser, so the server
only ever stores ciphertext and can't read them.

**Team Name:** FortKnoxMessanger

**Team Contact:** Daniel Colosa

**Team Members:** Daniel Colosa, Jabr Elzahiri, Juliette Cox, Ryan Prisaznuk, Baron Li, Long Mai

## Project Steps

1. Strip a plain group chat app down to accounts and chat, and fix its known security bugs.
2. Give each browser its own encryption keypair. The private key never leaves the browser; the
   server keeps a directory of public keys.
3. Encrypt every message in the browser (ECDH P-256, HKDF-SHA256, AES-256-GCM) and check its
   integrity before showing it.
4. Remove every place the server could see plaintext, and add rate limiting and login lockout.

## Startup Instructions

You need Docker and `openssl`.

1. Make the HTTPS certificate and login keys (only once):

   ```bash
   ./setup.sh
   ```

2. Start the app:

   ```bash
   docker compose up -d --build
   ```

3. Open **https://localhost** and click past the certificate warning (the certificate is
   self-signed). Use `https://localhost`, not port 8080, or you won't stay logged in.

4. To stop it, run `docker compose down`.

## Trying the Encrypted Chat

1. Open two separate browser sessions, such as a normal window and an incognito window.
2. Register a different account in each one.
3. In each window, visit `https://localhost/api/users/@me` and copy the `id`.
4. Go to `/chat`, paste the other account's id under **Private Encrypted Chat**, and click
   **Open Chat**.
5. Send messages back and forth. To see that the server only has ciphertext, run:

   ```bash
   docker compose exec mongo mongo cse418 --quiet --eval 'db.messages.find({}, {_id:0, ciphertext:1, iv:1}).forEach(printjson)'
   ```


## Security countermeasures (Milestone 4)

After our paired team's Milestone 3 attacks, we hardened SecureDove:

- 2FA secret never leaves the browser: the enrollment QR code is generated
  locally (public/js/vendor/qrcode.js); nothing is sent to an external QR service.
- Account actions are keyed on the immutable account id (JWT "sub"), not the
  username, so a renamed or replayed session can only affect its own account.
- 2FA regeneration uses a pending secret confirm: the old code keeps working
  until a code from the new secret is verified.
- Static file serving is confined to the public/ directory; path traversal
  (e.g. /public/../../etc/passwd) is rejected.
  - Usernames are unique at the database layer (unique index), closing the
  registration race that could create duplicate accounts.

Regression tests:
  python3 tests/traversal/test_traversal.py          # traversal blocked (5/5)
  python3 tests/totp_identity/test_totp_identity.py   # 2FA identity (4/4)
  node tests/qr/run-node.mjs                          # no external QR service
