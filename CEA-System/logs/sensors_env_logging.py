#!/usr/bin/env python3

import os
import sys
import time

import board
import busio
import adafruit_sht31d
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
SHT31_ID = "sht31_01"
SCD30_ID = "scd30_01"

# Define the I2C bus initiation
def init_i2c():
    """Create the shared I2C bus."""
    try:
        i2c = busio.I2C(board.SCL, board.SDA)
        print("[OK] I2C bus initialized.")
        return i2c
    except Exception as exc:
        print(f"[FATAL] Could not initialize I2C bus: {exc}")
        sys.exit(1)

# Define detecting sht31 sensor
def init_sht31(i2c):
    """Try to initialize SHT31 at 0x44 or 0x45."""
    for address in [0x44, 0x45]:
        try:
            sensor = adafruit_sht31d.SHT31D(i2c, address=address)
            _ = sensor.temperature
            print(f"[OK] SHT31 initialized at 0x{address:02X}.")
            return sensor, address
        except Exception:
            continue

    print("[WARN] SHT31 not found at 0x44 or 0x45.")
    return None, None

# Define SCD30 sensor initialization
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

# InfluxDB initialization
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

# Reading from SHT31
def read_sht31(sensor):
    """Read temperature and humidity from SHT31."""
    if sensor is None:
        return None

    try:
        return {
            "sht31_temperature_c": round(sensor.temperature, 2),
            "sht31_humidity_pct": round(sensor.relative_humidity, 2),
        }
    except Exception as exc:
        print(f"[WARN] Failed reading SHT31: {exc}")
        return None

# Reading from SCD30
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

# Building InfluxDB Point from readings
def build_point(sht31_data, scd30_data, sht31_addr):
    """Build one InfluxDB point from available sensor data."""
    point = Point("environment")

    if sht31_data is not None:
        point = (
            point
            .tag("sht31_id", SHT31_ID)
            .tag("sht31_address", f"0x{sht31_addr:02X}")
            .field("sht31_temperature_c", sht31_data["sht31_temperature_c"])
            .field("sht31_humidity_pct", sht31_data["sht31_humidity_pct"])
        )

    if scd30_data is not None:
        point = (
            point
            .tag("scd30_id", SCD30_ID)
            .field("scd30_co2_ppm", scd30_data["scd30_co2_ppm"])
            .field("scd30_temperature_c", scd30_data["scd30_temperature_c"])
            .field("scd30_humidity_pct", scd30_data["scd30_humidity_pct"])
        )

    return point

# Console summary
def print_status(sht31_data, scd30_data):
    """Print one readable status block to the terminal."""
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    print("\n" + "=" * 50)
    print(f"Timestamp: {timestamp}")

    if sht31_data is not None:
        print(f"SHT31 Temp:      {sht31_data['sht31_temperature_c']} °C")
        print(f"SHT31 Humidity:  {sht31_data['sht31_humidity_pct']} %")
    else:
        print("SHT31:           no data")

    if scd30_data is not None:
        print(f"SCD30 CO2:       {scd30_data['scd30_co2_ppm']} ppm")
        print(f"SCD30 Temp:      {scd30_data['scd30_temperature_c']} °C")
        print(f"SCD30 Humidity:  {scd30_data['scd30_humidity_pct']} %")
    else:
        print("SCD30:           no new data")

    if sht31_data is not None and scd30_data is not None:
        temp_diff = round(
            scd30_data["scd30_temperature_c"] - sht31_data["sht31_temperature_c"], 2
        )
        rh_diff = round(
            scd30_data["scd30_humidity_pct"] - sht31_data["sht31_humidity_pct"], 2
        )
        print(f"Temp difference: {temp_diff} °C (SCD30 - SHT31)")
        print(f"RH difference:   {rh_diff} % (SCD30 - SHT31)")

# Main Function
def main():
    i2c = init_i2c()
    client, write_api = init_influx()

    sht31, sht31_addr = init_sht31(i2c)
    scd30 = init_scd30(i2c)

    if sht31 is None and scd30 is None: 
        print("[FATAL] No sensors initialized. Check wiring and I2C")
        sys.exit(1)

    print("[INFO] Starting environmental logger. Press Ctrl+C to stop.")

    try: 
        while True:
            sht31_data = read_sht31(sht31)
            scd30_data = read_scd30(scd30)

            print_status(sht31_data, scd30_data)

            if sht31_data is None and scd30_data is None:
                print("[WARN] No sensor data available this cycle.")
            else:
                point = build_point(sht31_data, scd30_data, sht31_addr)

                try:
                    write_api.write(
                        bucket=INFLUX_BUCKET,
                        org=INFLUX_ORG,
                        record=point,
                    )
                    print("[OK] Wrote environmental data to InfluxDB.")
                except Exception as exc:
                    print(f"[WARN] Failed to write to InfluxDB: {exc}")

                # Re-scan missing sensors
                if sht31 is None:
                    sht31, sht31_addr = init_sht31(i2c)

                if scd30 is None:
                    scd30 = init_scd30(i2c)

                time.sleep(POLL_INTERVAL)

    except KeyboardInterrupt:
                print("\n[INFO] Stopped by user.")
    finally:
                client.close()

# Python entry point
if __name__ == "__main__":
    main()
