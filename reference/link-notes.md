# Useful references

I've found these links helpful for this project.

- https://circuitpython.readthedocs.io/projects/ble/en/latest/api.html
- https://learn.adafruit.com/circuitpython-display-support-using-displayio/text
- https://circuitpython.readthedocs.io/projects/il0373/en/latest/api.html
  1.54" 152x152 tri-color
- partial-update eink thread: https://forums.adafruit.com/viewtopic.php?f=47&t=141512
- fonts: https://learn.adafruit.com/custom-fonts-for-pyportal-circuitpython-display/overview
- displayio ref: https://learn.adafruit.com/custom-fonts-for-pyportal-circuitpython-display/overview
- eink datasheet: https://cdn-shop.adafruit.com/product-files/4243/4243_datahseet_GDEW0213I5F_V1.1_Specification__1_.pdf
- https://www.smart-prototyping.com/image/data/9_Modules/EinkDisplay/GDEW0154T8/IL0373.pdf
- board schematic https://learn.adafruit.com/assets/84661
- Bluefruit pinout: https://learn.adafruit.com/adafruit-circuit-playground-bluefruit/pinouts
- EInk gizmo pinout: https://learn.adafruit.com/adafruit-circuit-playground-tri-color-e-ink-gizmo/pinouts
- online image-to-hex: https://javl.github.io/image2cpp/
- Blluetooth feather comparison: https://learn.adafruit.com/adafruit-feather/bluetooth-feathers
- Write-file protection notes: https://learn.adafruit.com/adafruit-circuit-playground-express/circuitpython-storage
- Circuit playground Bluefruit schematic: https://learn.adafruit.com/adafruit-circuit-playground-bluefruit/downloads


Feather links:
getting started: https://learn.adafruit.com/introducing-the-adafruit-nrf52840-feather/circuitpython
circuitpython: https://circuitpython.org/board/feather_nrf52840_express/
Feather eink: https://learn.adafruit.com/adafruit-eink-display-breakouts/circuitpython-code-2
Feather e-ink quickstart: https://learn.adafruit.com/quickstart-using-adafruit-eink-epaper-displays-with-circuitpython
3rd pin on short side, far from usb

Batt-level sample from https://learn.adafruit.com/adafruit-feather-m0-adalogger/power-management
```c++
#define VBATPIN A7
   
float measuredvbat = analogRead(VBATPIN);
measuredvbat *= 2;    // we divided by 2, so multiply back
measuredvbat *= 3.3;  // Multiply by 3.3V, our reference voltage
measuredvbat /= 1024; // convert to voltage
Serial.print("VBat: " ); Serial.println(measuredvbat);
```