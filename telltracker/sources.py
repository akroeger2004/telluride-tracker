"""The three sources: how to fetch each one and how to convert what it returns into rows.

  telluride  web page   Telluride Ski & Golf snow report: mountain snow numbers, 17 lifts,
                        the hike-to terrain areas and every trail
  snotel     JSON       NRCS SNOTEL snow stations around Telluride (snow depth, water, temperature)
  nws        JSON       National Weather Service forecast for the Mountain Village grid point

No source needs a login or a key. Each fetcher keeps only the part that is tracked.
A converter turns the raw bytes into a list of item rows; it depends only on the bytes and on
the run date, so rebuilding the history from raw files always gives the same result.
"""
import html
import json
import re
import time
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta, timezone

BROWSER = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
           "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
POLITE = "telluride-tracker (Financial Data Analytics course project)"

REPORT_URL = "https://tellurideskiresort.com/snow-report/"
SNOTEL_URL = ("https://wcc.sc.egov.usda.gov/awdbRestApi/services/v1/data?stationTriplets={stations}"
              "&elements=SNWD,WTEQ,PREC,TAVG,TMAX,TMIN&duration=DAILY&beginDate={begin}&endDate={end}"
              "&returnFlags=false")
NWS_URL = "https://api.weather.gov/gridpoints/GJT/115,49"  # Mountain Village, Colorado

# SNOTEL stations within about 20 miles of Telluride: triplet -> (name, elevation in feet)
STATIONS = {
    "1344:CO:SNTL": ("Alta Lakes", 11290),
    "713:CO:SNTL": ("Red Mountain Pass", 11060),
    "538:CO:SNTL": ("Idarado", 9780),
    "629:CO:SNTL": ("Mineral Creek", 10030),
    "586:CO:SNTL": ("Lizard Head Pass", 10190),
    "632:CO:SNTL": ("Molas Lake", 10610),
    "465:CO:SNTL": ("El Diente Peak", 10210),
    "780:CO:SNTL": ("Spud Mountain", 10660),
    "387:CO:SNTL": ("Cascade #2", 8990),
}

# every numeric column of the history file, in order
NUMERIC = [
    "is_open", "on_hold", "is_groomed", "hours_open",
    "snow_depth_in", "snow_overnight_in", "snow_24h_in", "snow_48h_in", "snow_7d_in", "season_total_in",
    "lifts_open", "lifts_total", "trails_open", "trails_total",
    "swe_in", "precip_in", "elevation_ft",
    "temp_f", "temp_high_f", "temp_low_f",
    "forecast_snow_24h_in", "forecast_snow_72h_in", "forecast_precip_chance",
]
TEXT = ["category", "area", "level", "status", "obs_date"]


class SourceError(Exception):
    """The source answered, but not with the page or data we expect."""


# --------------------------------------------------------------------------- http


def http_get(url, headers=None, retries=4, timeout=60):
    hdrs = {"User-Agent": BROWSER, "Accept": "*/*", **(headers or {})}
    last = None
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=hdrs), timeout=timeout) as resp:
                return resp.read()
        except urllib.error.HTTPError as exc:
            last = exc
            if exc.code < 500 and exc.code != 429:
                raise
        except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
            last = exc
        time.sleep(3 * (attempt + 1))
    raise last


# -------------------------------------------------------------------------- helpers


def slug(text):
    return re.sub(r"[^a-z0-9]+", "-", html.unescape(text).lower()).strip("-")


def number(text):
    """First number in a string like '12\"' or '39°F' or '48&deg;F'."""
    m = re.search(r"-?\d+(?:\.\d+)?", html.unescape(text or ""))
    return float(m.group(0)) if m else None


def c_to_f(c):
    return c * 9 / 5 + 32


# ============================================================ source 1: the snow report

REPORT_START = "tsr-report-app-snow-totals"
REPORT_END = "tsr-report-app-forecast-items"


def extract_report_region(page):
    """Keep only the part of the page that holds the report (the rest is site navigation)."""
    if REPORT_START not in page or REPORT_END not in page:
        raise SourceError("the snow report is not on the page (layout changed or blocked)")
    start = page.rfind("<div", 0, page.index(REPORT_START))
    end_marker = page.index(REPORT_END)
    end = page.find("</div></div>", end_marker)
    end = len(page) if end < 0 else end + len("</div></div>")
    return page[start:end]


