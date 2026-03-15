# How to Start the FastAPI Server

## Quick Start

1. **Navigate to the project directory:**
   ```bash
   cd /Users/cdeachaval/Desktop/local/kitchen
   ```

2. **Activate the virtual environment:**
   ```bash
   source venv/bin/activate
   ```

3. **Start the server:** Run one of these (not both):

   ```bash
   # Baseline (localhost only) or untrusted networks:
   uvicorn application:app --reload
   ```

   For trusted networks (home, office) where you need LAN access (e.g. physical device testing), use instead:
   ```bash
   ./run_dev_trusted.sh
   ```

   The run script replaces the uvicorn command; it starts the server with the right binding. See [feedback_for_backend_local_mobile_dev.md](../api/b2c_client/feedback_for_backend_local_mobile_dev.md).

## What You'll See

The server will start and you'll see output like:
```
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
INFO:     Started reloader process [xxxxx] using WatchFiles
INFO:     Started server process [xxxxx]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
```

## Viewing Logs

- **All logs** (including errors) will appear in this terminal
- **Error messages** will show the full traceback
- **API requests** will be logged automatically
- **Application logs** (from `log_info`, `log_error`, etc.) will appear here

## Stopping the Server

Press `CTRL+C` in the terminal to stop the server.

## Troubleshooting

If you see import errors or module not found:
- Make sure the virtual environment is activated (you should see `(venv)` in your prompt)
- Verify you're in the correct directory: `/Users/cdeachaval/Desktop/local/kitchen`

## Testing the Enriched Endpoint

Once the server is running, you can test the endpoint:
```bash
# Get a valid token first (from your Postman collection or login endpoint)
curl -X GET "http://localhost:8000/plate-pickup/enriched" \
  -H "Authorization: Bearer YOUR_TOKEN_HERE"
```

Any errors will appear directly in the terminal where the server is running.

