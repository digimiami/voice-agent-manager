"""Refresh the Daytona Auto Mall inventory cache (daily cron).

Scrapes the dealer's DealerOn cosmos SRP API (52 pages x 12 vehicles)
into /root/voice-agent-manager/daytona_inventory.json — the file the
/api/inventory/search endpoint reads for the demo car-salesman agent.
"""
import json
import os
import sys
import time
import urllib.request

BASE = "https://www.daytonaautomall.com/api/vhcliaa/vehicle-pages/cosmos/srp/vehicles/20953/1698446"
OUT = "/root/voice-agent-manager/daytona_inventory.json"
HDRS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/126.0",
    "Accept": "application/json",
}


def fetch_page(page):
    url = f"{BASE}?host=www.daytonaautomall.com&PageNumber={page}&PageSize=12"
    req = urllib.request.Request(url, headers=HDRS)
    with urllib.request.urlopen(req, timeout=25) as r:
        return json.loads(r.read())


def main():
    vehicles = []
    pages = int(sys.argv[1]) if len(sys.argv) > 1 else 52
    for page in range(1, pages + 1):
        try:
            d = fetch_page(page)
            for c in d.get("DisplayCards") or []:
                v = c.get("VehicleCard") or {}
                if not v.get("VehicleVin"):
                    continue
                vehicles.append({
                    "vin": v.get("VehicleVin"), "stock": v.get("VehicleStockNumber"),
                    "year": v.get("VehicleYear"), "make": v.get("VehicleMake"),
                    "model": v.get("VehicleModel"), "trim": v.get("VehicleTrim"),
                    "name": v.get("VehicleName"),
                    "price": v.get("VehicleInternetPrice") or v.get("VehicleMsrp") or 0,
                    "msrp": v.get("VehicleMsrp"),
                    "mileage": v.get("Mileage") or v.get("VehicleMileage"),
                    "engine": v.get("VehicleEngine"), "transmission": v.get("VehicleTransmission"),
                    "drivetrain": v.get("VehicleDriveTrain"), "fuel": v.get("VehicleFuelType"),
                    "body": v.get("VehicleBodyStyle") or v.get("VehicleBodyType"),
                    "ext_color": v.get("VehicleExteriorColorLabel"),
                    "int_color": v.get("VehicleInteriorColorLabel"),
                    "mpg_city": v.get("VehicleMpgCity"), "mpg_hwy": v.get("VehicleMpgHwy"),
                    "features": (v.get("Features") or [])[:14],
                    "url": v.get("VehicleDetailUrl"),
                })
        except Exception as e:
            print(f"page {page} FAILED: {e}", flush=True)
        time.sleep(0.5)
    tmp = OUT + ".tmp"
    with open(tmp, "w") as f:
        json.dump(vehicles, f, indent=1)
    os.replace(tmp, OUT)
    priced = sum(1 for v in vehicles if v.get("price"))
    print(f"daytona inventory refreshed: {len(vehicles)} vehicles ({priced} priced)")


if __name__ == "__main__":
    main()
