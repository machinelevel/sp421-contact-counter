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
import gc

def main():
    """
    Initialize the modules, and then loop forever.
    """
    contact_counter = ContactCounts()
    bt_module = BluetoothModule()
    neo_module = NeopixelModule()
    eink_module = EInkModule()
    buttons = ButtonsModule()

    while True:
        contact_counter.periodic_update(buttons, neo_module)
        bt_module.periodic_update(contact_counter, buttons)
        neo_module.periodic_update(contact_counter, buttons)
        eink_module.periodic_update(contact_counter, buttons)
        gc.collect()
        time.sleep(1.0)

##################################################################
## ContactCounts is the class which tracks the main counting data
import storage

class ContactCounts:
    def __init__(self):
        self.start_time = time.time()
        self.scan_serial_number = 0
        self.sample_seconds = 0
        self.total_unique_contacts = set()
        self.current_contacts = set()
        self.prev_current_contacts = set()
        self.prev_num_total_unique_contacts = 0
        self.prior_unique_count = 0
        self.persistent_data = {'unique_counts':0,'sample_minutes':0}
        self.tried_remounting_storage = False
        self.reset_counts_timer = 0
        self.count_file_name = '/counter_data.txt'
        self.load_persistent_counter_data_at_startup()

    def periodic_update(self, buttons, neo_module=None):
        if buttons.left() and buttons.right():
            self.reset_counts_timer += 1
            if self.reset_counts_timer > 3:
                if neo_module:
                    neo_module.set_all((0,64,255))
                    time.sleep(0.5)
                self.reset_counts_to_zero()
                self.reset_counts_timer = 0
        else:
            self.reset_counts_timer = 0

        self.debug_print(buttons)

    def load_persistent_counter_data(self):
        self.prior_unique_count = 0

    def reset_counts_to_zero(self):
        self.total_unique_contacts.clear()
        self.prior_unique_count = 0
        self.sample_seconds = 0
        self.update_persistent_data()

    def update_contacts(self, new_contacts):
        self.scan_serial_number += 1
        self.prev_num_total_unique_contacts = len(self.total_unique_contacts)
        self.prev_current_contacts = self.current_contacts
        self.current_contacts = set(new_contacts)
        self.total_unique_contacts.update(self.current_contacts)
        self.update_persistent_data()

    def update_persistent_data(self):
        # TODO: optimize this for the fact that most of the time it won't change
        pd = {'unique_counts':len(self.total_unique_contacts) + self.prior_unique_count,
              'sample_minutes':self.sample_seconds // 60}
        if pd != self.persistent_data:
            self.persistent_data = pd
            self.save_persistent_data()

    def load_persistent_counter_data_at_startup(self):
        try:
            with open(self.count_file_name,'r') as f:
                # eval is unsafe, but here it's ok
                self.persistent_data.update(eval(f.read()))
                print('loaded data:',self.count_file_name,self.persistent_data)
            self.prior_unique_count = self.persistent_data['unique_counts']
            self.sample_seconds = 60 * self.persistent_data['sample_minutes']
        except:
            print('no data to load')

    def save_persistent_data(self):
        try:
            with open(self.count_file_name,'w') as f:
                f.write(str(self.persistent_data))
            print('saved data:',self.count_file_name,self.persistent_data)
        except:
            print('failed to save data')

    def timestr(self, t):
        t = int(t)
        days = t // (60 * 60 * 24)
        hrs = (t // (60 * 60)) % 24
        mins = (t // 60) % 60
        secs = t % 60
        return '{}d {}h {}m {}s'.format(days, hrs, mins, secs)

    def debug_print(self, buttons):
        self.current_debug_out = 'scan {}: {}/{}+{} contacts {} free-mem:{}'.format(self.scan_serial_number,
                len(self.current_contacts), len(self.total_unique_contacts),
                self.prior_unique_count, self.timestr(time.time() - self.start_time),
                gc.mem_free())
        print(self.current_debug_out)
        if buttons.left():
            print('Left button is down')
        if buttons.right():
            print('Right button is down')
        if buttons.switch():
            print('Switch is to the left')
##
##################################################################


##################################################################
## Buttons section: If you're not using buttons,
##                  you can just delete this whole section
class ButtonsModule:
    def __init__(self):
        self.left_button = digitalio.DigitalInOut(board.D4)
        self.right_button = digitalio.DigitalInOut(board.D5)
        self.slide_switch = digitalio.DigitalInOut(board.D7)
        self.left_button.switch_to_input(pull=digitalio.Pull.DOWN)
        self.right_button.switch_to_input(pull=digitalio.Pull.DOWN)
        self.slide_switch.switch_to_input(pull=digitalio.Pull.UP)
    def left(self):
        return self.left_button.value
    def right(self):
        return self.right_button.value
    def switch(self):
        return self.slide_switch.value
## (end of Buttons section)
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

    def periodic_update(self, cc, buttons):
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

    def periodic_update(self, cc, buttons):
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

    def set_all(self, color):
        for i in range(10):
            self.pixels[i] = color
        self.pixels.show()

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
from adafruit_epd.epd import Adafruit_EPD
from adafruit_epd import mcp_sram
import digitalio
import busio
import terminalio    # needed for tiny font

# converted at https://javl.github.io/image2cpp/
# 'font_motor_24w_p3', 24x206px
font_motor = {'width':24,
              'height':206,
              'offsets':{'0':[0+1,21],'1':[1*21+1,20],'2':[2*21+0,20],'3':[3*21+0,20],'4':[4*21-1,20], \
                         '5':[5*21-1,20],'6':[6*21-2,20],'7':[7*21-3,20],'8':[8*21-3,20],'9':[9*21-3,20]},
              'black_pixels':bytearray([ \
                0xff, 0xff, 0xff, 0xff, 0xf0, 0x1f, 0xff, 0x80, 0x07, 0xfe, 0x00, 0x03, 0xfc, 0x00, 0x03, 0xf8, \
                0x06, 0x03, 0xf8, 0x0e, 0x03, 0xf0, 0x0e, 0x03, 0xf0, 0x0c, 0x03, 0xf0, 0x1c, 0x03, 0xe0, 0x1c, \
                0x07, 0xe0, 0x18, 0x07, 0xe0, 0x38, 0x07, 0xc0, 0x38, 0x0f, 0xc0, 0x30, 0x0f, 0xc0, 0x30, 0x1f, \
                0xc0, 0x20, 0x1f, 0xe0, 0x00, 0x3f, 0xe0, 0x00, 0xff, 0xf8, 0x03, 0xff, 0xff, 0xff, 0xff, 0xff, \
                0xff, 0xff, 0xff, 0xf8, 0x0f, 0xff, 0xe0, 0x1f, 0xff, 0x80, 0x1f, 0xfe, 0x00, 0x1f, 0xfc, 0x00, \
                0x1f, 0xf8, 0x20, 0x3f, 0xf8, 0xc0, 0x3f, 0xff, 0xc0, 0x3f, 0xff, 0xc0, 0x7f, 0xff, 0x80, 0x7f, \
                0xff, 0x80, 0x7f, 0xff, 0x80, 0xff, 0xff, 0x00, 0xff, 0xff, 0x00, 0xff, 0xff, 0x01, 0xff, 0xc0, \
                0x00, 0x1f, 0x80, 0x00, 0x1f, 0x80, 0x00, 0x1f, 0xc0, 0x00, 0x3f, 0xff, 0xff, 0xff, 0xff, 0x00, \
                0x1f, 0xfe, 0x00, 0x07, 0xfe, 0x00, 0x03, 0xfe, 0x00, 0x03, 0xff, 0xfc, 0x03, 0xff, 0xfc, 0x03, \
                0xff, 0xfc, 0x03, 0xff, 0xf8, 0x07, 0xff, 0xf0, 0x0f, 0xff, 0x80, 0x1f, 0xfc, 0x00, 0x7f, 0xf0, \
                0x03, 0xff, 0xe0, 0x1f, 0xff, 0xe0, 0x3f, 0xff, 0xc0, 0x3f, 0xff, 0xc0, 0x3f, 0xff, 0xc0, 0x00, \
                0x1f, 0x80, 0x00, 0x3f, 0x80, 0x00, 0x3f, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xfe, 0x00, 0x07, \
                0xfc, 0x00, 0x03, 0xfc, 0x00, 0x03, 0xff, 0xfc, 0x03, 0xff, 0xfc, 0x03, 0xff, 0xfc, 0x03, 0xff, \
                0xf8, 0x07, 0xfe, 0x00, 0x0f, 0xfc, 0x00, 0x1f, 0xfc, 0x00, 0x1f, 0xfc, 0x00, 0x0f, 0xff, 0xf0, \
                0x0f, 0xff, 0xf0, 0x0f, 0xff, 0xe0, 0x1f, 0xff, 0xc0, 0x1f, 0x80, 0x00, 0x3f, 0x80, 0x00, 0x7f, \
                0x80, 0x00, 0xff, 0x80, 0x1f, 0xff, 0xff, 0xff, 0xff, 0xff, 0xf0, 0xff, 0xff, 0xe0, 0xff, 0xff, \
                0xc1, 0xff, 0xff, 0x83, 0xff, 0xff, 0x87, 0xff, 0xff, 0x0f, 0xff, 0xfe, 0x10, 0x0f, 0xfc, 0x30, \
                0x1f, 0xf8, 0x60, 0x1f, 0xf0, 0xe0, 0x1f, 0xe0, 0xe0, 0x3f, 0xe0, 0x00, 0x07, 0xc0, 0x00, 0x0f, \
                0xc0, 0x00, 0x0f, 0xc0, 0x00, 0x0f, 0xff, 0x80, 0x7f, 0xff, 0x80, 0x7f, 0xff, 0x80, 0xff, 0xff, \
                0x00, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xfe, 0x00, 0x01, 0xfc, 0x00, 0x01, 0xfc, 0x00, \
                0x01, 0xfc, 0x07, 0xff, 0xf8, 0x07, 0xff, 0xf8, 0x07, 0xff, 0xf8, 0x00, 0x7f, 0xf0, 0x00, 0x1f, \
                0xf0, 0x00, 0x0f, 0xf0, 0x00, 0x0f, 0xff, 0xf8, 0x0f, 0xff, 0xf8, 0x0f, 0xff, 0xf0, 0x0f, 0xff, \
                0xf0, 0x0f, 0xff, 0xe0, 0x1f, 0xc0, 0x00, 0x3f, 0x80, 0x00, 0x7f, 0x80, 0x01, 0xff, 0xc0, 0x3f, \
                0xff, 0xff, 0xff, 0xff, 0xff, 0xf0, 0x01, 0xff, 0x80, 0x01, 0xfe, 0x00, 0x01, 0xfc, 0x00, 0x01, \
                0xf8, 0x03, 0xff, 0xf8, 0x07, 0xff, 0xf0, 0x0f, 0xff, 0xf0, 0x00, 0x1f, 0xf0, 0x00, 0x0f, 0xe0, \
                0x00, 0x07, 0xe0, 0x00, 0x07, 0xe0, 0x38, 0x07, 0xc0, 0x38, 0x07, 0xc0, 0x30, 0x0f, 0xc0, 0x70, \
                0x0f, 0xc0, 0x20, 0x1f, 0xe0, 0x00, 0x3f, 0xe0, 0x00, 0x7f, 0xf8, 0x01, 0xff, 0xff, 0xff, 0xff, \
                0xff, 0xff, 0xff, 0xfc, 0x00, 0x00, 0xfc, 0x00, 0x00, 0xfc, 0x00, 0x01, 0xff, 0xfe, 0x03, 0xff, \
                0xf8, 0x07, 0xff, 0xf0, 0x0f, 0xff, 0xe0, 0x1f, 0xff, 0xc0, 0x3f, 0xff, 0xc0, 0x7f, 0xff, 0x80, \
                0x7f, 0xff, 0x00, 0xff, 0xff, 0x01, 0xff, 0xfe, 0x01, 0xff, 0xfe, 0x03, 0xff, 0xfc, 0x03, 0xff, \
                0xfc, 0x07, 0xff, 0xf8, 0x07, 0xff, 0xf8, 0x07, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, \
                0xe0, 0x1f, 0xff, 0x00, 0x07, 0xfe, 0x00, 0x03, 0xfc, 0x00, 0x03, 0xf8, 0x06, 0x03, 0xf8, 0x0e, \
                0x03, 0xf8, 0x0c, 0x03, 0xf8, 0x08, 0x07, 0xf8, 0x00, 0x0f, 0xf8, 0x00, 0x1f, 0xe0, 0x00, 0x0f, \
                0xe0, 0x18, 0x0f, 0xc0, 0x38, 0x0f, 0xc0, 0x30, 0x0f, 0x80, 0x70, 0x0f, 0x80, 0x20, 0x1f, 0xc0, \
                0x00, 0x3f, 0xc0, 0x00, 0x7f, 0xf0, 0x01, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xc0, \
                0x0f, 0xff, 0x00, 0x07, 0xfc, 0x00, 0x03, 0xf8, 0x02, 0x03, 0xf8, 0x06, 0x03, 0xf0, 0x0e, 0x03, \
                0xf0, 0x0c, 0x03, 0xf0, 0x0c, 0x03, 0xf0, 0x0c, 0x07, 0xf0, 0x00, 0x07, 0xf0, 0x00, 0x07, 0xfc, \
                0x00, 0x07, 0xff, 0xf0, 0x0f, 0xff, 0xf0, 0x0f, 0xff, 0xe0, 0x1f, 0xc0, 0x00, 0x3f, 0xc0, 0x00, \
                0x7f, 0x80, 0x01, 0xff, 0x80, 0x0f, 0xff, 0xff, 0xff, 0xff]),
}

class EInkModule:
    def __init__(self):
        self.width = 152
        self.height = 152
        self.eink_needs_update = True
        self.dirty_rect = [0, 0, self.width, self.height]
#        self.dirty_rect = None
        self.min_update_time = 15.0
        self.last_update_time = None
        self.displayed_unique_contacts = -1
        self.spi = busio.SPI(board.SCL, MOSI=board.SDA)
        self.cs_pin     = digitalio.DigitalInOut(board.RX)
        self.dc_pin     = digitalio.DigitalInOut(board.TX)
        self.sramcs_pin = None # None to use internal memory
        self.rst_pin    = digitalio.DigitalInOut(board.A3)
        self.busy_pin   = None
        self.display = EInkOverride(self.width, self.height, self.spi,
                                    cs_pin=self.cs_pin, dc_pin=self.dc_pin,
                                    sramcs_pin=self.sramcs_pin,
                                    rst_pin=self.rst_pin, busy_pin=self.busy_pin)

    def periodic_update(self, cc, buttons):
        num_unique = len(cc.total_unique_contacts) + cc.prior_unique_count
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
        d = self.display

        print("Clear buffer")
        d.fill(Adafruit_EPD.WHITE)
        d.pixel(10, 100, Adafruit_EPD.BLACK)

        print("Draw Rectangles")
        d.fill_rect(5, 5, 10, 10, Adafruit_EPD.RED)
        d.rect(0, 0, 20, 30, Adafruit_EPD.BLACK)

        print("Draw lines")
        d.line(0, 0, d.width - 1, d.height - 1, Adafruit_EPD.BLACK)
        d.line(0, d.height - 1, d.width - 1, 0, Adafruit_EPD.RED)

        # print("Draw text")
        # out_text = '{}'.format(self.displayed_unique_contacts)
        # x = 25
        # y = 70
        # w = 8 * len(out_text)
        # h = 12
        # d.text(out_text, x, y, Adafruit_EPD.BLACK)
        # self.add_dirty_rect([x, y, w, h])

        self.draw_big_number(self.displayed_unique_contacts, 76, 76, font_motor, do_clear=True)
        self.draw_big_number(self.displayed_unique_contacts, 76, 76, font_motor, do_clear=False)

        if self.dirty_rect:
            d.set_window(self.dirty_rect)
            d.display()
            self.dirty_rect = None

    def add_dirty_rect(self, r):
        if self.dirty_rect is None:
            ox1,oy1,ox2,oy2 = (self.width, self.height, 0, 0)
        else:
            ox1,oy1,ox2,oy2 = self.dirty_rect
            ox2 += ox1
            oy2 += oy1
        nx1,ny1,nx2,ny2 = r
        nx2 += nx1
        ny2 += ny1
        nx1 =  min(nx1, ox1) & 0xf8
        ny1 =  min(ny1, oy1)
        nx2 = (max(nx2, ox2) + 0x07) & 0xf8
        ny2 =  max(ny2, oy2)
        self.dirty_rect = [nx1, ny1, nx2 - nx1, ny2 - ny1]

    def draw_big_number(self, val, x, y, font, do_clear=False):
        x_step = 22-3
        y_size = 20
        text = '{}'.format(val)
        total_width = x_step * len(text)
        x -= total_width >> 1 # center it
        y -= y_size >> 1 # center it
        for c in text:
            offset = font['offsets'][c]
            self.draw_simple_image(font, x, y, invert_bits=True, do_clear=do_clear, row_start=offset[0], h=offset[1])
            x += x_step

    def draw_simple_image(self, image_data, x, y, invert_bits=False, do_clear=True, row_start=0, h=None):
        bp = image_data['black_pixels']
        w = image_data['width']
        if h is None:
            h = image_data['height']
        row_bytes = w >> 3
        self.add_dirty_rect([x, y, w, h])
#        print('len(bp)', len(bp))
        index = row_start * row_bytes
        for row in range(h):
            yy = y + row
            for bytecol in range(w >> 3):
                bits = bp[index]
                if invert_bits:
                    bits = ~bits
                index += 1
#                print('row,bytecol,index', row,bytecol,index)
                xx = x + (bytecol << 3)
                for bitcol in range(8):
                    if (bits << bitcol) & 0x80:
                        self.display.pixel(xx + bitcol, yy, Adafruit_EPD.BLACK)
                    elif do_clear:
                        self.display.pixel(xx + bitcol, yy, Adafruit_EPD.WHITE)

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
        self.ecs = cs_pin
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
            x,y,w,h = wrect
            data = []
            data.append(x & 0xf8)    # x should be the multiple of 8, the last 3 bit will always be ignored
            data.append(((x & 0xf8) + w  - 1) | 0x07)
            data.append(y >> 8)        
            data.append(y & 0xff)
            data.append((y + h - 1) >> 8)        
            data.append((y + h - 1) & 0xff)
            data.append(0x01)         # Gates scan both inside and outside of the partial window. (default) 
            self.command(_IL0373_PARTIAL_IN)
            self.command(_IL0373_PARTIAL_WINDOW, bytearray(data))

    def update(self):
        """
        COPY and OVERRIDE the Adafruit_IL0373 code, for the following reasons:
        1. Avoid waiting 15 seconds, when we could be scanning for contacts.
        """
        if self.window_rect is not None:
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

    def power_up(self):
        """
        COPY and OVERRIDE the Adafruit_IL0373 code, for the following reasons:
        1. Just so I can experiment with the startup settings
        """
        self.hardware_reset()
        self.busy_wait()

        self.command(_IL0373_POWER_SETTING, bytearray([0x03, 0x00, 0x2B, 0x2B, 0x09]))
        self.command(_IL0373_BOOSTER_SOFT_START, bytearray([0x17, 0x17, 0x17]))
        self.command(_IL0373_POWER_ON)

        self.busy_wait()
        time.sleep(0.2)

        self.command(_IL0373_PANEL_SETTING, bytearray([0xCF]))
        self.command(_IL0373_CDI, bytearray([0x37]))
        self.command(_IL0373_PLL, bytearray([0x29]))
        _b1 = self._width & 0xFF
        _b2 = (self._height >> 8) & 0xFF
        _b3 = self._height & 0xFF
        self.command(_IL0373_RESOLUTION, bytearray([_b1, _b2, _b3]))
        self.command(_IL0373_VCM_DC_SETTING, bytearray([0x0A]))
        time.sleep(0.05)

## (end of EInk section)
##################################################################


# Start the program
main()



