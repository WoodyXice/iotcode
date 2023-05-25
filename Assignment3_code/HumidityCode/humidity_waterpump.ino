#include <Servo.h>
#define zone1 8
#define zone2 7

int humiditysensorOutput_zone1 = 0;
int humiditysensorOutput_zone2 = 0;
int potentiometerInput_zone1 = 0;
int potentiometerInput_zone2 = 0;
Servo myservo;

unsigned long lastCommandTime = 0; // Time when last command received
unsigned long commandDelay = 3000; // Time delay between each command execution

void setup() {
  Serial.begin(9600);
  pinMode(A0, INPUT);
  pinMode(A1, INPUT);
  pinMode(A2, INPUT);
  pinMode(A3, INPUT);
  pinMode(zone1, OUTPUT);
  pinMode(zone2, OUTPUT);
  myservo.attach(9);
}

void loop() {
  humiditysensorOutput_zone1 = analogRead(A0);
  potentiometerInput_zone1 = analogRead(A1);
  humiditysensorOutput_zone2 = analogRead(A2);
  potentiometerInput_zone2 = analogRead(A3);
  
  int humidityOutput_1 = map(potentiometerInput_zone1, 0, 1023, 10, 70);
  int humidityOutput_2 = map(potentiometerInput_zone2, 0, 1023, 10, 70);

  if (Serial.available() > 0) {
    String command = Serial.readStringUntil('\n');
    handleCommand(command);
  }
  
  Serial.print(humidityOutput_1);
  Serial.print(",");
  Serial.println(humidityOutput_2);
  
  delay(5000);
}

void handleCommand(String command) {
  if (command.startsWith("IncreaseHumidityBig") || 
      command.startsWith("IncreaseHumiditySmall") || 
      command.startsWith("DecreaseHumiditySmall") || 
      command.startsWith("DecreaseHumidityBig") || 
      command.startsWith("OFF")) {

    int zone = command.endsWith("1") ? zone1 : zone2;
    digitalWrite(zone, HIGH);

    if (command.startsWith("IncreaseHumidityBig")) {
      myservo.write(180);
    }
    else if (command.startsWith("IncreaseHumiditySmall")) {
      myservo.write(135);
    }
    else if (command.startsWith("DecreaseHumiditySmall")) {
      myservo.write(45);
    }
    else if (command.startsWith("DecreaseHumidityBig")) {
      myservo.write(0);
    }
    else if (command.startsWith("OFF")) {
      myservo.write(90);
    }
    
    delay(5000); // Delay before turning off the LED
    digitalWrite(zone, LOW);
  }
}