def fetch_report():
    page = http_get(REPORT_URL).decode("utf-8", "replace")
    return extract_report_region(page).encode("utf-8")


_STATUS = re.compile(r"tsr-report-app-icon-(open|hold|closed|hike)")
_SUMMARY = re.compile(r"<span>([^<]+)</span>\s*<span><strong>([^<]*)</strong></span>")
_CONDITION = re.compile(r"Current snow condition</strong></span>\s*<br\s*/?>\s*<span>([^<]*)</span>")
_LIFT_ROW = re.compile(r"<tr>\s*<td>(.*?)</td>\s*<td>(.*?)</td>\s*<td>(.*?)</td>\s*<td>(.*?)</td>", re.S)
_AREA = re.compile(r"<p>\s*<span class=\"tsr-report-app-icon-(\w+)\"></span>\s*<span>([^<]*)</span>\s*</p>")
_TRAIL_ITEM = re.compile(
    r"<h4>\s*([^<]*?)\s*<span>"
    r"|<p\s+class=\"tsr-report-app-trail-list-trail\"([^>]*)>\s*"
    r"<span class=\"tsr-report-app-level\"[^>]*></span>\s*<span>([^<]*)</span>", re.S)
_FORECAST = re.compile(
    r"tsr-report-app-forecast-items\"><div>\s*<p>([^<]*)</p>\s*<p>([^<]*)</p>\s*"
    r"<p>High:\s*([^<]*)</p>\s*<p>Low:\s*([^<]*)</p>", re.S)
_HOURS = re.compile(r"(\d{1,2})(?::(\d{2}))?\s*([AP])M?\s*[-–to]+\s*(\d{1,2})(?::(\d{2}))?\s*([AP])M?", re.I)


def _status_of(fragment):
    m = _STATUS.search(fragment)
    return m.group(1) if m else ""


def _hours_open(text):
    """'9:00AM - 4:00PM' -> 7.0; 'CLOSED' or anything unreadable -> 0.0 or None."""
    t = html.unescape(text).strip()
    if not t or t.upper() == "CLOSED":
        return 0.0
    m = _HOURS.search(t)
    if not m:
        return None

    def to_hours(h, mnt, ap):
        h = int(h) % 12 + (12 if ap.upper() == "P" else 0)
        return h + int(mnt or 0) / 60

    span = to_hours(m.group(4), m.group(5), m.group(6)) - to_hours(m.group(1), m.group(2), m.group(3))
    return round(span, 2) if span > 0 else None


