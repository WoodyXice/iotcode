#include <Servo.h>
#define zone1 8
#define zone2 7

int temperatureOutput_zone1 = 0;
int temperatureOutput_zone2 = 0;
int potentiometerInput_zone1 = 0;
int potentiometerInput_zone2 = 0;
Servo myservo;

unsigned long lastCommandTime = 0; // Time when last command received
unsigned long commandDelay = 3000;

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
  temperatureOutput_zone1 = analogRead(A0);
  potentiometerInput_zone1 = analogRead(A1);
  temperatureOutput_zone2 = analogRead(A2);
  potentiometerInput_zone2 = analogRead(A3);
  
  int temperatureOutput_1 = map(potentiometerInput_zone1, 0, 1023, 10, 70);
  int temperatureOutput_2 = map(potentiometerInput_zone2, 0, 1023, 10, 70);

 
  if (Serial.available() > 0) 
  {
    String command = Serial.readStringUntil('\n');
    handleCommand(command);
  }
  //print value
  Serial.print(temperatureOutput_1);
  Serial.print(",");
  Serial.println(temperatureOutput_2);
  
  delay(5000);
}
void handleCommand(String command)
{
  if (command.startsWith("IncreaseTemperatureBig") || 
      command.startsWith("IncreaseTemperatureSmall") || 
      command.startsWith("DecreaseTemperatureSmall") || 
      command.startsWith("DecreaseTemperatureBig") || 
      command.startsWith("OFF")) {
    // Perform different operations based on the received command
    int zone = command.endsWith("1") ? zone1 : zone2;
    digitalWrite(zone, HIGH);

    if (command.startsWith("IncreaseTemperatureBig")) {
      myservo.write(180);
    }
    else if (command.startsWith("IncreaseTemperatureSmall")) {
      myservo.write(135);
    }
    else if (command.startsWith("DecreaseTemperatureSmall")) {
      myservo.write(45);
    }
    else if (command.startsWith("DecreaseTemperatureBig")) {
      myservo.write(0);
    }
    else if (command.startsWith("OFF")) {
      myservo.write(90);
    }
    
    // Turn off the light after executing the command
    delay(5000); // Delay for visibility
    digitalWrite(zone, LOW);
 }
}
