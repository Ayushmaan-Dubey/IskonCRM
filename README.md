# Flask Web App

Quick dev run instructions

1. Activate the project virtualenv (macOS / zsh):

```zsh
source .venv/bin/activate
```

2. Run the app (default port 5000):

```zsh
python main.py
```

3. If port 5000 is already in use, set a different port and run:

```zsh
export PORT=5001
python main.py
```

Troubleshooting

- If you see "ModuleNotFoundError: No module named 'flask'", make sure the venv is activated and Flask is installed in it:

```zsh
python -m pip install -r requirements.txt
```

- If the navbar toggler doesn't expand, try disabling `static/script.js` temporarily (it may throw a JS error). Open DevTools → Console to see errors.

Deploy to Render

This repo now includes a Render Blueprint in `render.yaml`.

1. Push this project to GitHub.
2. In Render, click `New +` -> `Blueprint`.
3. Select your GitHub repo.
4. Render will detect `render.yaml` and propose:
   - Web service: `temple-crm-web`
   - Postgres database: `temple-crm-db`
5. Approve the resources and deploy.

Notes

- `SECRET_KEY` is generated automatically by Render from the Blueprint.
- `DATABASE_URL` is wired automatically from the managed Postgres instance.
- Local development still uses `website/database.db` if `DATABASE_URL` is not set.
