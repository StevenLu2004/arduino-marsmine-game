#include <ESP8266WiFi.h>
#include <WiFiUDP.h>
#include <SPI.h>
#include <MFRC522.h>
#include <Adafruit_NeoPixel.h>
#define ABS(a_) (((a_) >= 0) ? (a_) : -(a_))
#define MIN(a_, b_) (((a_) <= (b_)) ? (a_) : (b_))
#define MAX(a_, b_) (((a_) >= (b_)) ? (a_) : (b_))
#define SETMIN(a_, b_) { if ((a_) > (b_)) { (a_) = (b_); } }
#define SETMAX(a_, b_) { if ((a_) < (b_)) { (a_) = (b_); } }

#define LED_DI D2
#define RC_RST D3
#define RC_SDA D4

// Pin layout
// | ESP   | RC      | LED  |
// | ----- | ------- | ---- |
// | D2    |         | Di   |
// | D3    | RST     |      |
// | D4    | SDA(SS) |      |
// | 3V3   | 3.3V    |      |
// | GND   | GND     |      |
// | D5    | SCK     |      |
// | D6    | MISO    |      |
// | D7    | MOSI    |      |
// |       | IRQ     |      |
// | (...) |         |      |
// | GND   |         | GND  |
// | 3V3   |         | +5V  |


#define cf const float
// Beziers
inline cf bzl(cf x, cf a, cf b) {
	cf y = 1 - x;
	return y*a + x*b;
}
inline cf bzq(cf x, cf a, cf b, cf c) {
	cf y = 1 - x;
	return y*(y*a + x*b*2) + x*x*c;
}
inline cf bzc(cf x, cf a, cf b, cf c, cf d) {
	cf y = 1 - x;
	return y*(y*(y*a + x*b*3) + x*x*c*3) + x*x*x*d;
}
inline cf bzt(cf x, cf a, cf b, cf c, cf d, cf e) {
	cf y = 1 - x;
	return y*(y*(y*(y*a + x*b*4) + x*x*c*6) + x*x*x*d*4) + x*x*x*x*e;
}
#undef cf


uint32_t now, justNow, dt; // maintain to be equal to millis()
float nowSec, justNowSec, dtSec; // now / 1000.0

void updateTime() {
	justNow = now;
	now = millis();
	justNowSec = nowSec;
	nowSec = now / 1000.0;
	dt = now - justNow;
	dtSec = nowSec - justNowSec;
}

struct Dword { // Vsauce!
	byte b0, b1, b2, b3;
	void toCStr(char *c) { c[0] = b0; c[1] = b1; c[2] = b2; c[3] = b3; }
};


#define sp Serial.print
#define spln Serial.println
#define spc Serial.print(' ')
#define spb(b_) {\
	if ((b_) < 0x10) sp('0');\
	sp((b_), HEX);\
}
#define spdw(d_) {\
	spb((d_).b0); spc; spb((d_).b1); spc;\
	spb((d_).b2); spc; spb((d_).b3);\
}
void spbs(byte *buffer, uint8_t bufferSize) {
	// Has defined new variable (i), thus cannot be written as a macro
	// (risks naming conflict)
	spb(buffer[0]);
	for (uint8_t i = 1; i < bufferSize; ++i) {
		sp(' '); spb(buffer[i]);
	}
}


template<typename T>
class CQueue {
private:
	T *arr;
	uint16_t capacity, front, rear;
	bool _isFull;
public:
	CQueue(uint16_t capacity_) {
		capacity = MAX(1, capacity_);
		arr = new T[capacity];
		front = rear = 0;
	}
	~CQueue() {
		delete[] arr;
	}
	bool push(T x) {
		if (_isFull) return false;
		arr[rear++] = x;
		if (rear == capacity) rear = 0;
		if (rear == front) _isFull = true;
		return true;
	}
	bool pop() {
		if (rear == front && !_isFull) return false;
		_isFull = false;
		front++;
		if (front == capacity) front = 0;
		return true;
	}
	T top() { return arr[front]; }
	inline bool isFull() { return _isFull; }
	inline bool isEmpty() { return front == rear && !_isFull; }
};


namespace myWifi {
	// const char* STASSID = "PiLab";
	// const char* STAPSK = "thisispilab";
	const char* STASSID = "PRIS_Student";
	const char* STAPSK = "wearethebest1";
	uint32_t nextReconnect;
	const uint16_t RECONNECT_WAIT = 10000;
	uint8_t status; // R2L, bit 0: current status, bit 1: status last time

	void reconnect() {
		spln("WiFi is reconnecting");
		WiFi.mode(WIFI_STA);
		WiFi.begin(STASSID, STAPSK);
		nextReconnect = now + RECONNECT_WAIT;
	}

