import board
import busio
import adafruit_sht31d
import time

# Initialize I2C and sensor
i2c = busio.I2C(board.SCL, board.SDA)
sensor = adafruit_sht31d.SHT31D(i2c, address = 0x44)

# Read and print values
while True:
    print(f"Temperature: {sensor.temperature:.1f} °C")
    print(f"Humidity: {sensor.relative_humidity:.1f} %")
    time.sleep(5)

