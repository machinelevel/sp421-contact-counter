# This is the simplest bare-bones version of the contact counter.
# It's sufficient to run the device, with no extra features.
import board
import time
import digitalio
import neopixel
import adafruit_ble

start_time = time.monotonic()
led = digitalio.DigitalInOut(board.D13) # LED blinks when scanning
led.direction = digitalio.Direction.OUTPUT

# the rssi is the signal strength. Play with this until
# you like the distance things are triggering
rssi = -80   # -80 is good, -20 is very close, -120 is very far away
scan_time = 1.0 # How many seconds to scan each time
radio = adafruit_ble.BLERadio()

pixels = neopixel.NeoPixel(board.NEOPIXEL, 10, brightness=0.2, auto_write=False)
light_colors = [(167,8,211),(40,2,200),(2,20,255),(0,255,242),(10,255,38),
                (185,211,12),(211,132,4),(211,66,8),(211,4,7),(255,0,0)]
contacts_per_light = 25 # Adjust this so the display does what you want
known_addresses = set() # All of the addresses we've seen already

while True:
    scan_result = radio.start_scan(timeout=scan_time, minimum_rssi=rssi)
    for sr in scan_result:
        known_addresses.add(sr.address)
    num_contacts = len(known_addresses)

    for i in range(10):
        if num_contacts > i * contacts_per_light:
            pixels[i] = light_colors[i]
        else:
            pixels[i] = (0,0,0)
    pixels.show()
    print('time:', time.monotonic() - start_time,
          'contacts:', num_contacts)

    led.value = True
    time.sleep(0.25)
    led.value = False
