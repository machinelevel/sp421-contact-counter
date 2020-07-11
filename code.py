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

def addrs_to_hex(addrs):
    return [''.join('{:02x}:'.format(x) for x in addr)[:-1] for addr in addrs]

def main():
    """
    Initialize the modules, and then loop forever.
    """
    print('free memory at startup:',gc.mem_free())

    contact_counter = ContactCounts()
    bt_module = BluetoothModule()
    neo_module = NeopixelModule()
    eink_module = EInkModule()
    buttons = ButtonsModule()

    while True:
        contact_counter.periodic_update(buttons, neo_module, eink_module)
        bt_module.periodic_update(contact_counter, buttons)
        neo_module.periodic_update(contact_counter, buttons)
        eink_module.periodic_update(contact_counter, buttons)
        contact_counter.debug_print(buttons)
        gc.collect()
        time.sleep(1.0)

##################################################################
## Settings: common adjustables for this program

# the rssi is the signal strength. Play with this until
# you like the distance things are triggering
setting_bt_rssi = -80 # -80 is good, -20 is very close, -120 is very far away
setting_bt_timeout = 0.25 # scan for this many seconds each time
setting_end_encounter_time = 5 * 60 # End an encounter after this many seconds of not seeing the device


##################################################################
## ContactCounts is the class which tracks the main counting data
#import storage

class Encounter:
    '''
    An encounter is a period of contact with someone else's device 
    '''
    def __init__(self, is_new_device):
        self.first_seen = time.monotonic() # When did this contact start
        self.last_seen = time.monotonic()  # When did we last see this device
        self.contact_duration = 0.0        # Integration over time
        self.is_new_device = is_new_device # First contact for this device

class Bloom:
    '''
    The bloom is a structure which tracks whether or not we've seen an address before
    '''
    def __init__(self, filename):
        self.filename = filename
        self.do_verify = False
        self.bits = bytearray(24 * 1024)
        self.clear()
        self.load_at_startup()

    def load_at_startup(self):
        # try to load the data
        try:
            with open(self.filename,'rb') as f:
                rsize = 256
                pos = 0
                while pos < len(self.bits):
                    data = f.read(rsize)
                    self.bits[pos:pos+rsize] = data
                    pos += rsize
            print('Loaded bloom file ok')
        except Exception as ex:
            print('Unable to load bloom file, creating new',ex)
            self.save()

    def save(self, byte_list=None):
        if byte_list is None:
            try:
                with open(self.filename,'wb') as f:
                    f.write(self.bits)
                print('Saved complete bloom file')
            except Exception as ex:
                print('Unable to save full bloom file',ex)
        else:
            try:
                with open(self.filename,'rb+') as f:
                    for pos in byte_list:
                        f.seek(pos)
                        f.write(self.bits[pos:pos+1])
                print('Saved bloom bytes',byte_list)
            except Exception as ex:
                print('Unable to save partial bloom file',ex)
        self.verify()

    def verify(self):
        if self.do_verify:
            try:
                test_size = 256
                test_offset = 0
                with open(self.filename,'rb') as f:
                    while test_offset < len(self.bits):
                        chk = f.read(test_size)
                        assert chk == self.bits[test_offset:test_offset+test_size],'verify mismatch'
                        test_offset += test_size
                print('Verified bloom file ok')
            except Exception as ex:
                print('Unable to verify bloom file',ex)

    def clear(self):
        for i in range(len(self.bits)):
            self.bits[i] = 0

    def add(self, addr):
        update_bytes = []
        is_new = False
        for field in range(3):
            bit_index = (addr[field * 2] << 8) | addr[field * 2 + 1]
            pos = (bit_index >> 3) + field * 8192
            mask = 1 << (bit_index & 7)
            if (self.bits[pos] & mask) == 0:
                self.bits[pos] |= mask
                update_bytes.append(pos)
                is_new = True
        if is_new:
            self.save(update_bytes)
        return is_new

