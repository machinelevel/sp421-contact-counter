"""
IMPORTANT
With this boot.py insalled, the device will DEFAULT to standalone mode,
where the code.py program can write data and a host computer cannot.

...so if you want to develop (change the program) ot otherwise write
from a PC, you must HOLD one of the buttons (either one will do)
while connecting or while pressing reset.
"""
import storage
import digitalio
import board

left_button = digitalio.DigitalInOut(board.D4)
right_button = digitalio.DigitalInOut(board.D5)
left_button.switch_to_input(pull=digitalio.Pull.DOWN)
right_button.switch_to_input(pull=digitalio.Pull.DOWN)

# If neither button is pressed during restart, allow saving of data
if left_button.value or right_button.value:
#    print('Develop mode activated: host can write, python cannot')
    pass
else:
#    print('Standalone mode activated: python can write, host cannot')
    storage.remount('/', False)


