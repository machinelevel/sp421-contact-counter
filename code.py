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
import board

def main():
    """
    Initialize the modules, and then loop forever.
    """
    contact_counter = ContactCounts()
    bt_module = BluetoothModule()
    neo_module = NeopixelModule()
    eink_module = EInkModule()

    while True:
        bt_module.periodic_update(contact_counter)
        neo_module.periodic_update(contact_counter)
        eink_module.periodic_update(contact_counter)
        contact_counter.debug_print()
        time.sleep(1.0)

##################################################################
## ContactCounts is the class which tracks the main counting data
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
##
##################################################################

##################################################################
## Bluetooth section: If you're not using Bluetooth,
##                    you can just delete this whole section
import adafruit_ble

class BluetoothModule:
    def __init__(self):
        self.radio = adafruit_ble.BLERadio()
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
import neopixel

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




##################################################################
## EInk section: If you're not using EInk,
##               you can just delete this whole section
from adafruit_epd.il0373 import Adafruit_IL0373
from adafruit_epd import mcp_sram
import digitalio
import busio
import terminalio    # needed for tiny font

class EInkModule:
    def __init__(self):
        self.width = 152
        self.height = 152
        self.eink_needs_update = True
        self.dirty_rect = [0, 0, self.width, self.height]
        self.min_update_time = 15.0
        self.last_update_time = None
        self.displayed_unique_contacts = -1
        self.spi = busio.SPI(board.SCL, MOSI=board.SDA)
        self.cs_pin     = digitalio.DigitalInOut(board.RX)
        self.dc_pin     = digitalio.DigitalInOut(board.TX)
        self.sramcs_pin = None # None to use internal memory
        self.rst_pin    = digitalio.DigitalInOut(board.A3)
        self.busy_pin   = None
        self.ink = EInkOverride(self.width, self.height, self.spi,
                                cs_pin=self.cs_pin, dc_pin=self.dc_pin,
                                sramcs_pin=self.sramcs_pin,
                                rst_pin=self.rst_pin, busy_pin=self.busy_pin)

    def periodic_update(self, cc):
        num_unique = len(cc.total_unique_contacts)
        if num_unique != self.displayed_unique_contacts:
            self.eink_needs_update = True;
        update_time_ok = self.last_update_time is None or \
                         time.time() - self.last_update_time > self.min_update_time

        if self.eink_needs_update and update_time_ok:
            self.displayed_unique_contacts = num_unique
            self.draw_everything(cc)
            self.eink_needs_update = False
            self.last_update_time = time.time()

    def draw_everything(self, cc):
        # draw stuff here
        self.dirty_rect = None
        self.add_dirty_rect([64, 64, 64, 64])
        self.ink.set_window(self.dirty_rect)
        self.ink.display()
        self.dirty_rect = None

    def add_dirty_rect(self, r):
        if self.dirty_rect is None:
            self.dirty_rect = [self.width, self.height, 0, 0]
        x1 = self.dirty_rect[0]
        y1 = self.dirty_rect[1]
        x2 = x1 + self.dirty_rect[2]
        y2 = y1 + self.dirty_rect[3]
        self.dirty_rect[0] = min(r[0], x1) & 0xf8
        self.dirty_rect[1] = min(r[1], y1)
        self.dirty_rect[2] = ((max(r[0] + r[2], x2) - x1) + 0x07) & 0xf8;
        self.dirty_rect[3] =  (max(r[1] + r[3], y2) - y1);

_IL0373_PANEL_SETTING = const(0x00)
_IL0373_POWER_SETTING = const(0x01)
_IL0373_POWER_OFF = const(0x02)
_IL0373_POWER_OFF_SEQUENCE = const(0x03)
_IL0373_POWER_ON = const(0x04)
_IL0373_POWER_ON_MEASURE = const(0x05)
_IL0373_BOOSTER_SOFT_START = const(0x06)
_IL0373_DEEP_SLEEP = const(0x07)
_IL0373_DTM1 = const(0x10)
_IL0373_DATA_STOP = const(0x11)
_IL0373_DISPLAY_REFRESH = const(0x12)
_IL0373_DTM2 = const(0x13)
_IL0373_PDTM1 = const(0x14)
_IL0373_PDTM2 = const(0x15)
_IL0373_PDRF = const(0x16)
_IL0373_LUT1 = const(0x20)
_IL0373_LUTWW = const(0x21)
_IL0373_LUTBW = const(0x22)
_IL0373_LUTWB = const(0x23)
_IL0373_LUTBB = const(0x24)
_IL0373_PLL = const(0x30)
_IL0373_CDI = const(0x50)
_IL0373_RESOLUTION = const(0x61)
_IL0373_VCM_DC_SETTING = const(0x82)
_IL0373_PARTIAL_WINDOW = const(0x90)
_IL0373_PARTIAL_IN = const(0x91)
_IL0373_PARTIAL_OUT = const(0x92)

