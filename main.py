import os
import sys

try:
    from website import create_app
except ModuleNotFoundError as exc:
    missing_module = exc.name or "unknown dependency"
    raise SystemExit(
        f"Missing dependency: {missing_module}. "
        "Install project requirements with 'python3 -m pip install -r requirements.txt'."
    ) from exc

app = create_app()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_DEBUG', 'false').lower() in ('1', 'true', 'yes')
    app.run(debug=debug, host='0.0.0.0', port=port)
