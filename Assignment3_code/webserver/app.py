from flask import Flask, render_template, jsonify, request
from datetime import datetime
from AWSIoTPythonSDK.MQTTLib import AWSIoTMQTTClient
from boto3.dynamodb.conditions import Attr, Key
from pytz import utc
from flask_apscheduler import APScheduler
import requests
import boto3
import datetime as dt
import threading
import json

# Instantiate Flask and APScheduler
app = Flask(__name__)
scheduler = APScheduler()

# Create a DynamoDB resource object using Boto3
# This is where your credentials to access the DynamoDB table are set
dynamodb = boto3.resource('dynamodb', region_name='ap-southeast-2', aws_access_key_id='AKIAVHROVJHA5WPKGZMW', aws_secret_access_key='3jiJxCQ8bWlbyC244K+M2WSCyjMv0BStnPmW2EAH')

# Reference the table you want to access
table = dynamodb.Table('iotnodes_data')

# Configure the MQTT client for AWS IoT
myMQTTClient = AWSIoTMQTTClient("Dashboard")
myMQTTClient.configureEndpoint("a38vbpblycdx95-ats.iot.ap-southeast-2.amazonaws.com", 8883)
myMQTTClient.configureCredentials("/home/ubuntu/cert/AmazonRootCA1.pem", "/home/ubuntu/cert/38c86702afacb3fb1dcc76af2e1ca721cb3655d9abf5c73bd092979549367ca8-private.pem.key", "/home/ubuntu/cert/38c86702afacb3fb1dcc76af2e1ca721cb3655d9abf5c73bd092979549367ca8-certificate.pem.crt")
myMQTTClient.configureOfflinePublishQueueing(-1)  # Infinite offline Publish queueing
myMQTTClient.configureDrainingFrequency(2)  # Draining: 2 Hz
myMQTTClient.configureConnectDisconnectTimeout(10)  # 10 sec
myMQTTClient.configureMQTTOperationTimeout(5)  # 5 sec
myMQTTClient.connect()  # Connect to the AWS IoT MQTT broker

# Function to interact with discord api to send alert msg
def send_discord_alert(sensor_type, value, range_dict, zone):
    try:
        # Generate a message based on the sensor_type and value
        if value < range_dict['abnormal_lower']:
            message = f"Alert! The {sensor_type} sensor in Zone {zone} has recorded a value of {value}, which is below the abnormal lower limit ({range_dict['abnormal_lower']})."
        elif range_dict['abnormal_lower'] <= value < range_dict['ideal_lower']:
            message = f"Warning! The {sensor_type} sensor in Zone {zone} has recorded a value of {value}, which is slightly lower than the ideal range."
        elif range_dict['ideal_upper'] < value <= range_dict['abnormal_upper']:
            message = f"Warning! The {sensor_type} sensor in Zone {zone} has recorded a value of {value}, which is slightly higher than the ideal range."
        elif value > range_dict['abnormal_upper']:
            message = f"Alert! The {sensor_type} sensor in Zone {zone} has recorded a value of {value}, which is above the abnormal upper limit ({range_dict['abnormal_upper']})."
        else:
            message = f"The {sensor_type} sensor in Zone {zone} is operating within the ideal range."

        # Create a payload to send to Discord
        payload = {
            "content": message
        }

        # You need a URL for your specific Discord channel here
        discord_webhook_url = "https://discord.com/api/webhooks/1109676448693878864/dxxRSW8nKU5L4lcDS9qS2p4F4G06_-fQPNiqlnULTvz6vN1chql3L7lxyx9HWJ1EtoRk"

        # Send the message to Discord
        response = requests.post(discord_webhook_url, data=json.dumps(payload), headers={"Content-Type": "application/json"})
        
        # Log the response from Discord to help debug issues
        app.logger.info(f'Response from Discord: {response.text}')

    except Exception as e:
        app.logger.error(f'Error in send_discord_alert: {str(e)}')

