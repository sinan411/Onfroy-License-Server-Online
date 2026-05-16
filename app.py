import os
import requests
from datetime import datetime, timedelta, timezone
from flask import Flask, request, jsonify

app = Flask(__name__)

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")
ADMIN_SECRET = os.getenv("ADMIN_SECRET")

TABLE = "licenses"


def supabase_headers():
    return {
        "apikey": SUPABASE_SERVICE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation"
    }


def table_url():
    return f"{SUPABASE_URL}/rest/v1/{TABLE}"


@app.route("/")
def home():
    return jsonify({
        "status": "Onfroy License Server Online",
        "database": "Supabase"
    })


@app.route("/create_license", methods=["POST"])
def create_license():
    data = request.json or {}

    if data.get("admin_secret") != ADMIN_SECRET:
        return jsonify({
            "success": False,
            "error": "Yetkisiz işlem"
        }), 403

    license_key = data.get("license_key", "").strip()
    customer = data.get("customer", "").strip()
    contact = data.get("contact", "").strip()
    days = int(data.get("days", 30))

    if not license_key or not customer:
        return jsonify({
            "success": False,
            "error": "license_key ve customer zorunlu"
        }), 400

    expires_at = (
        datetime.now(timezone.utc) + timedelta(days=days)
    ).isoformat()

    payload = {
        "license_key": license_key,
        "customer": customer,
        "contact": contact,
        "expires_at": expires_at,
        "status": "active"
    }

    r = requests.post(
        table_url(),
        headers=supabase_headers(),
        json=payload,
        timeout=20
    )

    if r.status_code not in [200, 201]:
        return jsonify({
            "success": False,
            "error": r.text
        }), 500

    return jsonify({
        "success": True,
        "license_key": license_key,
        "customer": customer,
        "expires_at": expires_at
    })


@app.route("/verify_license", methods=["POST"])
def verify_license():
    data = request.json or {}

    license_key = data.get("license_key", "").strip()
    device_id = data.get("device_id", "").strip()

    if not license_key:
        return jsonify({
            "success": False,
            "active": False,
            "error": "Lisans kodu boş"
        }), 400

    r = requests.get(
        table_url(),
        headers=supabase_headers(),
        params={
            "license_key": f"eq.{license_key}",
            "select": "*"
        },
        timeout=20
    )

    if r.status_code != 200:
        return jsonify({
            "success": False,
            "active": False,
            "error": r.text
        }), 500

    rows = r.json()

    if not rows:
        return jsonify({
            "success": False,
            "active": False,
            "error": "Lisans bulunamadı"
        }), 404

    license_data = rows[0]

    if license_data.get("status") != "active":
        return jsonify({
            "success": True,
            "active": False,
            "error": "Lisans pasif"
        })

    expires_at = datetime.fromisoformat(
        license_data["expires_at"].replace("Z", "+00:00")
    )

    now = datetime.now(timezone.utc)

    if expires_at < now:
        return jsonify({
            "success": True,
            "active": False,
            "error": "Lisans süresi dolmuş",
            "expires_at": license_data["expires_at"]
        })

    saved_device = license_data.get("device_id")

    if saved_device and device_id and saved_device != device_id:
        return jsonify({
            "success": True,
            "active": False,
            "error": "Bu lisans başka cihazda aktif"
        })

    if not saved_device and device_id:
        requests.patch(
            table_url(),
            headers=supabase_headers(),
            params={
                "license_key": f"eq.{license_key}"
            },
            json={
                "device_id": device_id,
                "updated_at": datetime.now(timezone.utc).isoformat()
            },
            timeout=20
        )

    remaining_days = max(
        0,
        (expires_at - now).days
    )

    return jsonify({
        "success": True,
        "active": True,
        "customer": license_data.get("customer"),
        "contact": license_data.get("contact"),
        "expires_at": license_data.get("expires_at"),
        "remaining_days": remaining_days,
        "device_id": saved_device or device_id
    })


@app.route("/list_licenses", methods=["POST"])
def list_licenses():
    data = request.json or {}

    if data.get("admin_secret") != ADMIN_SECRET:
        return jsonify({
            "success": False,
            "error": "Yetkisiz işlem"
        }), 403

    r = requests.get(
        table_url(),
        headers=supabase_headers(),
        params={
            "select": "*",
            "order": "created_at.desc"
        },
        timeout=20
    )

    if r.status_code != 200:
        return jsonify({
            "success": False,
            "error": r.text
        }), 500

    return jsonify({
        "success": True,
        "licenses": r.json()
    })


@app.route("/disable_license", methods=["POST"])
def disable_license():
    data = request.json or {}

    if data.get("admin_secret") != ADMIN_SECRET:
        return jsonify({
            "success": False,
            "error": "Yetkisiz işlem"
        }), 403

    license_key = data.get("license_key", "").strip()

    r = requests.patch(
        table_url(),
        headers=supabase_headers(),
        params={
            "license_key": f"eq.{license_key}"
        },
        json={
            "status": "disabled",
            "updated_at": datetime.now(timezone.utc).isoformat()
        },
        timeout=20
    )

    if r.status_code not in [200, 204]:
        return jsonify({
            "success": False,
            "error": r.text
        }), 500

    return jsonify({
        "success": True,
        "message": "Lisans devre dışı bırakıldı"
    })


@app.route("/reset_device", methods=["POST"])
def reset_device():
    data = request.json or {}

    if data.get("admin_secret") != ADMIN_SECRET:
        return jsonify({
            "success": False,
            "error": "Yetkisiz işlem"
        }), 403

    license_key = data.get("license_key", "").strip()

    r = requests.patch(
        table_url(),
        headers=supabase_headers(),
        params={
            "license_key": f"eq.{license_key}"
        },
        json={
            "device_id": None,
            "updated_at": datetime.now(timezone.utc).isoformat()
        },
        timeout=20
    )

    if r.status_code not in [200, 204]:
        return jsonify({
            "success": False,
            "error": r.text
        }), 500

    return jsonify({
        "success": True,
        "message": "Cihaz ID sıfırlandı"
    })


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.getenv("PORT", 5000))
    )