class HistoryBar:
    def __init__(self, filename):
        self.filename = filename
        self.num_columns = 8 * 15 # one column every 4 minutes for 8 hours
        self.data = bytearray(self.num_columns * 2)
        self.update_period = 60#4 * 60
        self.draw_period = 4*60#4 * 60
        self.start_index = 0
        self.last_update_time = time.monotonic()
        self.last_draw_time = time.monotonic()
        self.load_at_startup()

    def periodic_update(self, cc):
        t = time.monotonic()
        if t - self.last_update_time > self.update_period:
            self.last_update_time = t
            count_to_display = 0
            for enc in cc.current_encounters.values():
                if t - enc.last_seen < self.update_period:
                    count_to_display += 1
            next_index = self.start_index
            self.start_index += 1
            self.start_index %= self.num_columns
            self.set_value(next_index, count_to_display)
            self.save()
            print('updated historybar',next_index,count_to_display)

    def draw_update(self, eink):
        t = time.monotonic()
        if t - self.last_draw_time > self.draw_period:
            print('drawing historybar...')
            self.last_draw_time = t
            x = (eink.width - self.num_columns) >> 1
            y = 16
            w = self.num_columns
            h = 32
            tw = 6
            th = 8
            basey = y + h - 1
            d = eink.display
            d.fill_rect(x, y, w, h, Adafruit_EPD.WHITE)
            d.fill_rect(x-1, basey, w+2, 1, Adafruit_EPD.BLACK)
            maxval = 0
            for i in range(self.num_columns):
                maxval = max(maxval, self.get_value(i))
            if maxval > 0:
                if maxval < 10:
                    maxval = 10
                scale = h / maxval
                for i in range(self.num_columns):
                    dx = (i + self.num_columns - self.start_index) % self.num_columns
                    dsize = int(scale * self.get_value(i))
                    if dsize:
                        d.fill_rect(x+dx, basey - dsize, 1, dsize, Adafruit_EPD.BLACK)
            maxtext = '{}'.format(int(maxval))
            d.text(maxtext, x+w-tw*len(maxtext), y, Adafruit_EPD.BLACK)
            d.text('2 hours', x, y + h + 1, Adafruit_EPD.BLACK)
            d.set_window((x-1,y,w+2,h + th + 1))
            d.display()

    def set_value(self, index, value):
        i = index << 1
        self.data[i] = value & 0xff
        self.data[i + 1] = (value >> 8) & 0xff

    def get_value(self, index):
        i = index << 1
        return self.data[i] | (self.data[i + 1] << 8)

    def load_at_startup(self):
        # try to load the data
        try:
            with open(self.filename,'rb') as f:
                in_bytes = f.read()
                if len(in_bytes) == len(self.data):
                    for i in range(len(self.data)):
                        self.data[i] = in_bytes[i]
            print('Loaded historybar file ok')
        except Exception as ex:
            print('Unable to load historybar file',ex)

    def save(self, index_list=None):
        try:
            si = self.start_index << 1
            with open(self.filename,'wb') as f:
                f.write(self.data[si:])
                if si > 0:
                    f.write(self.data[:si])
            print('Saved historybar file')
        except Exception as ex:
            print('Unable to save full historybar file',ex)

