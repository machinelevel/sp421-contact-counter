# Currently reports: 145776 on cpgbf
import time
import gc

while True:
    gc.collect()
    print('free memory:',gc.mem_free())
    time.sleep(1)