# This function checks for new data from the sensors
def check_new_data():
    try:
        # Define the ideal and abnormal range for each sensor type
        ranges = {
            'Humidity': {'ideal_lower': 40, 'ideal_upper': 60, 'abnormal_lower': 30, 'abnormal_upper': 65},
            'Temperature': {'ideal_lower': 20, 'ideal_upper': 25, 'abnormal_lower': 15, 'abnormal_upper': 30},
            'Lighting': {'ideal_threshold': 100},
        }

        # Name of the secondary index
        index_name = 'Sensor_Type-Time-index'

        latest_items = {}

        # Fetch the latest item for each sensor type
        for sensor_type in ranges:
            response = table.query(
                IndexName=index_name,
                KeyConditionExpression=Key('Sensor_Type').eq(sensor_type),
                ScanIndexForward=False,  # Sort in descending order by time
                Limit=1  # Limit the result to only one item (the latest)
            )

            items = response['Items']
            if items:
                latest_item = items[0]
                latest_items[sensor_type] = latest_item

        # Prepare commands for each sensor type
        commands = {}
        for sensor_type, latest_item in latest_items.items():
            sensor_commands = [] # variable to store command for every sensors
            sensor_subtype = sensor_type.lower() # sensor variable used for command
            weather_condition = latest_item['Weather_Condition']
            hour = datetime.strptime(latest_item['Time'], "%Y-%m-%d %H:%M:%S").hour
            for i in range(1, 3):
                average_value = latest_item[f'Average_Value{i}']

                if sensor_type == 'Lighting':
                    if average_value < ranges[sensor_type]['ideal_threshold']:
                        command = f"ON{i}"
                    else:
                        command = f"OFF{i}"

                else:
                    if average_value < ranges[sensor_type]['abnormal_lower']:
                        send_discord_alert(sensor_type, average_value, ranges[sensor_type], i)
                        # Humidity level very low
                        if sensor_type == 'Humidity' and weather_condition in [
                            # Weather Condition like light rain will make the humidity level slightly increase
                                'light rain', 'moderate rain', 
                                'thunderstorm with light rain', 'thunderstorm with rain'
                            ]:
                            # Change to IncreaseHumiditySmall
                            command = f"Increase{sensor_type}Small{i}"
                        elif sensor_type == 'Humidity' and weather_condition in [
                            # Weather condition like heavy intensity rain will increase the humidity level massively
                                'thunderstorm with heavy rain', 'heavy intensity rain',
                                'very heavy rain', 'extreme rain'
                            ]:
                            # So turn off humidifier
                            command = f"OFF{i}"
                        # Temperature very low                                     # Weather condition no clouds 
                        elif sensor_type == 'Temperature' and weather_condition in ['clear sky', 'few clouds'] and 8 <= hour < 17:
                            # Increase temperature small if time is between 8AM and 5PM, no cloud and sunny day
                            command = f"Increase{sensor_type}Small{i}"
                        else:
                            command = f"Increase{sensor_type}Big{i}"

                    elif ranges[sensor_type]['abnormal_lower'] <= average_value < ranges[sensor_type]['ideal_lower']:
                        send_discord_alert(sensor_type, average_value, ranges[sensor_type], i)
                        # Humidity level slightly lower than normal range
                        if sensor_type == 'Humidity' and weather_condition in [
                            # Weather Condition like light rain will make the humidity level slightly increase
                                'light rain', 'moderate rain', 
                                'thunderstorm with light rain', 'thunderstorm with rain'
                            ]:
                            # So turn off
                            command = f"OFF{i}"
                        elif sensor_type == 'Humidity' and weather_condition in [
                            # Weather condition like heavy intensity rain will increase the humidity level massively
                                'thunderstorm with heavy rain', 'heavy intensity rain',
                                'very heavy rain', 'extreme rain'                                
                            ]:
                            # So decrease humidity slightly to maintain the humidity level
                            command = f"Decrease{sensor_subtype.capitalize()}Small"
                        # Temperature slightly lower than normal range
                        elif sensor_type == 'Temperature' and weather_condition in ['clear sky', 'few clouds'] and 8 <= hour < 17:
                            # Turn off if time is between 8AM and 5PM, no cloud and sunny day
                            command = f"OFF{i}"
                        else:
                            command = f"Increase{sensor_subtype.capitalize()}Small{i}"

                    elif ranges[sensor_type]['ideal_upper'] < average_value <= ranges[sensor_type]['abnormal_upper']:
                        send_discord_alert(sensor_type, average_value, ranges[sensor_type], i)
                        # Humidity level slightly greater than normal range
                        if sensor_type == 'Humidity' and weather_condition in [
                            # Weather Condition that will make the humidity level massively increase
                                'light rain', 'moderate rain', 'thunderstorm with light rain', 
                                'thunderstorm with rain', 'thunderstorm with heavy rain', 'heavy intensity rain',
                                'very heavy rain', 'extreme rain'                                    
                            ]:
                            # So decrease humidity greatly to maintain the humidity level
                            command = f"Decrease{sensor_subtype.capitalize()}Big{i}"
                        # Humidity level slightly greater than normal range with sunny no clouds day 
                        elif sensor_type == 'Humidity' and weather_condition in ['clear sky', 'few clouds'] and 8 <= hour < 17:
                            # Turn off if time is between 8am and 5pm, it will decrease the humidity automatically due to sunlight
                            command = f"OFF{i}" 
                        # Temperature slightly greater than normal range
                        elif sensor_type == 'Temperature' and weather_condition in [
                            # Weather Condition that will make the Temperature slightly decrease
                                'light rain', 'moderate rain', 'thunderstorm with light rain', 
                                'thunderstorm with rain', 'broken clouds', 'overcast clouds' 
                            ]:
                            # Turn off
                            command = f"OFF{i}"
                        elif sensor_type == 'Temperature' and weather_condition in [
                            # Weather condition that will make the Temperature massively decrease
                                'thunderstorm with heavy rain', 'heavy intensity rain', 'very heavy rain', 
                                'extreme rain', 'heavy intensity shower rain', 'ragged shower rain'                                      
                            ]:
                            # Slightly increase the temperature to maintain the normal range
                            command = f"Increase{sensor_subtype.capitalize()}Small{i}"
                        else:
                            command = f"Decrease{sensor_subtype.capitalize()}Small{i}"

                    elif average_value > ranges[sensor_type]['abnormal_upper']:
                        send_discord_alert(sensor_type, average_value, ranges[sensor_type], i)
                        # Humidity level is very high
                        if sensor_type == 'Humidity' and weather_condition in ['clear sky', 'few clouds'] and 8 <= hour < 17:
                            # Slightly decrease the humidity if time is between 8am and 5pm, since it will decrease the humidity automatically by sunlight
                            command = f"Decrease{sensor_subtype.capitalize()}Small{i}"
                        # Temperature is very high
                        elif sensor_type == 'Temperature' and weather_condition in [
                            # Weather condition that will make the Temperature slightly decrease
                                'light rain', 'moderate rain', 'thunderstorm with light rain', 
                                'thunderstorm with rain', 'broken clouds', 'overcast clouds' 
                            ]:
                            # So just slightly decrease the Temperature to maintain the normal range
                            command = f"Decrease{sensor_subtype.capitalize()}Small{i}"
                        elif sensor_type == 'Temperature' and weather_condition in [
                            # Weather condition that will make the Temperature massively decrease
                                'thunderstorm with heavy rain', 'heavy intensity rain', 
                                'very heavy rain', 'extreme rain'                                        
                            ]:
                            # So just turn off the conditional
                            command = f"OFF{i}"
                        else:
                            command = f"Decrease{sensor_subtype.capitalize()}Big{i}"
                    else:
                        send_discord_alert(sensor_type, average_value, ranges[sensor_type], i)
                        command = f"OFF{i}"

                # Add command for average_value
                sensor_commands.append(command)

            # Add commands for sensor type to the commands dictionary
            commands[sensor_subtype] = sensor_commands

        # Publish commands
        for sensor_type, sensor_commands in commands.items():
            topic = f"command/{sensor_type}"
            message = "\n".join(sensor_commands)
            myMQTTClient.publish(topic, message, 0)

    except Exception as e:
        app.logger.error(f'Error in check_new_data: {str(e)}')

