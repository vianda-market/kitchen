# Backend feedback: Local mobile development (LAN access)

**Purpose:** Enable B2C and B2B developers to test on physical devices or from multiple terminals against a local backend. The B2C frontend provides a toggle (`npm run dev:mobile` vs `npm run dev:mobile:local`) so developers choose LAN vs localhost based on network trust. This document describes backend requirements for LAN mode to work.

**Audience:** Backend team, B2C mobile, B2B web (kitchen-web).

---

## 1. Backend run scripts: Trusted vs untrusted network

The backend provides two run scripts at the project root. Choose based on where you are:

| Command | Binding | Use case |
|---------|---------|----------|
| `./run_dev_trusted.sh` | `0.0.0.0` (all interfaces) | Trusted network (home, office). Physical device testing. |
| `./run_dev_untrusted.sh` | `127.0.0.1` (localhost only, uvicorn default) | Untrusted network (plane, cafe, airport). Same as `uvicorn application:app --reload`. |

**CLI commands:**

Trusted network (LAN access for phones, tablets):

```bash
./run_dev_trusted.sh
# or:
uvicorn application:app --host 0.0.0.0 --reload
```

Untrusted network (localhost only – baseline):

```bash
./run_dev_untrusted.sh
# or (uvicorn defaults to 127.0.0.1:8000):
uvicorn application:app --reload
```

The scripts source `venv` or `.venv` if present. Run from the project root.

---

## 2. Required: Bind to all interfaces (for LAN mode)

When B2C developers run `npm run dev:mobile` on a trusted network, their phone loads the app via Expo and makes API requests to the developer's laptop. The backend must listen on **all interfaces** (not just 127.0.0.1) so devices on the same LAN can reach it.

**Action:** Use `./run_dev_trusted.sh` or run uvicorn with `--host 0.0.0.0`:

```bash
uvicorn application:app --host 0.0.0.0 --reload
```

---

## 3. Required: CORS for local development

The frontend runs on various origins during development:

- `http://localhost` (and common Expo ports: 8081, 19006, etc.)
- `http://<LAN_IP>:*` when the app is served from the developer's machine and accessed from a phone

**Action:** Allow these origins in development. Options:

- Add `http://localhost` and common dev ports (e.g. `http://localhost:8081`, `http://localhost:19006`)
- Use env-based relaxed CORS in development (e.g. `allow_origins=["*"]` or pattern match when `DEBUG=true`)
- Optionally allow `http://<LAN_IP>:` patterns for dev

**Recommendation:** Make CORS environment-aware: strict origins in production, permissive only in dev.

---

## 4. Frontend toggle (for context)

The B2C app provides two commands:

| Command | Mode | Use case |
|---------|------|----------|
| `npm run dev:mobile` | LAN – API URL = `http://<LAN_IP>:8000` | Trusted network (home, office). Physical device testing. |
| `npm run dev:mobile:local` | Localhost – API URL = `http://localhost:8000` | Untrusted network (plane, cafe). Use simulator/web only. |

Backend binding to 0.0.0.0 is only needed when developers use `dev:mobile` (LAN) on trusted networks. When they use `dev:mobile:local`, the app talks to localhost and no LAN exposure occurs.

---

## 5. Multi-terminal setup (trusted local network)

When testing both B2C and B2B on a trusted network, use separate terminals:

| Terminal | Command | Notes |
|----------|---------|-------|
| 1 | `./run_dev_trusted.sh` | Backend – binds to 0.0.0.0 |
| 2 | `npm run dev:mobile` | B2C mobile – API URL = `http://<LAN_IP>:8000` |
| 3 | `npm run dev` | B2B web – API URL = `http://localhost:8000` (or `http://<LAN_IP>:8000` if testing from another device) |

**B2B (kitchen-web) local setup:** See [LOCAL_NETWORK_DEV.md](../b2b_client/LOCAL_NETWORK_DEV.md) for API base URL configuration and LAN IP usage.

---

## 6. Security note

Binding to 0.0.0.0 makes the backend reachable from any device on the same network. Developers should use `./run_dev_trusted.sh` and `dev:mobile` only on trusted networks. On shared WiFi (plane, cafe, airport), use `./run_dev_untrusted.sh` and `dev:mobile:local` to avoid exposing the dev backend.
