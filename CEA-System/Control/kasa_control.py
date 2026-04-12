import os
import asyncio
from kasa import Discover
from influxdb_client import InfluxDBClient

# ── InfluxDB config ───────────────────────────────────────────────
INFLUX_URL    = "http://localhost:8086"
INFLUX_TOKEN  = "dgb7gK1La29f4buWmHf5OmUeUVDttZn1YZEUTq-7VGsf8PwVfNg0OGs8QM7HzRBGvSrHKK2J2FjsYh85Bu1yKQ=="
INFLUX_ORG    = "CEA-System"
INFLUX_BUCKET = "cea_sensors"

# ── Kasa plug config ──────────────────────────────────────────────
PLUG_IP = "192.168.1.64"  

# ── Temperature thresholds (°C) ───────────────────────────────────
TEMP_HIGH = 37.8   # turn OFF above this
TEMP_LOW  = 36.8   # turn ON below this

# ── Loop interval ─────────────────────────────────────────────────
CHECK_INTERVAL_SECONDS = 30


def get_latest_temperature():
    """Query the most recent scd30_temperature_c value from InfluxDB."""
    query = f'''
    from(bucket: "{INFLUX_BUCKET}")
      |> range(start: -2m)
      |> filter(fn: (r) => r._measurement == "environment")
      |> filter(fn: (r) => r._field == "scd30_temperature_c")
      |> last()
    '''
    with InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG, timeout=30_000) as client:
        tables = client.query_api().query(query)
        for table in tables:
            for record in table.records:
                return record.get_value()
    return None  # no data found


async def main():
    print("Connecting to Kasa plug...")
    plug = await Discover.discover_single(PLUG_IP)
    await plug.update()
    print(f"Connected: {plug.alias} | Currently on: {plug.is_on}")

    plug_state = plug.is_on  # track state to avoid redundant commands

    print(f"Starting control loop — checking every {CHECK_INTERVAL_SECONDS}s")
    print(f"Thresholds: turn OFF above {TEMP_HIGH}°C, turn ON below {TEMP_LOW}°C\n")

    while True:
        temperature = get_latest_temperature()

        if temperature is None:
            print("⚠ No temperature data found in InfluxDB — skipping this cycle")

        elif temperature > TEMP_HIGH:
            if plug_state is not False:
                await plug.turn_off()
                await asyncio.sleep(1)
                await plug.update()
                plug_state = False
                print(f"🌡 {temperature:.1f}°C > {TEMP_HIGH}°C → Plug OFF ({plug.alias})")
            else:
                print(f"🌡 {temperature:.1f}°C > {TEMP_HIGH}°C → Already OFF, no action")

        elif temperature < TEMP_LOW:
            if plug_state is not True:
                await plug.turn_on()
                await asyncio.sleep(1)
                await plug.update()
                plug_state = True
                print(f"🌡 {temperature:.1f}°C < {TEMP_LOW}°C → Plug ON ({plug.alias})")
            else:
                print(f"🌡 {temperature:.1f}°C < {TEMP_LOW}°C → Already ON, no action")

        else:
            print(f"🌡 {temperature:.1f}°C — within range ({TEMP_LOW}–{TEMP_HIGH}°C), no change")

        await asyncio.sleep(CHECK_INTERVAL_SECONDS)


if __name__ == "__main__":
    asyncio.run(main())