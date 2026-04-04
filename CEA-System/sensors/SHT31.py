import board
import busio
import adafruit_sht31d

# Initialize I2C and sensor
i2c = busio.I2C(board.SCL, board.SDA)
sensor = adafruit_sht31d.SHT31D(i2c)

# Read and print values
print(f"Temperature: {sensor.temperature:.1f} °C")
print(f"Humidity: {sensor.relative_humidity:.1f} %")