import time
import json
import threading
import serial
import mysql.connector
from datetime import datetime
from AWSIoTPythonSDK.MQTTLib import AWSIoTMQTTClient

# Set up the database connection
conn = mysql.connector.connect(
    host="localhost",
    database="assign3",
    user="pi",
    password="110303110303"
)
# Check if the connection is successful
if conn.is_connected():
    print("Connected to the database")
else:
    print("Failed to connect to the database")
cur = conn.cursor()

# Set up the serial port
ser = serial.Serial("/dev/ttyACM0", 9600)  # Replace 'COM1' with the appropriate serial port and baud rate
# AWS IoT certificate-based connection configuration
myMQTTClient = AWSIoTMQTTClient("humidity")
myMQTTClient.configureEndpoint("a38vbpblycdx95-ats.iot.ap-southeast-2.amazonaws.com", 8883)
myMQTTClient.configureCredentials("/home/pi/cert/AmazonRootCA1.pem", "/home/pi/cert/d056b1df5d868542c7b73a38764e9844a38f5bfeebefe2e86d02c1da804ced95-private.pem.key", "/home/pi/cert/d056b1df5d868542c7b73a38764e9844a38f5bfeebefe2e86d02c1da804ced95-certificate.pem.crt")
myMQTTClient.configureOfflinePublishQueueing(-1)  # Infinite offline Publish queueing
myMQTTClient.configureDrainingFrequency(2)  # Draining: 2 Hz
myMQTTClient.configureConnectDisconnectTimeout(10)  # 10 sec
myMQTTClient.configureMQTTOperationTimeout(5)  # 5 sec
myMQTTClient.connect()  # Connect to the AWS IoT MQTT broker
myMQTTClient.publish("humidity/info","connected",0)

# The callback for inserting data into the database
def insert_data(humidity_value1,humidity_value2):
    # Modify the SQL query to insert data into your specific table structure
    cur.execute("INSERT INTO humidity (humidity_value1, humidity_value2) VALUES (%s,%s)",(humidity_value1,humidity_value2,))
    conn.commit()

    # Fetch the inserted data from the database
    cur.execute("SELECT humidity_value1,humidity_value2,humidity_time FROM humidity ORDER BY id DESC LIMIT 1")
    row = cur.fetchone()
    fetched_humidity_value1 = row[0]
    fetched_humidity_value2 = row[1]
    fetched_humidity_time = row[2]
    
    return fetched_humidity_value1, fetched_humidity_value2, fetched_humidity_time

# The callback for when a PUBLISH message is received from the server.
def on_message(client, userdata, message):
    try:
        print("Received message '" + str(message.payload) + "' on topic '"
              + message.topic + "' with QoS " + str(message.qos))
        # Here you can parse the message and perform the operation on your Arduino
        command = message.payload.decode('utf-8')
        print("Command to be sent: ", command)
        ser.write(command.encode())
    except Exception as e:
        print("An error occurred while processing the message:")
        print("Payload: ", str(message.payload))
        print("Error: ", str(e))

def handle_mqtt():
    myMQTTClient.subscribe("command/humidity", 1, on_message)  # replace "your/topic" with your actual topic
    while True:
        time.sleep(1)

def calculate_and_publish():
    current_time = datetime.now()  # Get the current time
    formatted_time = current_time.strftime("%Y-%m-%d %H:%M:%S")  # Format the current time
    
    # Calculate the averages
    cur.execute("SELECT AVG(humidity_value1), AVG(humidity_value2) FROM humidity")
    row = cur.fetchone()
    average_humidity_value1 = float(row[0])
    average_humidity_value2 = float(row[1])

    # Generate the payload using the fetched data and averages
    payload = {
        "Sensor_Type": "Humidity",
        "Average_Value1": average_humidity_value1,
        "Average_Value2": average_humidity_value2,
        "Time": formatted_time
    }
    
    # Convert the paylaod to JSON format
    payload_json = json.dumps(payload)
    
    # Publish the payload to the desired MQTT topic
    myMQTTClient.publish("humidity/data", payload_json, 0)

    print("Published Payload:", payload)

mqtt_thread = threading.Thread(target=handle_mqtt)
mqtt_thread.start()

last_average_time = int(time.time()) 
# Read data from the serial port and insert it into the database
while True:    
    if ser.in_waiting > 0:
        data = ser.readline().decode().strip()  # Read data from the serial port
        try:
            humidity_value = data
            # Split the humidity value into two values
            humidity_value1, humidity_value2 = humidity_value.split(",")

            # Insert the data into the database
            fetched_humidity_value1, fetched_humidity_value2, fetched_humidity_time = insert_data(humidity_value1, humidity_value2)
            
            # Calculate the averages every 5 minutes
            current_time = int(time.time())
            if current_time - last_average_time >= 300:
                last_average_time = current_time
                calculate_and_publish()
            
            time.sleep(1)
        except ValueError:
            pass
            
# Publish the data to the cloud using MQTT protocol
#client.publish("YOUR_TOPIC", data)

# Close the database connection
cur.close()
conn.close()
