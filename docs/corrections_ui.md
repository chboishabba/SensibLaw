# Corrections UI

This interface provides a minimal form for submitting corrections to an in-memory ledger.

## Deployment

1. Install server dependencies:
   ```bash
   pip install fastapi uvicorn
   ```
2. Launch the API server:
   ```bash
   uvicorn src.server.ledger_api:app --reload
   ```
3. Open the UI in your browser:
   [http://localhost:8000/ui/corrections/](http://localhost:8000/ui/corrections/)

Submitting the form sends a POST request to `/ledger`, which stores the entry in memory.