	void update() {
		status = (status << 1 | (WiFi.status() == WL_CONNECTED)) & 3;
		if (!(status & 1) && now >= nextReconnect) reconnect();
		if (status == 1) spln("WiFi has just connected");
	}
}


namespace myUdp {
	const uint16_t LOCAL_PORT = 1926;
	const uint16_t MCAST_PORT = 817;
	const uint16_t SERVER_PORT = 88;
	const IPAddress MCAST_GROUP(224, 0, 3, 141);
	const char MCAST_KEY1[] = "q\xfe\xce\x92";
	const char MCAST_KEY2[] = "\x1f|\xde\xe9";
	IPAddress serverIp;
	bool hasServerIp;
	uint32_t nextAskedServerIp;
	const uint16_t ASK_SERVER_IP_WAIT = 5000;
	char buffer[5];
	WiFiUDP sock;
	CQueue<Dword> tasks(4096);

	void _askServerIp() {
		spln("UDP pings for server IP");
		sock.beginPacket(MCAST_GROUP, MCAST_PORT);
		sock.write(MCAST_KEY1);
		sock.endPacket();
		nextAskedServerIp = now + ASK_SERVER_IP_WAIT;
	}

	void reinit() {
		sock.stop();
		sock.begin(LOCAL_PORT);
		_askServerIp();
	}

	void isPanicking() { return !hasServerIp && tasks.isFull(); }

	void update() {
		while (int packSize = sock.parsePacket()) {
			sock.read(buffer, 4);
			if (!strcmp(buffer, MCAST_KEY2)) {
				serverIp = sock.remoteIP();
				hasServerIp = true;
				sp("Received server IP: "); spln(serverIp.toString().c_str());
			}
		}
		if (hasServerIp) {
			while (!tasks.isEmpty()) {
				sp("UDP pop send() task: "); spdw(tasks.top()); spln();
				tasks.top().toCStr(buffer); tasks.pop();
				sock.beginPacket(serverIp, SERVER_PORT);
				sock.write(buffer);
				sock.endPacket();
			}
		} else if (now >= nextAskedServerIp) {
			_askServerIp();
		}
	}

	bool send(Dword d) {
		sp("UDP add send() task: "); spdw(d); spln();
		return tasks.push(d);
	}
}


namespace myPixel {
	const uint16_t PIXEL_COUNT = 15;
	Adafruit_NeoPixel strip(PIXEL_COUNT, LED_DI, NEO_GRB + NEO_KHZ800);
	float height; // between 0.0 and 1.0
	uint8_t r, g, b, brightness = 255, darkness, sr, sg, sb;
	// darkness: darker... brightness?
	// s[rgb]: status color
	uint16_t blink0 = 0, blink01 = 1000;

	void init() { strip.begin(); }

	void renderBoot() {
		// Vsauce!
		strip.setBrightness(255);
		strip.setPixelColor(0, 170, 0, 170);
		strip.setPixelColor(1, 170, 170, 0);
		strip.setPixelColor(2, 170, 170, 170);
		strip.setPixelColor(3, 0, 170, 170);
		strip.setPixelColor(4, 170, 170, 0);
		strip.setPixelColor(5, 0, 0, 170);
		strip.setPixelColor(6, 170, 170, 170);
		strip.setPixelColor(7, 170, 0, 170);
		strip.setPixelColor(8, 170, 170, 0);
		strip.setPixelColor(9, 0, 170, 170);
		strip.setPixelColor(10, 170, 170, 0);
		strip.setPixelColor(11, 170, 0, 170);
		strip.setPixelColor(12, 0, 170, 0);
		strip.setPixelColor(13, 0, 0, 170);
		strip.show();
	}

	void render() {
		if (now % blink01 >= blink0) strip.setBrightness(brightness);
		else strip.setBrightness(darkness);
		uint16_t pxcnt = PIXEL_COUNT - 1;
		uint16_t fullPxs = height * pxcnt, i;
		for (i = 0; i < fullPxs; ++i)
			strip.setPixelColor(i, r, g, b);
		if (fullPxs != pxcnt) {
			float k = height * pxcnt - fullPxs;
			uint8_t kr = round(r*k), kg = round(g*k), kb = round(b*k);
			strip.setPixelColor(fullPxs, kr, kg, kb);
			for (i = fullPxs + 1; i < pxcnt; ++i)
				strip.setPixelColor(i, 0, 0, 0);
		}
		strip.setPixelColor(pxcnt, sr, sg, sb);
		strip.show();
	}

