from flask import Flask, request, jsonify
from datetime import datetime, timedelta
import json
import os

app = Flask(__name__)

LICENSE_DB = "licenses.json"
ADMIN_SECRET = os.getenv("ADMIN_SECRET", "degistir")


def load_licenses():
    if not os.path.exists(LICENSE_DB):
        return {}

    with open(LICENSE_DB, "r", encoding="utf-8") as f:
        return json.load(f)


def save_licenses(data):
    with open(LICENSE_DB, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)


@app.route("/")
def home():
    return jsonify({"status": "Onfroy License Server Online"})


@app.route("/check_license", methods=["POST"])
def check_license():
    data = request.json or {}

    key = data.get("license_key", "").strip()
    device_id = data.get("device_id", "").strip()

    licenses = load_licenses()

    if key not in licenses:
        return jsonify({"valid": False, "reason": "Lisans bulunamadı"})

    lic = licenses[key]

    if not lic.get("active", True):
        return jsonify({"valid": False, "reason": "Lisans pasif"})

    expires_at = lic.get("expires_at")
    expires = datetime.strptime(expires_at, "%Y-%m-%d")

    if datetime.now() > expires:
        return jsonify({
            "valid": False,
            "reason": "Lisans süresi doldu",
            "expires_at": expires_at
        })

    if not lic.get("device_id"):
        lic["device_id"] = device_id
        licenses[key] = lic
        save_licenses(licenses)

    if lic.get("device_id") != device_id:
        return jsonify({"valid": False, "reason": "Lisans başka cihaza bağlı"})

    remaining_days = (expires - datetime.now()).days

    return jsonify({
        "valid": True,
        "customer": lic.get("customer", "Müşteri"),
        "expires_at": expires_at,
        "remaining_days": remaining_days
    })


@app.route("/create_license", methods=["POST"])
def create_license():
    data = request.json or {}

    if data.get("admin_secret") != ADMIN_SECRET:
        return jsonify({"success": False, "error": "Yetkisiz"})

    key = data.get("license_key")
    customer = data.get("customer", "Müşteri")
    days = int(data.get("days", 30))

    expires_at = (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d")

    licenses = load_licenses()

    licenses[key] = {
        "customer": customer,
        "expires_at": expires_at,
        "device_id": "",
        "active": True
    }

    save_licenses(licenses)

    return jsonify({
        "success": True,
        "license_key": key,
        "customer": customer,
        "expires_at": expires_at
    })


@app.route("/extend_license", methods=["POST"])
def extend_license():
    data = request.json or {}

    if data.get("admin_secret") != ADMIN_SECRET:
        return jsonify({"success": False, "error": "Yetkisiz"})

    key = data.get("license_key")
    days = int(data.get("days", 30))

    licenses = load_licenses()

    if key not in licenses:
        return jsonify({"success": False, "error": "Lisans bulunamadı"})

    current_expiry = datetime.strptime(licenses[key]["expires_at"], "%Y-%m-%d")

    if current_expiry < datetime.now():
        current_expiry = datetime.now()

    new_expiry = current_expiry + timedelta(days=days)

    licenses[key]["expires_at"] = new_expiry.strftime("%Y-%m-%d")

    save_licenses(licenses)

    return jsonify({
        "success": True,
        "license_key": key,
        "expires_at": licenses[key]["expires_at"]
    })


@app.route("/disable_license", methods=["POST"])
def disable_license():
    data = request.json or {}

    if data.get("admin_secret") != ADMIN_SECRET:
        return jsonify({"success": False, "error": "Yetkisiz"})

    key = data.get("license_key")
    licenses = load_licenses()

    if key not in licenses:
        return jsonify({"success": False, "error": "Lisans bulunamadı"})

    licenses[key]["active"] = False
    save_licenses(licenses)

    return jsonify({"success": True, "message": "Lisans pasifleştirildi"})