# Function to start the scheduler
def start_scheduler():
    global scheduler_thread
    scheduler.add_job(id='Check new data', func=check_new_data, trigger='interval', minutes=10)
    scheduler_thread = threading.Thread(target=scheduler.start)
    scheduler_thread.start()

# Function to stop the scheduler
def stop_scheduler():
    global scheduler_thread
    scheduler.remove_job('Check new data')
    if scheduler_thread and scheduler_thread.is_alive():
        scheduler_thread.join()

# Route to start the scheduler
@app.route('/start_scheduler', methods=['POST'])
def start_scheduler_route():
    start_scheduler()
    return jsonify({'success': True})

# Route to stop the scheduler
@app.route('/stop_scheduler', methods=['POST'])
def stop_scheduler_route():
    stop_scheduler()
    return jsonify({'success': True})

# Route to get time until the next execution of 'Check new data' job
@app.route('/next_execution')
def next_execution():
    # Get the job from the scheduler
    job = scheduler.get_job('Check new data')

    # If job does not exist return an error
    if job is None:
        return jsonify({'error': 'Job not found'})

    # Get the next time the job will run
    next_run_time = job.next_run_time

    # Get the current time
    current_time = dt.datetime.now(utc)

    # Calculate the remaining time in seconds
    remaining_seconds = (next_run_time - current_time).total_seconds()

    # Return the remaining time as a JSON response
    return jsonify({'remaining_seconds': remaining_seconds})