	void rgb(uint8_t r_, uint8_t g_, uint8_t b_) {
		r = r_; g = g_, b = b_;
	}
	void statusrgb(uint8_t r_, uint8_t g_, uint8_t b_) {
		sr = r_; sg = g_, sb = b_;
	}
	void _hsv(float h, float s, float v, bool is_status) {
		if (s == 0.0) {
			if (is_status) sr = sg = sb = round(v * 255);
			else r = g = b = round(v * 255);
			return;
		}
		uint8_t i = h * 6.0;
		float f = h * 6.0 - i;
		float p = v * (1.0 - s);
		float q = v * (1.0 - s * f);
		float t = v * (1.0 - s * (1.0 - f));
		float fr, fg, fb;
		switch (i % 6) {
			case 0: fr = v, fg = t, fb = p; break;
			case 1: fr = q, fg = v, fb = p; break;
			case 2: fr = p, fg = v, fb = t; break;
			case 3: fr = p, fg = q, fb = v; break;
			case 4: fr = t, fg = p, fb = v; break;
			case 5: fr = v, fg = p, fb = q;
		}
		if (is_status) {
			sr = round(fr*255), sg = round(fg*255), sb = round(fb*255);
		} else {
			r = round(fr*255), g = round(fg*255), b = round(fb*255);
		}
	}
	void hsv(float h, float s, float v) { _hsv(h, s, v, false); }
	void statushsv(float h, float s, float v) { _hsv(h, s, v, true); }

	void setBrightness(uint8_t brightness_, uint8_t darkness_ = 0) {
		brightness = brightness_;
		darkness = darkness_;
	}

	void setBlink(uint16_t blink0_, uint16_t blink1_) {
		blink0 = blink0_;
		blink01 = blink0 + blink1_;
	}
}


namespace myRfReader {
	// Based on
	// https://github.com/Martin-Laclaustra/MFRC522-examples/blob/main/UIDRemovalDetection/UIDRemovalDetection.ino

	MFRC522 rc(RC_SDA, RC_RST);
	uint32_t nextReinit;
	const uint16_t REINIT_WAIT = 1000;
	uint8_t hasCard; // R2L, bit 0: current status, bit 1: status last time
	Dword cardId; // A (supposedly) unique ID derived from the card UID

	void reinit() {
		rc.PCD_Init();
		hasCard = 0; cardId = (Dword){0,0,0,0};
		nextReinit = now + REINIT_WAIT;
		spln("Reinitialize RC522");
	}

	bool pcdIsReady() {
		// Check RC522 board connection readiness by reading version register
		byte v;
		return (v = rc.PCD_ReadRegister(MFRC522::VersionReg)) && v != 0xff;
	}

	bool isNewCardPresent() { return rc.PICC_IsNewCardPresent(); } // wrapper

	bool isAnyCardPresent() {
		// Mirror implementation of isNewCardPresent; the actual difference is
		// in using WakeupA instead of RequestA.

		byte bufferATQA[2];
		byte bufferSize = sizeof(bufferATQA);

		// Reset baud rates
		rc.PCD_WriteRegister(rc.TxModeReg, 0x00);
		rc.PCD_WriteRegister(rc.RxModeReg, 0x00);
		// Reset ModWidthReg
		rc.PCD_WriteRegister(rc.ModWidthReg, 0x26);

		MFRC522::StatusCode result = rc.PICC_WakeupA(bufferATQA, &bufferSize);
		return (result == STATUS_OK || result == STATUS_COLLISION);
	}

	bool readCardSerial() {
		// Reimplementation to mirror MFRC522::ReadCardSerial() functionality
		// but matches semantics in Martin-Laclaustra's example. Don't know
		// what's the effect of including/excluding the validBits argument in
		// MFRC522::PICC_Select().
		MFRC522::StatusCode result = rc.PICC_Select(&rc.uid, 8 * rc.uid.size);
		return (result == STATUS_OK);
	}

	void updateCardId() {
		cardId.b0 = rc.uid.uidByte[0];
		cardId.b1 = rc.uid.uidByte[1];
		cardId.b2 = rc.uid.uidByte[2];
		cardId.b3 = rc.uid.uidByte[3];
	}

	void update() {
		hasCard &= 1;
		if (!pcdIsReady()) {
			if (now >= nextReinit) reinit();
			hasCard <<= 1; return;
		}
		bool cardPresent = isAnyCardPresent();
		if (!hasCard && !cardPresent) { hasCard = 0; return; }
		bool readResult = readCardSerial();
		if (!hasCard && readResult) {
			// Card detected
			hasCard = 1;
			sp("Detected card with UID: ");
			spbs(rc.uid.uidByte, rc.uid.size); spln();
			updateCardId();
		} else if (hasCard && !readResult) {
			// Card removed
			hasCard = 2;
			spln("The card is lost");
		} else if (!hasCard && !readResult) {
			// (How did we even get here??) Clear locked card data just in case
			// some data was retrieved in the select procedure but an error
			// prevented locking.
			rc.uid.size = 0;
		} else {
			hasCard = 3;
		}
		rc.PICC_HaltA();
	}
}


