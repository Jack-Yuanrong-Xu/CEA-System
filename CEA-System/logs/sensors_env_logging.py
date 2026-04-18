#!/usr/bin/env python3

import os
import sys
import time

import board
import busio
import adafruit_scd30

from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS

# ── InfluxDB settings ─────────────────────────────────────
INFLUX_URL = "http://localhost:8086"
INFLUX_TOKEN = os.environ["INFLUX_TOKEN"]
INFLUX_ORG = "CEA-System"
INFLUX_BUCKET = "cea_sensors"

# ── Logger settings ───────────────────────────────────────
POLL_INTERVAL = 10

# ── Sensor metadata ───────────────────────────────────────
SCD30_ID = "scd30_01"


def init_i2c():
    """Create the shared I2C bus."""
    try:
        i2c = busio.I2C(board.SCL, board.SDA)
        print("[OK] I2C bus initialized.")
        return i2c
    except Exception as exc:
        print(f"[FATAL] Could not initialize I2C bus: {exc}")
        sys.exit(1)


def init_scd30(i2c):
    """Try to initialize SCD30."""
    try:
        sensor = adafruit_scd30.SCD30(i2c)

        try:
            sensor.measurement_interval = 2
        except Exception:
            pass

        print("[OK] SCD30 initialized at 0x61.")
        return sensor
    except Exception as exc:
        print(f"[WARN] SCD30 not available: {exc}")
        return None


def init_influx():
    """Create InfluxDB client and write API."""
    try:
        client = InfluxDBClient(
            url=INFLUX_URL,
            token=INFLUX_TOKEN,
            org=INFLUX_ORG,
        )
        write_api = client.write_api(write_options=SYNCHRONOUS)
        print("[OK] InfluxDB client initialized.")
        return client, write_api
    except Exception as exc:
        print(f"[FATAL] Could not connect to InfluxDB: {exc}")
        sys.exit(1)


def read_scd30(sensor):
    """Read CO2, temperature, and humidity from SCD30."""
    if sensor is None:
        return None

    try:
        if not sensor.data_available:
            return None

        return {
            "scd30_co2_ppm": round(sensor.CO2, 2),
            "scd30_temperature_c": round(sensor.temperature, 2),
            "scd30_humidity_pct": round(sensor.relative_humidity, 2),
        }
    except Exception as exc:
        print(f"[WARN] Failed reading SCD30: {exc}")
        return None


def build_point(scd30_data):
    """Build one InfluxDB point from available SCD30 data."""
    point = Point("environment")

    if scd30_data is not None:
        point = (
            point
            .tag("scd30_id", SCD30_ID)
            .field("scd30_co2_ppm", scd30_data["scd30_co2_ppm"])
            .field("scd30_temperature_c", scd30_data["scd30_temperature_c"])
            .field("scd30_humidity_pct", scd30_data["scd30_humidity_pct"])
        )

    return point


def print_status(scd30_data):
    """Print one readable status block to the terminal."""
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    print("\n" + "=" * 50)
    print(f"Timestamp: {timestamp}")

    if scd30_data is not None:
        print(f"SCD30 CO2:       {scd30_data['scd30_co2_ppm']} ppm")
        print(f"SCD30 Temp:      {scd30_data['scd30_temperature_c']} °C")
        print(f"SCD30 Humidity:  {scd30_data['scd30_humidity_pct']} %")
    else:
        print("SCD30:           no new data")


def main():
    i2c = init_i2c()
    client, write_api = init_influx()

    scd30 = init_scd30(i2c)

    if scd30 is None:
        print("[FATAL] No SCD30 initialized. Check wiring and I2C.")
        sys.exit(1)

    print("[INFO] Starting environmental logger. Press Ctrl+C to stop.")

    try:
        while True:
            scd30_data = read_scd30(scd30)

            print_status(scd30_data)

            if scd30_data is None:
                print("[WARN] No SCD30 data available this cycle.")
            else:
                point = build_point(scd30_data)

                try:
                    write_api.write(
                        bucket=INFLUX_BUCKET,
                        org=INFLUX_ORG,
                        record=point,
                    )
                    print("[OK] Wrote environmental data to InfluxDB.")
                except Exception as exc:
                    print(f"[WARN] Failed to write to InfluxDB: {exc}")

            # Re-scan missing sensor every cycle
            if scd30 is None:
                scd30 = init_scd30(i2c)

            time.sleep(POLL_INTERVAL)

    except KeyboardInterrupt:
        print("\n[INFO] Stopped by user.")
    finally:
        client.close()


if __name__ == "__main__":
    main()
