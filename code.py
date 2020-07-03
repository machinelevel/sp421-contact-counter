"""
Secret Plan #421: Contact Counter
by Eric and Sue Johnston, inventions@machinelevel.com
3 July 2020

This program was written for the Adafruit C.P. Bluefruit
Line a radiation exposure badge worn by powerplant workers,
it measures exposure to close-range contact with other people
(actually their Bluetooth gizmos). It's not precise, but it's
useful.

The counter reports the number of unique Bluetooth contacts, so:
  Sitting at home all day: 10
  Walking around town with friends: 300
  Rock concert or baseball game: 10,000

The hope is that these numbers can help evaluate risk of
contracting and spreading diseases such as influenza and COVID-19

License:
    This software is free (like free speech AND free beer)
    It was built partially from awesome scraps and samples,
    which can be found in the "references" folder. Thx for those!
    Do anything you like with this, but please use for good.
    If you use it, drop us a note and say hi!
    There is no warranty at all, use at your own risk.
"""
import time
from adafruit_ble import BLERadio
import board
import neopixel
import displayio
import digitalio
import terminalio

def main():
    """
    Initialize the modules, and then loop forever.
    """
    contact_counter = ContactCounts()
    bt_module = BluetoothModule()
    neo_module = NeopixelModule()

    while True:
        bt_module.periodic_update(contact_counter)
        neo_module.periodic_update(contact_counter)
        contact_counter.debug_print()
        time.sleep(1.0)

##################################################################
## Bluetooth section: If you're not using Bluetooth,
##                    you can just delete this whole section
class ContactCounts:
    def __init__(self):
        self.start_time = time.time()
        self.scan_serial_number = 0
        self.total_unique_contacts = set()
        self.current_contacts = set()
        self.prev_current_contacts = set()
        self.prev_num_total_unique_contacts = 0

    def update_contacts(self, new_contacts):
        self.scan_serial_number += 1
        self.prev_num_total_unique_contacts = len(self.total_unique_contacts)
        self.prev_current_contacts = self.current_contacts
        self.current_contacts = set(new_contacts)
        self.total_unique_contacts.update(self.current_contacts)

    def timestr(self, t):
        t = int(t)
        days = t // (60 * 60 * 24)
        hrs = (t // (60 * 60)) % 24
        mins = (t // 60) % 60
        secs = t % 60
        return '{}d {}h {}m {}s'.format(days, hrs, mins, secs)

    def debug_print(self):
        print('scan {}: {}/{} contacts {}'.format(self.scan_serial_number,
                len(self.current_contacts), len(self.total_unique_contacts),
                self.timestr(time.time() - self.start_time)))


##################################################################

##################################################################
## Bluetooth section: If you're not using Bluetooth,
##                    you can just delete this whole section
class BluetoothModule:
    def __init__(self):
        self.radio = BLERadio()
        # the rssi is the signal strength. Play with this until
        # you like the distance things are triggering
        self.rssi = -80   # -80 is good, -20 is very close, -120 is very far away
        self.scan_timeout = 0.25

    def periodic_update(self, cc):
        scan_result = self.radio.start_scan(timeout=self.scan_timeout,
                                            minimum_rssi=self.rssi)
        contacts = [s.address for s in scan_result]
        cc.update_contacts(contacts)

## (end of Bluetooth section)
##################################################################

##################################################################
## Neopixel section: If you're not using Neopixels,
##                   you can just delete this whole section
class NeopixelModule:
    def __init__(self):
        self.pixels = neopixel.NeoPixel(board.NEOPIXEL, 10,
                                        brightness=0.2, auto_write=False)
        self.pixels_need_update = True

    def periodic_update(self, cc):
        if len(cc.current_contacts) != len(cc.prev_current_contacts):
            self.pixels_need_update = True

        if self.pixels_need_update:
            num_contacts = len(cc.current_contacts)
            for i in range(10):
                if i < num_contacts:
                    self.pixels[i] = self.colorwheel255(100 - i * 10)
                else:
                    self.pixels[i] = (0,0,0)
            self.pixels.show()
            self.pixels_need_update = False

    def colorwheel255(self, pos):
        # Input a value 0 to 255 to get a color value.
        # The colors are a transition r - g - b - back to r.
        if pos < 0 or pos > 255:
            return (0, 0, 0)
        if pos < 85:
            return (255 - pos * 3, pos * 3, 0)
        if pos < 170:
            pos -= 85
            return (0, 255 - pos * 3, pos * 3)
        pos -= 170
        return (pos * 3, 0, 255 - pos * 3)

## (end of Neopixel section)
##################################################################

main()



