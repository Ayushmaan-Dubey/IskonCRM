# Voice quick-add agent

Talks to volunteers on the Add Newcomer page (LiveKit Cloud). Runs separately from the Flask app.

## One-time setup
1. Flask app (local `.env` and Render environment): `LIVEKIT_URL` (wss://…livekit.cloud), `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET`.
2. Install the LiveKit CLI, then from this folder: `lk cloud auth`, `lk agent create` (use the same project), and `lk agent deploy` for later updates.
   The agent uses LiveKit Inference for speech-to-text, the LLM and text-to-speech, so it needs no other API keys.
3. Open Add Newcomer while logged in, tap "Start talking".

## Local testing
`pip install -r requirements.txt`, set the same three variables, `python agent.py download-files`, then `python agent.py dev`.
