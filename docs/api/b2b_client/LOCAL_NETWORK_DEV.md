# B2B Local Network Development

**Purpose:** Enable kitchen-web (B2B) to run against a local backend. This doc supports laptop-based testing and future tablet/phone testing on the same LAN.

**Audience:** B2B frontend (kitchen-web).

---

## Backend run scripts

The Kitchen backend (this repo) provides two run scripts at the project root. Choose based on network trust:

| Script | Use when |
|--------|----------|
| `./run_dev_trusted.sh` | Trusted network (home, office) – backend binds to all interfaces |
| `./run_dev_untrusted.sh` | Untrusted network (plane, cafe, airport) – backend binds to localhost only |

On a trusted LAN, use `./run_dev_trusted.sh` so the backend is reachable from other devices if needed. On untrusted networks, use `./run_dev_untrusted.sh` (or the baseline `uvicorn application:app --reload`) to bind to localhost only.

**Full explanation:** See [feedback_for_backend_local_mobile_dev.md](../b2c_client/feedback_for_backend_local_mobile_dev.md) for trusted vs untrusted rationale and security notes.

---

## API base URL configuration

Configure your API base URL in kitchen-web based on where you run the frontend:

| Scenario | API base URL |
|---------|--------------|
| Same machine (laptop) | `http://localhost:8000` |
| Another device on LAN (e.g. tablet) | `http://<LAN_IP>:8000` |

**Obtain LAN IP:**

- **macOS:** `ipconfig getifaddr en0` (or `en1` if on Ethernet)
- **Linux:** `hostname -I \| awk '{print $1}'` or `ip addr`
- **Windows:** `ipconfig` – look for IPv4 Address under your active adapter

---

## Multi-terminal setup

When running backend and B2B frontend together on a trusted network:

1. **Terminal 1:** `./run_dev_trusted.sh` (from kitchen repo)
2. **Terminal 2:** `npm run dev` (from kitchen-web repo), with `API_URL` or equivalent set to `http://localhost:8000`

If testing kitchen-web from a different device on the LAN (e.g. tablet), set the API base URL to `http://<YOUR_LAPTOP_LAN_IP>:8000` and ensure the backend was started with `./run_dev_trusted.sh`.

---

## Note

B2B is primarily tested from a laptop browser. This doc ensures consistency with B2C local dev and supports future device testing.
