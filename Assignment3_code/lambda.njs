const AWS = require('aws-sdk');
const dynamodb = new AWS.DynamoDB.DocumentClient();
const TableName = 'iotnodes_data';
const https = require('https');

const generateUniqueId = () => {
  return Math.random().toString(36).substring(2) + Date.now().toString(36);
};

const getData = (path) => new Promise((resolve, reject) => {
    const options = {
        host: 'api.openweathermap.org',
        port: 443,
        path,
        method: 'GET'
    };
    const req = https.request(options, res => {
        let buffer = '';
        res.on('data', chunk => buffer += chunk);
        res.on('end', () => resolve(JSON.parse(buffer)));
    });
    req.on('error', e => reject(e.message));
    req.end();
});

exports.handler = async (event) => {
    console.log('Received event:', JSON.stringify(event));

    try {
        const { Sensor_Type, Average_Value1, Average_Value2, Time } = event;
        const uniqueId = generateUniqueId();
        const itemId = `${Sensor_Type}-${uniqueId}`;

        const city = "Kuching";
        const apiKey = process.env.OPENWEATHER_API_KEY;
        const path = `/data/2.5/weather?q=${city}&appid=${apiKey}`;

        const weatherData = await getData(path);
        console.log('Received weather data:', JSON.stringify(weatherData));

        const enrichedData = {
            ID: itemId,
            Sensor_Type,
            Average_Value1,
            Average_Value2,
            Time,
            City: weatherData.name,
            Weather_Condition: weatherData.weather && weatherData.weather[0] ? weatherData.weather[0].description : null,
            Wind_Speed: weatherData.wind ? weatherData.wind.speed : null
        };

        console.log('Enriched data:', JSON.stringify(enrichedData));

        const params = {
            TableName,
            Item: enrichedData
        };

        await dynamodb.put(params).promise();
        console.log('Enriched data added to DynamoDB');

        return {
            statusCode: 200,
            body: JSON.stringify('Enrichment and storage of sensor data completed successfully!')
        };
    } catch (error) {
        console.error('Error occurred during data storing:', error);
        throw error;
    }
};