def convert_report(content, run_date):
    page = content.decode("utf-8", "replace")
    summary = {html.unescape(k).strip(): v for k, v in _SUMMARY.findall(page)}
    if "Snow depth" not in summary:
        raise SourceError("snow report: no snow depth found")
    lift_table = page[page.index("tsr-report-app-lift-table"):] if "tsr-report-app-lift-table" in page else ""
    lifts = []
    for icon, name, area, hours in _LIFT_ROW.findall(lift_table.split("</table>")[0]):
        name = html.unescape(re.sub(r"<[^>]+>", "", name)).strip()
        if name:
            lifts.append((name, html.unescape(area).strip(), _status_of(icon), re.sub(r"<[^>]+>", "", hours)))
    areas_html = page.split("tsr-report-app-terrain-areas-list", 1)[1].split("</div>")[0] \
        if "tsr-report-app-terrain-areas-list" in page else ""
    areas = [(html.unescape(n).strip(), i) for i, n in _AREA.findall(areas_html)]  # i is already open/hold/closed/hike

    trails, group = {}, ""
    trail_html = page.split("tsr-report-app-trail-list-lift", 1)[1] if "tsr-report-app-trail-list-lift" in page else ""
    for lift_name, attrs, trail_name in _TRAIL_ITEM.findall(trail_html):
        if lift_name:
            group = html.unescape(lift_name).strip()
            continue
        a = dict(re.findall(r'data-(\w+)="([^"]*)"', attrs))
        key = "trail:" + slug(trail_name)
        if not slug(trail_name) or key in trails:
            continue  # a trail listed under two lifts is one item
        status = "closed" if a.get("closed") == "1" else "hold" if a.get("hold") == "1" else "open"
        trails[key] = {"item": html.unescape(trail_name).strip(), "area": group, "level": a.get("level", ""),
                       "status": status, "groomed": 1 if a.get("groomed") == "1" else 0}
    if len(lifts) < 5 or len(trails) < 20:
        raise SourceError(f"snow report: only {len(lifts)} lifts and {len(trails)} trails found")

    rows = []
    n_open_lifts = sum(1 for _, _, s, _ in lifts if s == "open")
    n_open_trails = sum(1 for t in trails.values() if t["status"] == "open")
    forecast = _FORECAST.search(page)
    cond = _CONDITION.search(page)
    rows.append({
        "item_id": "mountain:telluride", "item": "Telluride Ski Resort", "category": "mountain",
        "area": "Telluride", "status": html.unescape(cond.group(1)).strip().lower() if cond else "",
        "obs_date": run_date.isoformat(),
        "snow_depth_in": number(summary.get("Snow depth")), "season_total_in": number(summary.get("Season total")),
        "snow_overnight_in": number(summary.get("Snow overnight")), "snow_24h_in": number(summary.get("Last 24 hours")),
        "snow_48h_in": number(summary.get("Last 48 hours")), "snow_7d_in": number(summary.get("Last 7 days")),
        "lifts_open": n_open_lifts, "lifts_total": len(lifts),
        "trails_open": n_open_trails, "trails_total": len(trails),
        "temp_f": number(forecast.group(1)) if forecast else None,
        "temp_high_f": number(forecast.group(3)) if forecast else None,
        "temp_low_f": number(forecast.group(4)) if forecast else None,
    })
    seen = set()
    for name, area, status, hours in lifts:
        key = "lift:" + slug(name)
        if key in seen:
            continue
        seen.add(key)
        rows.append({"item_id": key, "item": name, "category": "lift", "area": area, "status": status,
                     "is_open": 1 if status == "open" else 0, "on_hold": 1 if status == "hold" else 0,
                     "hours_open": _hours_open(hours)})
    for name, status in areas:
        key = "terrain:" + slug(name)
        if key in seen or not slug(name):
            continue
        seen.add(key)
        rows.append({"item_id": key, "item": name, "category": "terrain", "area": "Hike-to terrain",
                     "status": status, "is_open": 1 if status in ("open", "hike") else 0,
                     "on_hold": 1 if status == "hold" else 0})
    for key, t in trails.items():
        rows.append({"item_id": key, "item": t["item"], "category": "trail", "area": t["area"], "level": t["level"],
                     "status": t["status"], "is_open": 1 if t["status"] == "open" else 0,
                     "on_hold": 1 if t["status"] == "hold" else 0, "is_groomed": t["groomed"]})
    return rows


# ================================================================= source 2: SNOTEL


def fetch_snotel():
    today = datetime.now(timezone.utc).date()
    url = SNOTEL_URL.format(stations=",".join(STATIONS), begin=(today - timedelta(days=6)).isoformat(),
                            end=today.isoformat())
    return http_get(url, {"User-Agent": POLITE, "Accept": "application/json"})


def convert_snotel(content, run_date):
    data = json.loads(content)
    if not isinstance(data, list) or not data:
        raise SourceError("snotel: no stations returned")
    rows = []
    for station in data:
        triplet = station.get("stationTriplet")
        if triplet not in STATIONS:
            continue
        latest = {}  # element -> (date, value) of the newest value on or before the run date
        for series in station.get("data", []):
            code = series["stationElement"]["elementCode"]
            for v in series.get("values", []):
                if v.get("value") is not None and v["date"] <= run_date.isoformat():
                    if code not in latest or v["date"] > latest[code][0]:
                        latest[code] = (v["date"], v["value"])
        if "SNWD" not in latest:
            continue
        name, elevation = STATIONS[triplet]
        rows.append({
            "item_id": "station:" + triplet.split(":")[0], "item": name + " (SNOTEL)", "category": "station",
            "area": "San Juan Mountains", "obs_date": latest["SNWD"][0], "elevation_ft": elevation,
            "snow_depth_in": latest["SNWD"][1],
            "swe_in": latest.get("WTEQ", (0, None))[1], "precip_in": latest.get("PREC", (0, None))[1],
            "temp_f": latest.get("TAVG", (0, None))[1], "temp_high_f": latest.get("TMAX", (0, None))[1],
            "temp_low_f": latest.get("TMIN", (0, None))[1],
        })
    if not rows:
        raise SourceError("snotel: none of the tracked stations reported snow depth")
    return rows


