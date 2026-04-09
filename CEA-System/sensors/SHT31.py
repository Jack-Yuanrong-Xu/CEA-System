import board
import busio
import adafruit_sht31d
import time
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS

# InfluxDB settings
INFLUX_URL    = "http://localhost:8086"
INFLUX_TOKEN  = "dgb7gK1La29f4buWmHf5OmUeUVDttZn1YZEUTq-7VGsf8PwVfNg0OGs8QM7HzRBGvSrHKK2J2FjsYh85Bu1yKQ=="
INFLUX_ORG    = "CEA-System"
INFLUX_BUCKET = "cea_sensors"

# Sensor settings
SENSOR_ID = "sht31_01"
POLL_INTERVAL = 10

# Initialize I2C and sensor
i2c = busio.I2C(board.SCL, board.SDA)
sensor = adafruit_sht31d.SHT31D(i2c, address = 0x44)

# Initialize InfluxDB client
client = InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG)
write_api = client.write_api(write_options=SYNCHRONOUS)

print(f"CEA-System sensor logger started. Writing to bucket: {INFLUX_BUCKET}")

# Main Loop
while True:
    try: 
        temperature = sensor.temperature
        humidity = sensor.relative_humidity

        point = (
            Point("environment")
            .tag("sensor_id", SENSOR_ID)
            .field("temperature_c", temperature)
            .field("humidity_pct", humidity)
        )

        write_api.write(bucket=INFLUX_BUCKET, org=INFLUX_ORG, record=point)

        print(f"Temperature: {temperature:.1f} °C | Humidity: {humidity:.1f} %")
    
    except Exception as e: 
        print(f"Error: {e}")

    time.sleep(POLL_INTERVAL)