class ContactCounts:
    def __init__(self):
        self.startup_time = time.monotonic()
        self.current_encounters = {}
        self.persistent_data = {'unique_counts':0,'sample_seconds':0}
        self.count_file_name = '/data_counter.txt'
        self.need_save = False
        self.is_low_power = False
        self.bloom = Bloom('/data_bloom.bin')
        self.reset_counts_to_zero()
        self.load_persistent_counter_data_at_startup()
        self.reset_button_hold_timer = 0
        self.history_bar = HistoryBar('/data_historybar.bin')
        # self.histogram = Histogram('/histogram.bin')

    def periodic_update(self, buttons, neo_module=None, eink_module=None):
        if self.history_bar is not None:
            self.history_bar.periodic_update(self)
            self.history_bar.draw_update(eink_module)

        if self.need_save:
            self.save_persistent_data()
            self.need_save = False

        # enggage power saver
        if buttons.switch() != self.is_low_power:
            self.set_low_power(buttons.switch(), neo_module, eink_module)

        # hold both buttons down to reset counts
        if buttons.left() and buttons.right():
            self.reset_button_hold_timer += 1
            if self.reset_button_hold_timer > 3:
                if neo_module:
                    neo_module.set_all((0,64,255))
                    time.sleep(0.25)
                    neo_module.set_all((0,0,0))
                self.reset_counts_to_zero()
                self.save_persistent_data()
                self.bloom.clear()
                self.bloom.save()
                self.reset_button_hold_timer = 0
        else:
            self.reset_button_hold_timer = 0

    def set_low_power(self, low_power, neo_module=None, eink_module=None):
        self.is_low_power = low_power
        if self.is_low_power:
            print('(switch to low power mode)')
        else:
            print('(switch to high power mode)')
        if neo_module:
            neo_module.set_low_power(low_power)
        if eink_module:
            eink_module.set_low_power(low_power)

    def reset_counts_to_zero(self):
        self.current_encounters.clear()
        self.sample_last_time = self.sample_start_time = time.monotonic()
        self.scan_serial_number = 0
        self.persistent_data['unique_counts'] = 0
        self.persistent_data['sample_seconds'] = 0

    def check_if_new(self, addr):
        is_new = self.bloom.add(addr)
        if is_new:
            self.persistent_data['unique_counts'] += 1
            self.need_save = True
        return is_new

    def get_total_unique(self):
        return self.persistent_data['unique_counts']

    def update_contacts(self, new_contacts):
        this_time = time.monotonic()
        self.persistent_data['sample_seconds'] += this_time - self.sample_last_time
        for addr in new_contacts:
            contact = self.current_encounters.get(addr, None)
            if contact is not None:
                contact.last_seen = this_time
                contact.contact_duration += this_time - self.sample_last_time
            else:
                self.current_encounters[addr] = Encounter(self.check_if_new(addr))
        self.sample_last_time = this_time

        # Delete any old contacts
        for addr in list(self.current_encounters.keys()):
            if this_time > self.current_encounters[addr].last_seen + setting_end_encounter_time:
                del self.current_encounters[addr]

    def load_persistent_counter_data_at_startup(self):
        try:
            with open(self.count_file_name,'r') as f:
                # eval is unsafe, but here it's ok
                self.persistent_data.update(eval(f.read()))
                print('loaded data:',self.count_file_name,self.persistent_data)
        except Exception as ex:
            print('no data to load',ex)

    def save_persistent_data(self):
        try:
            with open(self.count_file_name,'w') as f:
                f.write(str(self.persistent_data))
            print('saved data:',self.count_file_name,self.persistent_data)
        except Exception as ex:
            print('failed to save data',ex)

    def timestr(self, t):
        t = int(t)
        days = t // (60 * 60 * 24)
        hrs = (t // (60 * 60)) % 24
        mins = (t // 60) % 60
        secs = t % 60
        return '{}d {}h {}m {}s'.format(days, hrs, mins, secs)

    def debug_print(self, buttons):
        self.current_debug_out = 'scan {}: {}/{} contacts t={} free-mem:{}'.format(self.scan_serial_number,
                len(self.current_encounters), self.persistent_data['unique_counts'],
                self.timestr(self.persistent_data['sample_seconds']),
                gc.mem_free())
        if not self.is_low_power:
            print(self.current_debug_out)
            if buttons.left():
                print('Left button is down')
            if buttons.right():
                print('Right button is down')
            # if buttons.switch():
            #     print('Switch is to the left')
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
from adafruit_ble.advertising.standard import ProvideServicesAdvertisement
from adafruit_ble.services.nordic import UARTService
from adafruit_bluefruit_connect.packet import Packet
# Only the packet classes that are imported will be known to Packet.
# from adafruit_bluefruit_connect.color_packet import ColorPacket

class BluetoothModule:
    def __init__(self):
        self.radio = adafruit_ble.BLERadio()

        # set up Bluefruit Connect
        self.uart_server = UARTService()
        self.advertisement = ProvideServicesAdvertisement(self.uart_server)
        self.was_connected = False
        self.radio.start_advertising(self.advertisement)

    def periodic_update(self, cc, buttons):
        scan_result = self.radio.start_scan(timeout=setting_bt_timeout,
                                            minimum_rssi=setting_bt_rssi)
        contacts = [s.address.address_bytes for s in scan_result]
        cc.update_contacts(contacts)

        # update Bluefruit Connect
        if self.radio.connected:
            self.was_connected = True
            # packet = Packet.from_stream(self.uart_server)
            # if isinstance(packet, ColorPacket):
            #     print(packet.color)
            # INCOMING (RX) check for incoming text
            if self.uart_server.in_waiting:
                raw_bytes = self.uart_server.read(self.uart_server.in_waiting)
                text = raw_bytes.decode().strip()
                # print("raw bytes =", raw_bytes)
                print("RX:", text)
                if '143.all' in text:
                    t = time.monotonic()
                    order = sorted([(c.first_seen, addr) for addr,c in cc.current_encounters.items()])
                    for i,o in enumerate(order):
                        addr = o[1]
                        enc = cc.current_encounters[addr]
                        first = int((t - enc.first_seen) / 60)
                        last = int((t - enc.last_seen) / 60)
                        text = '{}: {} {}m {}m\n'.format(i, addrs_to_hex([addr]), first, last)
                        self.uart_server.write(text.encode())

            # OUTGOING (TX) periodically send text
            text = cc.current_debug_out
            #text = '\n{},{}\n'.format(val1, val2)
            #print("TX:", text.strip())
            self.uart_server.write((text+'\n').encode())

        elif self.was_connected:
            self.was_connected = False
            self.radio.start_advertising(self.advertisement)



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
        self.current_displayed_count = -1

    def periodic_update(self, cc, buttons):
        if cc.is_low_power:
            return

        # One light for each encounter still active as of a minute ago
        t = time.monotonic()
        count_to_display = 0
        for enc in cc.current_encounters.values():
            if t - enc.last_seen < 60:
                count_to_display += 1

        if count_to_display != self.current_displayed_count:
            self.pixels_need_update = True

        if self.pixels_need_update:
            self.current_displayed_count = count_to_display
            for i in range(10):
                if i < self.current_displayed_count:
                    self.pixels[i] = self.colorwheel255(100 - i * 10)
                else:
                    self.pixels[i] = (0,0,0)
            self.pixels.show()
            self.pixels_need_update = False

    def set_low_power(self, low_power):
        if low_power:
            self.set_all((0,0,0))
        else:
            self.pixels_need_update = True

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
        self.displaying_low_batt_warning = False
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
        num_unique = cc.get_total_unique()
        if num_unique != self.displayed_unique_contacts:
            self.eink_needs_update = True;
        update_time_ok = self.last_update_time is None or \
                         time.monotonic() - self.last_update_time > self.min_update_time

        self.check_low_battery_warning(cc)

        if self.eink_needs_update and update_time_ok:
            self.displayed_unique_contacts = num_unique
            self.draw_everything(cc)
            self.eink_needs_update = False
            self.last_update_time = time.monotonic()

    def check_low_battery_warning(self, cc):
        low_batt = self.display.check_low_battery_warning()
        if low_batt:
            print('LOW BATTERY WARNING:')
        if self.displaying_low_batt_warning != low_batt:
            self.displaying_low_batt_warning = low_batt
            message = 'LOW BATTERY' if low_batt else '           '
            self.draw_tiny_text((24, 24, message))
            if low_batt:
                time.sleep(15)


    def set_low_power(self, low_power):
        if low_power:
            self.min_update_time = 60 * 5
            self.display.busy_wait()
            time.sleep(0.2)
            self.display.power_down()
        else:
            self.min_update_time = 15.0
            self.eink_needs_update = True
        # Show the icon
        message = 'BATT SAVER MODE' if low_power else '               '
        self.draw_tiny_text((24, 36, message))
        time.sleep(5)

    def draw_tiny_text(self, ttxt):
        x,y,message = ttxt
        w = len(message) * 6
        h = 8
        d = self.display
        d.fill_rect(x, y, w, h, Adafruit_EPD.WHITE)
        d.text(message, x, y, Adafruit_EPD.BLACK)
        d.set_window((x,y,w,h))
        d.display()

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

        print('draw big number')
        self.draw_big_number(self.displayed_unique_contacts, 76, 76, font_motor, do_clear=True)
        self.draw_big_number(self.displayed_unique_contacts, 76, 76, font_motor, do_clear=False)

        if self.dirty_rect:
            d.set_window(self.dirty_rect)
            d.display()
            self.dirty_rect = None
            if cc.is_low_power:
                d.busy_wait()
                time.sleep(0.2)
                d.power_down()
        print('draw done')

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

_IL0373_LOW_POWER_DETECT = const(0x51)

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

    def check_low_battery_warning(self):
        low_batt = self.command(_IL0373_LOW_POWER_DETECT)
        return bool(low_batt)

    def update(self):
        """
        COPY and OVERRIDE the Adafruit_IL0373 code, for the following reasons:
        1. Avoid waiting 15 seconds, when we could be scanning for contacts.
        """
        if self.window_rect is not None:
            print('update()...')
            self.command(_IL0373_DISPLAY_REFRESH)

    def display(self):
        """
        COPY and OVERRIDE the Adafruit_IL0373 code, for the following reasons:
        1. Allow a partial-screen refresh
        """
        if self.window_rect is None:
            return

        print('display()...')

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