namespace myMineApp {
	const float DRAIN_SPEED = 0.1; // rc/sec
	const float NATURAL_REFILL_SPEED = 0.1, REFILL_SPEED = 0.06; // rc/sec
	const float DRAIN_UNTIL_OVERHEAT = 0.2; // rc
	const float OVERHEAT_WAIT = 5.0; // sec
	const uint8_t SCORE_PER_OVERHEAT = 3;
	// ## Refill speed prisoner's dilemma
	// If the quadcopter completely drains the mine, the mine will be recharged
	// with REFILL_SPEED and will be unusable until full; otherwise, the mine
	// will recharge with NATURAL_REFILL_SPEED and be usable any time.
	// Obviously, the net produce is greater when the mine is not completely
	// used up; however, draining the mine whenever one can and as much as
	// possible is favorable for competition.

	float storage = 1.0; // Unit: resource (rc)
	float partialScore = 0.0; // rc
	float heat; // (unitless/proportion)
	bool reportScore; // Signal indicating whether the quadcopter scores
	bool overheating, refilling; // More signals
	bool justOverheated, justCooled, justRefilled, justEmptied; // More signals

	void incHeat() { heat = MIN(heat + dtSec/OVERHEAT_WAIT, 1.0); }
	void decHeat() { heat = MAX(heat - dtSec/OVERHEAT_WAIT, 0.0); }
	void naturalRefillStorage() {
		storage = MIN(storage + NATURAL_REFILL_SPEED * dtSec, 1.0);
	}
	void refillStorage() {
		storage = MIN(storage + REFILL_SPEED * dtSec, 1.0);
		if (storage == 1.0) refilling = false, justRefilled = true;
	}
	void drainStorage() {
		storage = MAX(storage - DRAIN_SPEED * dtSec, 0.0);
		if (storage == 0.0) refilling = true, justEmptied = true;
	}
	void incPartialScore() {
		partialScore += DRAIN_SPEED * dtSec;
		if (partialScore >= DRAIN_UNTIL_OVERHEAT / SCORE_PER_OVERHEAT) {
			partialScore -= DRAIN_UNTIL_OVERHEAT / SCORE_PER_OVERHEAT;
			reportScore = true;
		}
	}

	void update(uint8_t hasDrone) {
		// @param hasDrone mirrors hasCard (see namespace myRfReader)
		reportScore = false;
		justOverheated = justCooled = justRefilled = justEmptied = false;

		if (hasDrone & 1) incOverheat();
		else decOverheat();

		if (heat == 1.0) overheating = true, justOverheated = true;
		else if (heat == 0.0) oveheating = false, justCooled = true;

		if (refilling) { refillStorage(); return; }

		if (overheating) return;

		switch (hasDrone) {
		case 2:
			partialScore = 0.0;
		case 0:
			naturalRefillStorage();
			break;
		case 1:
			partialScore = 0.0;
		case 3:
			drainStorage();
			incPartialScore();
		}
	}
}


void setup() {
	myPixel::init();
	myPixel::setBrightness(255, 25);
	myPixel::renderBoot();
	delay(500);
	Serial.begin(74880);
	delay(500);
	SPI.begin();
	delay(500);
}


void loop() {
	updateTime();

	myWifi::update();
	switch (myWifi::status) {
		case 1: myUdp::reinit();
		case 3: myUdp::update();
	}

	myRfReader::update();

	myMineApp::update(myRfReader::hasCard);

	if (myMineApp::reportScore) myUdp::send(myRfReader::cardId);

	myPixel::height = myMineApp::storage;
	if (!myMineApp::refilling && !myMineApp::overheating) {
		// Normal state
		myPixel::hsv(bzl(myMineApp::heat, 1.0/3, 1.0/6), 1.0, 1.0);
	} else if (myMineApp::refilling) {
		myPixel::rgb(0, 192, 255);
	} else if (myMineApp::overheating) {
		myPixel::hsv(bzl(myMineApp::heat, 1.0/6, 0.0), 1.0, 1.0);
	}
	myPixel::sr = (myWifi::status & 1) ? 0 : 255;
	myPixel::sg = myUdp::isPanicking() ? 255 : myUdp::hasServerIp ? 0 : 128;
	myPixel::sb = myRfReader::pcdIsReady() ? 0 : 255;
	if (myPixel::sr || myPixel::sg || myPixel::sb) myPixel::setBlink(50, 50);
	else myPixel::setBlink(0, 1000);
	myPixel::render();
}
