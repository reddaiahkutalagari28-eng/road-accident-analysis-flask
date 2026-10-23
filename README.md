# Road Accident Analysis System (Flask + SQLite)

## Features
- Login and session-based access control
- Dashboard with KPIs and recent incidents
- Accident entry, edit and delete
- Search and filters by keyword, location, severity, weather and dates
- Charts for severity, weather, monthly trends and top locations
- Interactive OpenStreetMap view (records need latitude and longitude)
- CSV import and export
- SQLite storage initialized automatically

## Demo sign-in
Username: `admin`
Password: `Admin@123`

This is a demo credential. Set `ADMIN_PASSWORD` before first database initialization and use a strong `SECRET_KEY` before public deployment. The initial admin is only created if the users table is empty.

## VS Code setup (Windows PowerShell)
Open this folder in VS Code, then Terminal → New Terminal:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python app.py
```

If PowerShell blocks activation, run `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`, then activate again. Open http://127.0.0.1:5000.

## Database
SQLite is stored at `instance/accidents.db`. Keep this file to preserve records. You can set `DATABASE_PATH` to use another path.

## CSV format
Required: `accident_date` (YYYY-MM-DD), `location`, `severity`.
Optional: `weather`, `latitude`, `longitude`, `description`.

## GitHub update commands
```powershell
git status
git add app.py requirements.txt README.md templates static .gitignore .env.example sample_accidents.csv
git commit -m "Build Flask road accident analysis system"
git push origin main
```

## Render deployment
1. Push the project to GitHub.
2. In https://render.com create a Web Service from the repository.
3. Build command: `pip install -r requirements.txt`
4. Start command: `gunicorn app:app`
5. Add environment variables `SECRET_KEY` (long random value), `ADMIN_PASSWORD` (strong password set before first database creation), and `FLASK_DEBUG=0`.
6. For persistent SQLite data, attach a persistent disk mounted at `/var/data` and set `DATABASE_PATH=/var/data/accidents.db`.

A cloud service's ephemeral filesystem can be cleared on redeploy/restart. Use a persistent disk or managed database for records that must persist. Chart.js and Leaflet are loaded from CDNs and need browser internet access.
