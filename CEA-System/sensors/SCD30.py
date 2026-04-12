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
INFLUX_URL    = "http://localhost:8086"
INFLUX_TOKEN  = os.environ["INFLUX_TOKEN"]
INFLUX_ORG    = "CEA-System"
INFLUX_BUCKET = "cea_sensors"

# ── Logger settings ───────────────────────────────────────
POLL_INTERVAL = 10
SCD30_ID      = "scd30_01"


def init_i2c():
    try:
        i2c = busio.I2C(board.SCL, board.SDA)
        print("[OK] I2C bus initialized.")
        return i2c
    except Exception as exc:
        print(f"[FATAL] Could not initialize I2C bus: {exc}")
        sys.exit(1)


def init_scd30(i2c):
    try:
        sensor = adafruit_scd30.SCD30(i2c)
        try:
            sensor.measurement_interval = 2
        except Exception:
            pass
        print("[OK] SCD30 initialized at 0x61.")
        return sensor
    except Exception as exc:
        print(f"[FATAL] SCD30 not available: {exc}")
        sys.exit(1)


def init_influx():
    try:
        client = InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG)
        write_api = client.write_api(write_options=SYNCHRONOUS)
        print("[OK] InfluxDB client initialized.")
        return client, write_api
    except Exception as exc:
        print(f"[FATAL] Could not connect to InfluxDB: {exc}")
        sys.exit(1)


def read_scd30(sensor):
    try:
        if not sensor.data_available:
            return None
        return {
            "co2_ppm":       round(sensor.CO2, 2),
            "temperature_c": round(sensor.temperature, 2),
            "humidity_pct":  round(sensor.relative_humidity, 2),
        }
    except Exception as exc:
        print(f"[WARN] Failed reading SCD30: {exc}")
        return None


def build_point(data):
    return (
        Point("environment")
        .tag("sensor_id", SCD30_ID)
        .field("co2_ppm",       data["co2_ppm"])
        .field("temperature_c", data["temperature_c"])
        .field("humidity_pct",  data["humidity_pct"])
    )


def print_status(data):
    print("\n" + "=" * 40)
    print(f"Timestamp:   {time.strftime('%Y-%m-%d %H:%M:%S')}")
    if data:
        print(f"CO2:         {data['co2_ppm']} ppm")
        print(f"Temperature: {data['temperature_c']} °C")
        print(f"Humidity:    {data['humidity_pct']} %")
    else:
        print("SCD30:       no new data this cycle")


def main():
    i2c              = init_i2c()
    scd30            = init_scd30(i2c)
    client, write_api = init_influx()

    print("[INFO] Starting environmental logger. Press Ctrl+C to stop.")

    try:
        while True:
            data = read_scd30(scd30)
            print_status(data)

            if data:
                try:
                    write_api.write(bucket=INFLUX_BUCKET, org=INFLUX_ORG, record=build_point(data))
                    print("[OK] Wrote to InfluxDB.")
                except Exception as exc:
                    print(f"[WARN] InfluxDB write failed: {exc}")

            time.sleep(POLL_INTERVAL)

    except KeyboardInterrupt:
        print("\n[INFO] Stopped by user.")
    finally:
        client.close()


if __name__ == "__main__":
    main()