class EInkOverride(Adafruit_IL0373):
    def __init__(self, width, height, spi, cs_pin, dc_pin,
                 sramcs_pin, rst_pin, busy_pin):
        self.window_rect = None
        super(EInkOverride, self).__init__(width, height, spi,
            cs_pin=cs_pin, dc_pin=dc_pin, sramcs_pin=sramcs_pin,
            rst_pin=rst_pin, busy_pin=busy_pin)

    def set_window(self, wrect):
        if wrect is None:
            self.window_rect = None
        else:
            self.window_rect = [x for x in wrect]

    def start_partial_window(self, wrect):
        if wrect is not None:
            if self.spi_device.try_lock():
                x,y,w,h = wrect
                time.sleep(0.002)
                data = []
                data.append(x & 0xf8)    # x should be the multiple of 8, the last 3 bit will always be ignored
                data.append(((x & 0xf8) + w  - 1) | 0x07)
                data.append(y >> 8)        
                data.append(y & 0xff)
                data.append((y + h - 1) >> 8)        
                data.append((y + h - 1) & 0xff)
                data.append(0x01)         # Gates scan both inside and outside of the partial window. (default) 
                self.command(_IL0373_PARTIAL_IN)
                self.command(_IL0373_PARTIAL_WINDOW, data)
                time.sleep(0.002)
                self.spi_device.unlock()

    def update(self):
        """
        COPY and OVERRIDE the Adafruit_IL0373 code, for the following reasons:
        1. Avoid waiting 15 seconds, when we could be scanning for contacts.
        """
        if self.window_rect is not None:
            x,y,w,h = self.window_rect
            if w > 0 and h > 0:
                self.command(_IL0373_DISPLAY_REFRESH)

    def display(self):
        """
        COPY and OVERRIDE the Adafruit_IL0373 code, for the following reasons:
        1. Allow a partial-screen refresh
        """
        if self.window_rect is None:
            return

        self.power_up()

        self.set_ram_address(0, 0)

        if self.sram:
            while not self.spi_device.try_lock():
                time.sleep(0.01)
            self.sram.cs_pin.value = False
            # send read command
            self._buf[0] = mcp_sram.Adafruit_MCP_SRAM.SRAM_READ
            # send start address
            self._buf[1] = 0
            self._buf[2] = 0
            self.spi_device.write(self._buf, end=3)
            self.spi_device.unlock()

        # first data byte from SRAM will be transfered in at the
        # same time as the EPD command is transferred out
        databyte = self.write_ram(0)

        while not self.spi_device.try_lock():
            time.sleep(0.01)
        self._dc.value = True

        if self.sram:
            for _ in range(self._buffer1_size):
                databyte = self._spi_transfer(databyte)
            self.sram.cs_pin.value = True
        else:
            for databyte in self._buffer1:
                self._spi_transfer(databyte)

        self._cs.value = True
        self.spi_device.unlock()
        time.sleep(0.002)

        if self.sram:
            while not self.spi_device.try_lock():
                time.sleep(0.01)
            self.sram.cs_pin.value = False
            # send read command
            self._buf[0] = mcp_sram.Adafruit_MCP_SRAM.SRAM_READ
            # send start address
            self._buf[1] = (self._buffer1_size >> 8) & 0xFF
            self._buf[2] = self._buffer1_size & 0xFF
            self.spi_device.write(self._buf, end=3)
            self.spi_device.unlock()

        if self._buffer2_size != 0:
            # first data byte from SRAM will be transfered in at the
            # same time as the EPD command is transferred out
            databyte = self.write_ram(1)

            while not self.spi_device.try_lock():
                time.sleep(0.01)
            self._dc.value = True

            if self.sram:
                for _ in range(self._buffer2_size):
                    databyte = self._spi_transfer(databyte)
                self.sram.cs_pin.value = True
            else:
                for databyte in self._buffer2:
                    self._spi_transfer(databyte)

            self._cs.value = True
            self.spi_device.unlock()
        else:
            if self.sram:
                self.sram.cs_pin.value = True

        self.start_partial_window(self.window_rect)
        self.update()
## (end of Neopixel section)
##################################################################


# Start the program
main()



