import os
import sys
import time
import asyncio
from datetime import datetime, timezone

from kasa import Discover
from influxdb_client import InfluxDBClient

INFLUX_URL = "http://localhost:8086"
INFLUX_TOKEN = os.environ["INFLUX_TOKEN"]
INFLUX_ORG = "CEA-System"
INFLUX_BUCKET = "cea_sensors"

PLUG_IP = "192.168.1.64"

TEMP_HIGH = 37.68
TEMP_LOW = 37.56
TEMP_EMERGENCY_HIGH = 38.00

CHECK_INTERVAL_SECONDS = 30
KASA_TIMEOUT = 5

MAX_TEMP_AGE_SECONDS = 60
MAX_CONSECUTIVE_FAILURES = 3


def get_latest_temperature(query_api):
    query = f'''
    from(bucket: "{INFLUX_BUCKET}")
      |> range(start: -5m)
      |> filter(fn: (r) => r._measurement == "environment")
      |> filter(fn: (r) => r._field == "scd30_temperature_c")
      |> last()
    '''

    tables = query_api.query(query)
    for table in tables:
        for record in table.records:
            return record.get_value(), record.get_time()

    return None, None


async def kasa_update(plug):
    await asyncio.wait_for(plug.update(), timeout=KASA_TIMEOUT)


async def kasa_turn_on(plug):
    await asyncio.wait_for(plug.turn_on(), timeout=KASA_TIMEOUT)


async def kasa_turn_off(plug):
    await asyncio.wait_for(plug.turn_off(), timeout=KASA_TIMEOUT)


def decide_heater_state(temp, current_on):
    if temp is None:
        return False, "no_temp_fail_safe_off"

    if temp >= TEMP_EMERGENCY_HIGH:
        return False, "emergency_off"

    if temp > TEMP_HIGH:
        return False, "high_off"

    if temp < TEMP_LOW:
        return True, "low_on"

    return current_on, "hold"


async def force_off_and_exit(plug, reason):
    print(f"[FATAL] {reason}")

    try:
        await kasa_update(plug)
        if plug.is_on:
            await kasa_turn_off(plug)
            print("[SAFE] Plug forced OFF before shutdown.")
        else:
            print("[SAFE] Plug already OFF.")
    except Exception as exc:
        print(f"[WARN] Could not confirm/force plug OFF: {exc}")

    raise SystemExit(1)


async def main():
    print("Creating InfluxDB client...")
    client = InfluxDBClient(
        url=INFLUX_URL,
        token=INFLUX_TOKEN,
        org=INFLUX_ORG,
        timeout=5000,
    )
    query_api = client.query_api()

    print("Connecting to Kasa plug...")
    plug = await asyncio.wait_for(
        Discover.discover_single(PLUG_IP),
        timeout=KASA_TIMEOUT
    )
    await kasa_update(plug)
    print(f"Connected: {plug.alias} | Currently on: {plug.is_on}")

    consecutive_failures = 0

    try:
        while True:
            try:
                temp, temp_time = get_latest_temperature(query_api)
                await kasa_update(plug)

                current_on = plug.is_on

                if temp is None or temp_time is None:
                    desired_on, reason = False, "no_temp_fail_safe_off"
                else:
                    age_seconds = (datetime.now(timezone.utc) - temp_time).total_seconds()

                    if age_seconds > MAX_TEMP_AGE_SECONDS:
                        desired_on, reason = False, f"stale_temp_fail_safe_off ({int(age_seconds)}s old)"
                        temp = None
                    else:
                        desired_on, reason = decide_heater_state(temp, current_on)

                if desired_on != current_on:
                    if desired_on:
                        await kasa_turn_on(plug)
                        if temp is not None:
                            print(f"{temp:.2f}°C -> Plug ON ({reason})")
                        else:
                            print(f"Temp unavailable -> Plug ON ({reason})")
                    else:
                        await kasa_turn_off(plug)
                        if temp is not None:
                            print(f"{temp:.2f}°C -> Plug OFF ({reason})")
                        else:
                            print(f"Temp unavailable -> Plug OFF ({reason})")
                else:
                    if temp is not None:
                        print(f"{temp:.2f}°C -> No change ({reason})")
                    else:
                        print(f"Temp unavailable -> No change ({reason})")

                consecutive_failures = 0

            except asyncio.TimeoutError:
                consecutive_failures += 1
                print(f"[WARN] Timeout talking to plug ({consecutive_failures}/{MAX_CONSECUTIVE_FAILURES})")

            except Exception as e:
                consecutive_failures += 1
                print(f"[WARN] Error ({consecutive_failures}/{MAX_CONSECUTIVE_FAILURES}): {e}")

            if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                await force_off_and_exit(
                    plug,
                    f"Too many consecutive failures ({consecutive_failures}). Exiting for clean restart."
                )

            await asyncio.sleep(CHECK_INTERVAL_SECONDS)

    finally:
        client.close()


if __name__ == "__main__":
    asyncio.run(main())
