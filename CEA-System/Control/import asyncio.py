import asyncio
from kasa import Discover

PLUG_IP = "192.168.1.64"  # replace with your plug's IP

async def main():
    plug = await Discover.discover_single(PLUG_IP)
    await plug.update()
    print(f"{plug.alias} is on: {plug.is_on}")

    await plug.turn_on()
    print("Turned on")

    #await plug.turn_off()
    #print(f"Is on: {plug.is_on}")

asyncio.run(main())