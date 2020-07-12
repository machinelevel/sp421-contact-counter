import board
import time
import digitalio
import neopixel
import adafruit_ble
import os
import gc

def addr_to_hex(addr):
    return ''.join('{:02x}:'.format(x) for x in addr)[:-1]
def addrs_to_hex(addrs):
    return [addr_to_hex(addr) for addr in addrs]

led = digitalio.DigitalInOut(board.D13)
led.direction = digitalio.Direction.OUTPUT

radio = adafruit_ble.BLERadio()
# the rssi is the signal strength. Play with this until
# you like the distance things are triggering
rssi = -80   # -80 is good, -20 is very close, -120 is very far away
scan_timeout = 0.25
unique_contacts=set()

# set up Bluefruit Connect (from ej)
if 1:
    from adafruit_ble.advertising.standard import ProvideServicesAdvertisement
    from adafruit_ble.services.nordic import UARTService
    from adafruit_bluefruit_connect.packet import Packet
    uart_server = UARTService()
    advertisement = ProvideServicesAdvertisement(uart_server)
    was_connected = False
    radio.start_advertising(advertisement)


pixels = neopixel.NeoPixel(board.NEOPIXEL, 10,
                               brightness=0.2, auto_write=False)
pixels[0]=(10,255,38)
pixels[1]=(0,255,242)
pixels[2]=(2,20,255)
pixels[3]=(40,2,200)
pixels[4]=(167,8,211)
pixels[5]=(185,211,12)
pixels[6]=(211,132,4)
pixels[7]=(211,66,8)
pixels[8]=(211,4,7)
pixels[9]=(255,0,0)
pixels.show()
debug_test=0
multstage=0
multipliers=[25]
multcolors=[(167,8,211),(40,2,200),(2,20,255),(0,255,242),(10,255,38),
            (185,211,12),(211,132,4),(211,66,8),(211,4,7),(255,0,0)]

def btprint(text):
    print(text)
    if radio.connected:
         uart_server.write((text+'\n').encode())

class DoubleLager:
    def __init__(self):
        self.log_file_max_size = 100 * 1024
        self.filenames = ['/data_log0.txt', '/data_log1.txt']
        self.log_index = 1
        try:
            size0 = os.stat(self.filenames[0]).st_size
            if size0 < self.log_file_max_size:
                self.log_index = 0
        except:
            pass

    def log_str(self, line):
        '''write a string to the log'''
        try:
            with open(self.filenames[self.log_index],'a') as f:
                f.write(line+'\n')
                if f.tell() > self.log_file_max_size:
                    self.log_index = (self.log_index + 1) & 1
                    with open(self.filenames[self.log_index],'w') as f2:
                        pass
        except Exception as ex:
            btprint('failed to write log: {}'.format(ex))

    def log_dump(self, bt=None):
        '''Read the logs out to stdout and bt-connect'''
        for i in range(2):
            index = (self.log_index + i + 1) & 1
            try:
                with open(self.filenames[index],'r') as f:
                    for line in f:
                        btprint(line)
            except Exception as ex:
                btprint('failed to read log: {}'.format(ex))

lager = DoubleLager()
btprint('my new project!')
lager.log_str('startup,{},{}'.format(int(time.monotonic()), len(unique_contacts)))
while True:
    gc.collect()
    time.sleep(1.0)
    led.value = True
    time.sleep(0.2)
    led.value = False
    scan_result = radio.start_scan(timeout=scan_timeout,
                                            minimum_rssi=rssi)
    contacts = [s.address.address_bytes for s in scan_result]
    for addr in contacts:
        if not addr in unique_contacts:
            unique_contacts.add(addr)
            lager.log_str('add,{},{},{}'.format(int(time.monotonic()),
                                                len(unique_contacts),
                                                addr_to_hex(addr)))

    num_contacts=len(unique_contacts)+debug_test
    debug_text = '{},{} // uniques:{} current:{} free mem:{}k'.format(len(contacts),
                                                                      len(unique_contacts),
                                                                      len(unique_contacts),
                                                                      addrs_to_hex(contacts),
                                                                      int(gc.mem_free() // 1024))
    btprint(debug_text)

    #1-50 color 1 (increments of 5)
    #51-250 color 2 (increments of 25)
    #251-1000 color 3 (increments of 100)
    #1001-2500 color 4 (increments of 250)


    if multstage<len(multipliers)-1:
        if num_contacts>10*multipliers[multstage]:
            multstage+=1

    lightcolor=multcolors[multstage]
    contacts_per_light=multipliers[multstage]

    for i in range(10):
        if num_contacts>i*contacts_per_light:
            pixels[i]=multcolors[i]
        else:
            pixels[i]=(0,0,0)

    pixels.show()

    # update Bluefruit Connect
    if radio.connected:
        was_connected = True
        uart_server.write(debug_text.encode())
        if uart_server.in_waiting:
            raw_bytes = uart_server.read(uart_server.in_waiting)
            text = raw_bytes.decode().strip()
            btprint("RX:", text)
            if '143.all' in text:
                btprint('all uniques:')
                for i,addr in enumerate(sorted(list(unique_contacts))):
                    btprint(' {}: {}'.format(i,addrs_to_hex([addr])))
            elif '143.log' in text:
                lager.log_dump()
    elif was_connected:
        was_connected = False
        radio.start_advertising(advertisement)

    #debug_test+=50