# Function to manually control the actuator for Humidity
@app.route('/action1', methods=['POST'])
def action1():
    try:
        # Extract sensor type and command from the POST request body
        sensor_type = request.json.get('sensor_type')
        command = request.json.get('command')

        # Check if sensor type and command are provided
        if not sensor_type or not command:
            return jsonify({'error': 'Both sensor type and command must be provided'}), 400

        # Publish the command to the MQTT topic
        myMQTTClient.publish(f"command/{sensor_type.lower()}", command, 0)

        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)})

# Function to manually control the actuator for Temperature
@app.route('/action2', methods=['POST'])
def action2():
    try:
        # Extract sensor type and command from the POST request body
        sensor_type = request.json.get('sensor_type')
        command = request.json.get('command')

        # Check if sensor type and command are provided
        if not sensor_type or not command:
            return jsonify({'error': 'Both sensor type and command must be provided'}), 400

        # Publish the command to the MQTT topic
        myMQTTClient.publish(f"command/{sensor_type.lower()}", command, 0)

        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)})

# Function to manually control the actuator for Lighting
@app.route('/action3', methods=['POST'])
def action3():
    try:
        # Extract sensor type and command from the POST request body
        sensor_type = request.json.get('sensor_type')
        command = request.json.get('command')

        # Check if sensor type and command are provided
        if not sensor_type or not command:
            return jsonify({'error': 'Both sensor type and command must be provided'}), 400

        # Publish the command to the MQTT topic
        myMQTTClient.publish(f"command/{sensor_type.lower()}", command, 0)

        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)})

# Route to get humidity data
@app.route('/humidity')
def humidity():
    try:
        # Scan the DynamoDB table for items where 'Sensor_Type' is 'Humidity'
        response = table.scan(FilterExpression=Attr('Sensor_Type').eq('Humidity'))
        items = response['Items']

        # Convert items to the desired format
        data = [
            {
                'Sensor_Type': item['Sensor_Type'],
                'Average_Value1': item['Average_Value1'],
                'Average_Value2': item['Average_Value2'],
                'City': item['City'],
                'Time': item['Time'],
                'Weather_Condition': item['Weather_Condition'],
                'Wind_Speed': item['Wind_Speed']
            }
            for item in items
        ]
        # Return data as JSON
        return jsonify({'data': data})
    except Exception as e:
        # If there is an error, return it as a JSON response
        return jsonify({'error': str(e)})

# Route to display humidity data
@app.route('/humidity_view')
def humidity_view():
    return render_template('humidity.html')

# Route to get temperature data
@app.route('/temperature')
def temperature():
    try:
        response = table.scan(FilterExpression=Attr('Sensor_Type').eq('Temperature'))
        items = response['Items']
        data = [
            {
                'Sensor_Type': item['Sensor_Type'],
                'Average_Value1': item['Average_Value1'],
                'Average_Value2': item['Average_Value2'],
                'City': item['City'],
                'Time': item['Time'],
                'Weather_Condition': item['Weather_Condition'],
                'Wind_Speed': item['Wind_Speed']
            }
            for item in items
        ]
        return jsonify({'data': data})
    except Exception as e:
        return jsonify({'error': str(e)})

# Route to display temperature data
@app.route('/temperature_view')
def temperature_view():
    return render_template('temperature.html')

# Route to get lighting data
@app.route('/lighting')
def lighting():
    try:
        response = table.scan(FilterExpression=Attr('Sensor_Type').eq('Lighting'))
        items = response['Items']
        data = [
            {
                'Sensor_Type': item['Sensor_Type'],
                'Average_Value1': item['Average_Value1'],
                'Average_Value2': item['Average_Value2'],
                'City': item['City'],
                'Time': item['Time'],
                'Weather_Condition': item['Weather_Condition'],
                'Wind_Speed': item['Wind_Speed']
            }
            for item in items
        ]
        return jsonify({'data': data})
    except Exception as e:
        return jsonify({'error': str(e)})

# Route to display lighting data
@app.route('/lighting_view')
def lighting_view():
    return render_template('lighting.html')

# Route to display home page
@app.route('/')
def index():
    return render_template('index.html')

if __name__ == "__main__":
    app.run(host="0.0.0.0",debug=False)