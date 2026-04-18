import os
import time
import asyncio
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


def get_latest_temperature():
    query = f'''
    from(bucket: "{INFLUX_BUCKET}")
      |> range(start: -2m)
      |> filter(fn: (r) => r._measurement == "environment")
      |> filter(fn: (r) => r._field == "scd30_temperature_c")
      |> last()
    '''

    with InfluxDBClient(
        url=INFLUX_URL,
        token=INFLUX_TOKEN,
        org=INFLUX_ORG,
        timeout=5000,
    ) as client:
        tables = client.query_api().query(query)
        for table in tables:
            for record in table.records:
                return record.get_value()
    return None


async def kasa_update(plug):
    await asyncio.wait_for(plug.update(), timeout=KASA_TIMEOUT)


async def kasa_turn_on(plug):
    await asyncio.wait_for(plug.turn_on(), timeout=KASA_TIMEOUT)


async def kasa_turn_off(plug):
    await asyncio.wait_for(plug.turn_off(), timeout=KASA_TIMEOUT)


def decide_heater_state(temp, current_on):
    if temp is None:
        return current_on, "no_temp"

    # Emergency cutoff
    if temp >= TEMP_EMERGENCY_HIGH:
        return False, "emergency_off"

    # Normal hysteresis
    if temp > TEMP_HIGH:
        return False, "high_off"

    if temp < TEMP_LOW:
        return True, "low_on"

    return current_on, "hold"


async def main():
    print("Connecting to Kasa plug...")
    plug = await asyncio.wait_for(
        Discover.discover_single(PLUG_IP),
        timeout=KASA_TIMEOUT
    )
    await kasa_update(plug)
    print(f"Connected: {plug.alias} | Currently on: {plug.is_on}")

    while True:
        try:
            temp = get_latest_temperature()
            await kasa_update(plug)

            current_on = plug.is_on
            desired_on, reason = decide_heater_state(temp, current_on)

            if temp is None:
                print("No temperature data found")

            elif desired_on != current_on:
                if desired_on:
                    await kasa_turn_on(plug)
                    print(f"{temp:.2f}°C -> Plug ON ({reason})")
                else:
                    await kasa_turn_off(plug)
                    print(f"{temp:.2f}°C -> Plug OFF ({reason})")

            else:
                print(f"{temp:.2f}°C -> No change ({reason})")

        except asyncio.TimeoutError:
            print("Timeout talking to plug")
        except Exception as e:
            print(f"Error: {e}")

        await asyncio.sleep(CHECK_INTERVAL_SECONDS)


if __name__ == "__main__":
    asyncio.run(main())

