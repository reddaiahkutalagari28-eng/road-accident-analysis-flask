import csv, io, os, sqlite3
from pathlib import Path
from datetime import date
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash, abort, make_response
from werkzeug.security import generate_password_hash, check_password_hash

ROOT = Path(__file__).resolve().parent
DB_PATH = os.environ.get("DATABASE_PATH", str(ROOT / "instance" / "accidents.db"))
Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-only-change-this-secret")
SEVERITIES = ["Minor", "Moderate", "Serious", "Fatal"]
WEATHER = ["Clear", "Rain", "Fog", "Wind", "Cloudy", "Other"]

def db():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c

def init_db():
    with db() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS users(
            id INTEGER PRIMARY KEY, username TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL)""")
        c.execute("""CREATE TABLE IF NOT EXISTS accidents(
            id INTEGER PRIMARY KEY AUTOINCREMENT, accident_date TEXT NOT NULL,
            location TEXT NOT NULL, severity TEXT NOT NULL, weather TEXT NOT NULL DEFAULT 'Other',
            latitude REAL, longitude REAL, description TEXT DEFAULT '',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP, updated_at TEXT DEFAULT CURRENT_TIMESTAMP)""")
        if c.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0:
            c.execute("INSERT INTO users(username,password_hash) VALUES(?,?)",
                      ("admin", generate_password_hash(os.environ.get("ADMIN_PASSWORD", "Admin@123"))))
        if c.execute("SELECT COUNT(*) FROM accidents").fetchone()[0] == 0:
            c.executemany("""INSERT INTO accidents(accident_date,location,severity,weather,latitude,longitude,description)
                VALUES(?,?,?,?,?,?,?)""", [
                ("2026-01-12","Rajampeta Main Road","Moderate","Clear",14.195,79.159,"Two-vehicle collision near the junction."),
                ("2026-02-03","Kadapa Bypass","Serious","Rain",14.467,78.824,"Wet road surface and reduced visibility."),
                ("2026-03-19","Tirupati Highway","Minor","Clear",13.628,79.419,"Minor rear-end collision."),
                ("2026-04-08","Nellore Road Junction","Fatal","Fog",14.442,79.986,"Serious collision at an intersection."),
                ("2026-05-21","Anantapur Ring Road","Moderate","Wind",14.681,77.600,"Vehicle lost control near a curve."),
                ("2026-06-11","Kurnool Highway","Serious","Cloudy",15.828,78.037,"Motorcycle and car collision."),
            ])

def auth(view):
    @wraps(view)
    def wrapped(*a, **kw):
        if "user_id" not in session:
            flash("Please sign in to continue.", "warning")
            return redirect(url_for("login"))
        return view(*a, **kw)
    return wrapped

@app.context_processor
def shared():
    return {"username": session.get("username"), "severities": SEVERITIES, "weather_types": WEATHER, "today": date.today().isoformat()}

def get_records(args=None):
    args = args or request.args
    sql, params = "SELECT * FROM accidents WHERE 1=1", []
    q = (args.get("q") or "").strip()
    severity, weather = args.get("severity", ""), args.get("weather", "")
    start, end = args.get("date_from", ""), args.get("date_to", "")
    location = (args.get("location") or "").strip()
    if q:
        sql += " AND (location LIKE ? OR description LIKE ?)"; params += [f"%{q}%", f"%{q}%"]
    if location:
        sql += " AND location LIKE ?"; params.append(f"%{location}%")
    if severity in SEVERITIES:
        sql += " AND severity=?"; params.append(severity)
    if weather in WEATHER:
        sql += " AND weather=?"; params.append(weather)
    if start: sql += " AND accident_date>=?"; params.append(start)
    if end: sql += " AND accident_date<=?"; params.append(end)
    sql += " ORDER BY accident_date DESC, id DESC"
    with db() as c: return c.execute(sql, params).fetchall()

def parse_form(form):
    r = {k:(form.get(k) or "").strip() for k in ["accident_date","location","severity","weather","latitude","longitude","description"]}
    errors=[]
    try:
        from datetime import datetime
        datetime.strptime(r["accident_date"], "%Y-%m-%d")
    except ValueError: errors.append("Enter a valid date.")
    if not r["location"]: errors.append("Location / road name is required.")
    if r["severity"] not in SEVERITIES: errors.append("Choose a valid severity.")
    if r["weather"] not in WEATHER: errors.append("Choose a valid weather condition.")
    for key, lo, hi in [("latitude",-90,90),("longitude",-180,180)]:
        if r[key]:
            try:
                r[key]=float(r[key])
                if not lo <= r[key] <= hi: errors.append(f"{key.title()} is out of range.")
            except ValueError: errors.append(f"{key.title()} must be a number.")
        else: r[key]=None
    if (r["latitude"] is None) != (r["longitude"] is None): errors.append("Enter both coordinates or leave both blank.")
    return r, errors

@app.route("/")
def index():
    return redirect(url_for("dashboard" if session.get("user_id") else "login"))

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method=="POST":
        with db() as c: u=c.execute("SELECT * FROM users WHERE username=?",((request.form.get("username") or "").strip(),)).fetchone()
        if u and check_password_hash(u["password_hash"],request.form.get("password","")):
            session.clear(); session["user_id"]=u["id"]; session["username"]=u["username"]
            flash("Signed in successfully.","success"); return redirect(url_for("dashboard"))
        flash("Incorrect username or password.","danger")
    return render_template("login.html", page_title="Sign in")

@app.route("/logout")
@auth
def logout():
    session.clear(); flash("You have signed out.","info"); return redirect(url_for("login"))

@app.route("/dashboard")
@auth
def dashboard():
    rows=get_records()
    with db() as c:
        total=c.execute("SELECT COUNT(*) FROM accidents").fetchone()[0]
        fatal=c.execute("SELECT COUNT(*) FROM accidents WHERE severity='Fatal'").fetchone()[0]
        serious=c.execute("SELECT COUNT(*) FROM accidents WHERE severity='Serious'").fetchone()[0]
        locs=c.execute("SELECT COUNT(DISTINCT location) FROM accidents").fetchone()[0]
        recent=c.execute("SELECT * FROM accidents ORDER BY accident_date DESC,id DESC LIMIT 5").fetchall()
        sev=c.execute("SELECT severity,COUNT(*) n FROM accidents GROUP BY severity").fetchall()
        wea=c.execute("SELECT weather,COUNT(*) n FROM accidents GROUP BY weather").fetchall()
        mon=c.execute("SELECT substr(accident_date,1,7) m,COUNT(*) n FROM accidents GROUP BY m ORDER BY m").fetchall()
    charts={"sev_labels":[x["severity"] for x in sev],"sev_values":[x["n"] for x in sev],
            "weather_labels":[x["weather"] for x in wea],"weather_values":[x["n"] for x in wea],
            "month_labels":[x["m"] for x in mon],"month_values":[x["n"] for x in mon]}
    return render_template("dashboard.html",page_title="Dashboard",total=total,fatal=fatal,serious=serious,locations=locs,recent=recent,charts=charts,filtered_count=len(rows))

@app.route("/records")
@auth
def records():
    return render_template("records.html",page_title="Accident records",accidents=get_records(),filters=request.args)

@app.route("/accidents/new",methods=["GET","POST"])
@auth
def new_accident():
    r={"accident_date":date.today().isoformat(),"location":"","severity":"Minor","weather":"Clear","latitude":"","longitude":"","description":""}
    if request.method=="POST":
        r,errs=parse_form(request.form)
        if errs:
            for e in errs: flash(e,"danger")
            r["latitude"]=request.form.get("latitude","");r["longitude"]=request.form.get("longitude","")
        else:
            with db() as c:
                c.execute("INSERT INTO accidents(accident_date,location,severity,weather,latitude,longitude,description) VALUES(?,?,?,?,?,?,?)",
                          tuple(r[k] for k in ["accident_date","location","severity","weather","latitude","longitude","description"]))
            flash("Accident record added.","success");return redirect(url_for("records"))
    return render_template("accident_form.html",page_title="Add accident",accident=r,mode="new")

@app.route("/accidents/<int:rid>/edit",methods=["GET","POST"])
@auth
def edit_accident(rid):
    with db() as c: row=c.execute("SELECT * FROM accidents WHERE id=?",(rid,)).fetchone()
    if not row: abort(404)
    r=dict(row)
    if request.method=="POST":
        r,errs=parse_form(request.form)
        if errs:
            for e in errs: flash(e,"danger")
            r["id"]=rid;r["latitude"]=request.form.get("latitude","");r["longitude"]=request.form.get("longitude","")
        else:
            with db() as c:
                c.execute("""UPDATE accidents SET accident_date=?,location=?,severity=?,weather=?,latitude=?,longitude=?,description=?,updated_at=CURRENT_TIMESTAMP WHERE id=?""",
                          tuple(r[k] for k in ["accident_date","location","severity","weather","latitude","longitude","description"])+(rid,))
            flash("Accident record updated.","success");return redirect(url_for("records"))
    return render_template("accident_form.html",page_title="Edit accident",accident=r,mode="edit")

@app.route("/accidents/<int:rid>/delete",methods=["POST"])
@auth
def delete_accident(rid):
    with db() as c: c.execute("DELETE FROM accidents WHERE id=?",(rid,))
    flash("Accident record deleted.","success");return redirect(url_for("records"))

@app.route("/charts")
@auth
def charts():
    with db() as c:
        sev=c.execute("SELECT severity,COUNT(*) n FROM accidents GROUP BY severity").fetchall()
        wea=c.execute("SELECT weather,COUNT(*) n FROM accidents GROUP BY weather").fetchall()
        mon=c.execute("SELECT substr(accident_date,1,7) m,COUNT(*) n FROM accidents GROUP BY m ORDER BY m").fetchall()
        loc=c.execute("SELECT location,COUNT(*) n FROM accidents GROUP BY location ORDER BY n DESC LIMIT 10").fetchall()
    data={"sev_labels":[x["severity"] for x in sev],"sev_values":[x["n"] for x in sev],
          "weather_labels":[x["weather"] for x in wea],"weather_values":[x["n"] for x in wea],
          "month_labels":[x["m"] for x in mon],"month_values":[x["n"] for x in mon],
          "loc_labels":[x["location"] for x in loc],"loc_values":[x["n"] for x in loc]}
    return render_template("charts.html",page_title="Charts & trends",charts=data)

@app.route("/map")
@auth
def accident_map():
    with db() as c: rows=c.execute("SELECT * FROM accidents WHERE latitude IS NOT NULL AND longitude IS NOT NULL ORDER BY accident_date DESC").fetchall()
    return render_template("map.html",page_title="Accident map",points=[dict(x) for x in rows])

@app.route("/export")
@auth
def export_csv():
    out=io.StringIO(); w=csv.writer(out)
    fields=["id","accident_date","location","severity","weather","latitude","longitude","description","created_at","updated_at"]
    w.writerow(fields)
    for r in get_records(): w.writerow([r[k] for k in fields])
    response=make_response("\\ufeff"+out.getvalue());response.headers["Content-Type"]="text/csv; charset=utf-8"
    response.headers["Content-Disposition"]="attachment; filename=road_accidents.csv";return response

@app.route("/import",methods=["POST"])
@auth
def import_csv():
    f=request.files.get("file")
    if not f or not f.filename.lower().endswith(".csv"):
        flash("Choose a CSV file.","warning");return redirect(url_for("records"))
    try:
        reader=csv.DictReader(io.StringIO(f.stream.read().decode("utf-8-sig")))
        if not reader.fieldnames or not {"accident_date","location","severity"}.issubset(reader.fieldnames):
            flash("CSV needs accident_date, location, and severity columns.","danger");return redirect(url_for("records"))
        added=0
        with db() as c:
            for item in reader:
                r,errs=parse_form({"accident_date":item.get("accident_date",""),"location":item.get("location",""),
                    "severity":item.get("severity",""),"weather":item.get("weather") or "Other","latitude":item.get("latitude",""),
                    "longitude":item.get("longitude",""),"description":item.get("description","")})
                if not errs:
                    c.execute("INSERT INTO accidents(accident_date,location,severity,weather,latitude,longitude,description) VALUES(?,?,?,?,?,?,?)",
                              tuple(r[k] for k in ["accident_date","location","severity","weather","latitude","longitude","description"]));added+=1
        flash(f"Imported {added} valid record(s). Invalid rows were skipped.","success" if added else "warning")
    except Exception as e: flash(f"Could not import CSV: {e}","danger")
    return redirect(url_for("records"))

@app.errorhandler(404)
def not_found(e): return render_template("error.html",page_title="Not found",code=404),404

init_db()
if __name__=="__main__":
    app.run(host="127.0.0.1",port=int(os.environ.get("PORT","5000")),debug=os.environ.get("FLASK_DEBUG","1")=="1")