# ===================================================================== source 3: NWS

NWS_KEEP = ("updateTime", "elevation", "temperature", "maxTemperature", "minTemperature",
            "snowfallAmount", "probabilityOfPrecipitation")


def fetch_nws():
    raw = json.loads(http_get(NWS_URL, {"User-Agent": POLITE, "Accept": "application/geo+json"}))
    props = raw["properties"]
    return json.dumps({"properties": {k: props[k] for k in NWS_KEEP if k in props}},
                      separators=(",", ":")).encode("utf-8")


_DURATION = re.compile(r"P(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?)?")


def _interval(valid_time):
    start_text, dur = valid_time.split("/")
    start = datetime.fromisoformat(start_text)
    d, h, m = (int(x or 0) for x in _DURATION.fullmatch(dur).groups())
    return start, start + timedelta(days=d, hours=h, minutes=m)


def _series(prop):
    return [(*_interval(v["validTime"]), v["value"]) for v in (prop or {}).get("values", []) if v.get("value") is not None]


def _window_sum(series, w0, w1):
    """Total of an amount-per-interval series over [w0, w1), prorating partial overlaps."""
    total = 0.0
    for s, e, value in series:
        overlap = (min(e, w1) - max(s, w0)).total_seconds()
        if overlap > 0:
            total += value * overlap / (e - s).total_seconds()
    return total


def convert_nws(content, run_date):
    props = json.loads(content)["properties"]
    if "snowfallAmount" not in props:
        raise SourceError("nws: no snowfall forecast in the response")
    # the forecast windows start at 12:00 UTC (6 a.m. in Telluride) on the run date
    w0 = datetime(run_date.year, run_date.month, run_date.day, 12, tzinfo=timezone.utc)
    w24, w72 = w0 + timedelta(hours=24), w0 + timedelta(hours=72)
    snow = _series(props["snowfallAmount"])

    def overlapping(series, a, b):
        return [v for s, e, v in series if e > a and s < b]

    highs = overlapping(_series(props.get("maxTemperature")), w0, w24)
    lows = overlapping(_series(props.get("minTemperature")), w0, w24)
    pop = overlapping(_series(props.get("probabilityOfPrecipitation")), w0, w24)
    return [{
        "item_id": "forecast:mountain-village", "item": "Mountain Village forecast", "category": "forecast",
        "area": "Mountain Village", "obs_date": run_date.isoformat(),
        "forecast_snow_24h_in": round(_window_sum(snow, w0, w24) / 25.4, 2),
        "forecast_snow_72h_in": round(_window_sum(snow, w0, w72) / 25.4, 2),
        "forecast_precip_chance": max(pop) if pop else None,
        "temp_high_f": round(c_to_f(max(highs)), 1) if highs else None,
        "temp_low_f": round(c_to_f(min(lows)), 1) if lows else None,
    }]


SOURCES = [
    {"name": "telluride", "label": "Telluride Ski & Golf snow report", "format": "html", "url": REPORT_URL,
     "fetch": fetch_report, "convert": convert_report},
    {"name": "snotel", "label": "NRCS SNOTEL stations near Telluride", "format": "json",
     "url": "https://wcc.sc.egov.usda.gov/awdbRestApi/services/v1/data", "fetch": fetch_snotel,
     "convert": convert_snotel},
    {"name": "nws", "label": "National Weather Service, Mountain Village forecast", "format": "json",
     "url": NWS_URL, "fetch": fetch_nws, "convert": convert_nws},
]
BY_NAME = {s["name"]: s for s in SOURCES}
