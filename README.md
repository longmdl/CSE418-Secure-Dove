# CSE418 Secure Dove

A web app written on raw TCP sockets in Python. HTTP parsing, routing, cookies, WebSockets and JWT
auth are all done by hand in `util/`, no web framework.

It runs as four Docker containers:

- **nginx**: handles HTTPS and forwards requests
- **auth_server**: register, login, logout (the only thing that can sign login tokens)
- **myapp**: everything else
- **mongo**: the database

## Running it

You need Docker (with Compose) and `openssl`.

**1. Generate the keys and cert (only once)**

From the repo root:

```bash
./setup.sh
```

This makes the HTTPS cert in `nginx/` and the JWT keypair in `keys/`. The build fails without
them. If you see `"/keys/jwt_private.pem": not found`, you skipped this step.

Running it again makes new keys, which logs everyone out.

**2. Start it**

```bash
docker compose up --build
```

Open **https://localhost**. Your browser will warn about the certificate because it's self-signed.
Click "Advanced" and continue. (In Chrome, typing `thisisunsafe` on the warning page also works.)

**To stop it**

```bash
docker compose down       # stop
docker compose down -v    # stop and delete the database
```

## Use https://localhost, not port 8080

Port 8080 goes straight to `myapp`, but every cookie is marked `Secure`. Browsers won't save those
over plain HTTP, so you'll never stay logged in there. Always use `https://localhost`.

## What's in it

| Page | Where | What it does |
|------|-------|--------------|
| Home | `/` | Landing page |
| Register / Login | `/register`, `/login` | Make an account and log in |
| Chat | `/chat` | Send, edit and delete messages |
| Find users | `/search-users` | Search for people |
| Settings | `/settings` | Change your username or password, turn on 2FA |

### Logging in

- **Username and password.** Passwords are stored with bcrypt.
- **Password + 2FA code.** If you turned on 2FA in Settings, login also asks for the code.

A successful login sets an `auth_token` cookie holding an RS256 JWT that lasts 1 hour. Only
`auth_server` holds the private key; `myapp` only verifies.


## Running without Docker

Faster when you're editing code. Run only Mongo in Docker:

```bash
docker compose -f docker-compose.db-only.yml up -d
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 server.py
```

Then go to http://localhost:8080. Two catches:

- Don't set `DOCKER_DB`, or it will look for Mongo at the wrong host.
- The code reads the JWT keys from `/root/keys/`, which only exists inside the container, so
  anything that needs login won't work locally unless you change those paths
  (`util/auth.py`, `auth/auth_controller.py`).

## Where things are

```
server.py        main app and its route list
auth_server.py   auth server (register/login/logout)
setup.sh         makes the cert and JWT keys
util/            HTTP, WebSocket, JWT and database helpers
controller/      request handlers
service/         app logic
repository/      database queries
auth/            auth server handler and Dockerfile
public/          HTML, JS, images
nginx/           nginx config
keys/            generated JWT keys (not committed)
docs/            deliverables and the sprint backlog
```

To add a route, add a line in `server.py` and a handler in the right controller.

## Problems

- **Build says `jwt_private.pem` or `cert.pem` not found.** Run `./setup.sh` from the repo root.
- **Browser says the connection isn't private.** That's the self-signed cert. Continue anyway.
- **I log in and get logged right back out.** You're on port 8080. Use `https://localhost`.
- **My code changes aren't showing up.** The code is copied into the image, so rebuild with
  `docker compose up --build`.
- **The app can't connect to Mongo.** Try `docker compose down -v` and then
  `docker compose up --build`.

Don't commit `keys/` or the files in `nginx/` that `setup.sh` creates. They're already in
`.gitignore`.
