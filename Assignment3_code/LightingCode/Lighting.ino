int value = 0;
int value2 = 0;
#define zone1 11
#define zone2 12

void setup()
{
  Serial.begin(9600);

  // Zone 1
  pinMode(zone1, OUTPUT); // pin 11 for zone 1
  pinMode(A0, INPUT);

  // Zone 2
  pinMode(zone2, OUTPUT); // pin 12 for zone 2
  pinMode(A1, INPUT);
}

void loop()
{
  value = analogRead(A0);  // Read value for zone 1
  value2 = analogRead(A1); // Read value for zone 2
  if (Serial.available() > 0)
  {
    String command = Serial.readStringUntil('\n');
    handleCommand(command);
  }    
  Serial.print(value);
  Serial.print(',');
  Serial.print(value2);
  Serial.println();

  delay(5000);
}

void handleCommand(String command)
{
  if (command.startsWith("ON") || command.startsWith("OFF"))
  {
    int zone = command.endsWith("1") ? zone1 : zone2;

    if (command.startsWith("ON"))
    {
      // Turn on the light in the specified zone
      digitalWrite(zone, HIGH);
    }
    else if (command.startsWith("OFF"))
    {
      // Turn off the light in the specified zone
      digitalWrite(zone, LOW);
    }
  }
}
