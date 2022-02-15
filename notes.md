# Notes

ESP8266 NodeMCU 1.0

UDP connection

RFID-RC522 reader

Neopixels LED strip

The last two to be found using library manager

| ESP   | RC      | LED  |
| ----- | ------- | ---- |
| D2    |         | Di   |
| D3    | RST     |      |
| D4    | SDA(SS) |      |
| 3V3   | 3.3V    |      |
| GND   | GND     |      |
| D5    | SCK     |      |
| D6    | MISO    |      |
| D7    | MOSI    |      |
|       | IRQ     |      |
| (...) |         |      |
| GND   |         | GND  |
| 3V3   |         | +5V  |

Change in code: after including RC522 header

```cpp
#define RST_PIN D3
#define SS_PIN D4
```

Use SumoBot code as ESP8266 reference