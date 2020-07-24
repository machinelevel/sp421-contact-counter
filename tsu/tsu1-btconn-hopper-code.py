import board
import time
import digitalio
import neopixel
import adafruit_ble
import _bleio
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
scan_timeout = 1.0

# set up Bluefruit Connect (from ej)
if 1:
    from adafruit_ble.advertising.standard import ProvideServicesAdvertisement
    from adafruit_ble.services.nordic import UARTService
    from adafruit_bluefruit_connect.packet import Packet
    uart_server = UARTService()
    advertisement = ProvideServicesAdvertisement(uart_server)
    was_connected = False
    radio.start_advertising(advertisement)

def make_thumbprint(contact):
    keys = sorted(list(contact.data_dict.keys()))
    sizes = [len(contact.data_dict[k]) for k in keys]
    return bytes([contact.address.type] + keys + sizes)

class Encounter:
    def __init__(self, hopper_thumbprint):
        self.first_seen = time.monotonic()  # When did this contact start
        self.last_seen = time.monotonic()   # When did we last see this device
        self.thumbprint = hopper_thumbprint # to help identify hopper-buddies

total_unique_contacts = 0 # The big important number
known_statics = set()     # All of the non-hoppers we've seen already
current_encounters = {}   # All of the currently active encounters

def update_contacts(new_contacts):
    global total_unique_contacts
    global known_statics
    global current_encounters

    this_time = time.monotonic()
    stale_time = this_time - 5 * 60 # if no pings for 5 min, drop a contact

    # update times for old contacts
    new_addrs = {nc.address.address_bytes:nc for nc in new_contacts} # removes dupes
    old_hoppers = {}
    for addr in list(current_encounters.keys()):
        encounter = current_encounters[addr]
        if addr in new_addrs:
            encounter.last_seen = this_time
            if encounter.thumbprint:
                encounter.thumbprint = make_thumbprint(new_addrs[addr])
            del new_addrs[addr]
        else:
            if encounter.last_seen < stale_time:
                del current_encounters[addr]
            else:
                if encounter.thumbprint:
                    old_hoppers[addr] = encounter

    # now for any addresses which are new, create/migrate contacts
    for addr,nc in new_addrs.items():
        is_hopper = nc.address.type == _bleio.Address.RANDOM_PRIVATE_RESOLVABLE or nc.address.type == _bleio.Address.RANDOM_PRIVATE_NON_RESOLVABLE
        if is_hopper:
            encounter = None
            thumbprint = make_thumbprint(nc)
            for haddr,hopper in old_hoppers.items():
                if hopper.thumbprint == thumbprint:
                    # migrate the hopper
                    del old_hoppers[haddr]
                    del current_encounters[haddr]
                    encounter = hopper
                    btprint('--> Migrate hopper {}->{}'.format(addr_to_hex(haddr), addr_to_hex(addr)))
                    break
            if encounter is None:
                encounter = Encounter(thumbprint)
                total_unique_contacts += 1
                btprint('--> New hopper {}'.format(addr_to_hex(addr)))
        else:
            encounter = Encounter(None)
            if not addr in known_statics:
                total_unique_contacts += 1
                known_statics.add(addr)
                btprint('--> New static {}'.format(addr_to_hex(addr)))
        current_encounters[addr] = encounter



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

btprint('my new project!')
while True:
    gc.collect()
    if gc.mem_free() < 5000:
        known_statics.clear()
    led.value = True
    time.sleep(0.25)
    led.value = False
#    t1 = time.monotonic()
    scan_result = radio.start_scan(timeout=scan_timeout, minimum_rssi=rssi)
    items = list(scan_result)
#    print(time.monotonic() - t1, len(items), addrs_to_hex([item.address.address_bytes for item in items]))
    update_contacts(items)

    num_contacts=total_unique_contacts+debug_test
    debug_text = '{},{} // uniques:{} current:{} free mem:{}k'.format(total_unique_contacts,
                                                                      len(current_encounters),
                                                                      len(current_encounters),
                                                                      addrs_to_hex(list(current_encounters.keys())),
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
            btprint("RX: {}".format(text))
            if '143.all' in text:
                btprint('all unique statics:')
                for i,addr in enumerate(sorted(list(known_statics))):
                    btprint(' {}: {}'.format(i,addrs_to_hex([addr])))
    elif was_connected:
        was_connected = False
        radio.start_advertising(advertisement)

    #debug_test+=50
