import board
import busio
import adafruit_sht31d
import time
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS

# ── InfluxDB connection settings ──────────────────────────
INFLUX_URL    = "http://localhost:8086"
INFLUX_TOKEN  = "dgb7gK1La29f4buWmHf5OmUeUVDttZn1YZEUTq-7VGsf8PwVfNg0OGs8QM7HzRBGvSrHKK2J2FjsYh85Bu1yKQ=="
INFLUX_ORG    = "CEA-System"
INFLUX_BUCKET = "cea_sensors"

SENSOR_ID     = "sht31_01"
POLL_INTERVAL = 10

# ── Initialize I2C ────────────────────────────────────────
i2c = busio.I2C(board.SCL, board.SDA)

# ── Helper: detect sensor at 0x44 or 0x45 ────────────────
def find_sensor():
    for address in [0x44, 0x45]:
        try:
            s = adafruit_sht31d.SHT31D(i2c, address=address)
            _ = s.temperature
            print(f"SHT31 found at 0x{address:02X}")
            return s
        except Exception:
            continue
    return None

# ── Initialize InfluxDB ───────────────────────────────────
client    = InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG)
write_api = client.write_api(write_options=SYNCHRONOUS)

sensor = find_sensor()
if sensor is None:
    raise RuntimeError("SHT31 not found at 0x44 or 0x45 — check wiring")

print(f"CEA-System logger started. Writing to: {INFLUX_BUCKET}")

# ── Main loop ─────────────────────────────────────────────
while True:
    try:
        temperature = sensor.temperature
        humidity    = sensor.relative_humidity

        point = (
            Point("environment")
            .tag("sensor_id", SENSOR_ID)
            .field("temperature_c", temperature)
            .field("humidity_pct",  humidity)
        )

        write_api.write(bucket=INFLUX_BUCKET, org=INFLUX_ORG, record=point)
        print(f"Temperature: {temperature:.1f} °C | Humidity: {humidity:.1f} %")

    except Exception as e:
        print(f"Error: {e} — re-scanning I2C bus...")
        time.sleep(2)
        sensor = find_sensor()
        if sensor is None:
            print("Sensor not found — retrying in 10s...")

    time.sleep(POLL_INTERVAL)