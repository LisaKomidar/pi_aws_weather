import os
import urllib2
import json
import glob
import time
import RPi.GPIO as io
from sense_hat import SenseHat 
from AWSIoTPythonSDK.MQTTLib import AWSIoTMQTTClient
import calendar
import subprocess

# --------- User Settings ---------
STATE = "PA"
CITY = "Kane"
SENSOR_LOCATION_NAME = "Kane"
WUNDERGROUND_API_KEY = "wunderground_key" #wunderground key
BUCKET_NAME = ":partly_sunny: " + CITY + " Weather"
BUCKET_KEY = "shwu1"
ACCESS_KEY = "accesskey" #access key from wunderground
MINUTES_BETWEEN_READS = 15
METRIC_UNITS = False
# AWS IoT certificate based connection
myMQTTClient = AWSIoTMQTTClient("lk_pi") #IoT device name from AWS
myMQTTClient.configureEndpoint(".iot.us-west-2.amazonaws.com", 8883) #Endpoint from AWS
myMQTTClient.configureCredentials("rootCA.cert.pem", ".private.pem.key", ".pem.crt")  #cert file locations
myMQTTClient.configureOfflinePublishQueueing(-1)  # Infinite offline Publish queueing
myMQTTClient.configureDrainingFrequency(2)  # Draining: 2 Hz
myMQTTClient.configureConnectDisconnectTimeout(10)  # 10 sec
myMQTTClient.configureMQTTOperationTimeout(5)  # 5 sec
#connect and publish
myMQTTClient.connect()
myMQTTClient.publish("thing01/info", "connected", 0)

def isFloat(string):
    try:
        float(string)
        return True
    except ValueError:
        return False

def get_smooth(x):
	if not hasattr(get_smooth, "t"):
		get_smooth.t = [x,x,x]
	get_smooth.t[2] = get_smooth.t[1]
	get_smooth.t[1] = get_smooth.t[0]
	get_smooth.t[0] = x
	xs = (get_smooth.t[0]+get_smooth.t[1]+get_smooth.t[2])/3
	return(xs)

def get_conditions():
	api_conditions_url = "http://api.wunderground.com/api/" + WUNDERGROUND_API_KEY + "/conditions/q/" + STATE + "/" + CITY + ".json"
	try:
	  	f = urllib2.urlopen(api_conditions_url)
	except:
		print "Failed to get conditions"
		return []
	json_conditions = f.read()
	f.close()
	return json.loads(json_conditions)

def get_cpu_temp():
    	res = os.popen("vcgencmd measure_temp").readline()
    	t = float(res.replace("temp=","").replace("'C\n",""))
    	return(t)

def main():
	sense = SenseHat()
	conditions = get_conditions()
	if ('current_observation' not in conditions):
		print "Error! Wunderground API call failed, check your STATE and CITY and make sure your Wunderground API key is valid!"
		if 'error' in conditions['response']:
			print "Error Type: " + conditions['response']['error']['type']
			print "Error Description: " + conditions['response']['error']['description']
		exit()
	else:
		print('Connected to Wunderground')
	while True:
		# -------------- Sense Hat --------------
		#temp_c = sense.get_temperature()
		#humidity = sense.get_humidity() 
		#pressure_mb = sense.get_pressure() 
        	t1 = sense.get_temperature_from_humidity()
        	t2 = sense.get_temperature_from_pressure()
        	t_cpu = get_cpu_temp()
        	humidity = round(sense.get_humidity(),1)
        	p = round(sense.get_pressure(),1)
	        t = (t1+t2)/2
	        t_corr = t - ((t_cpu-t)/1.5)
	        t_corr = get_smooth(t_corr)
	        temp_f = round(1.8 * round(t_corr, 1) + 32)

		# -------------- Wunderground --------------
		conditions = get_conditions()
		if ('current_observation' not in conditions):
			print "Error! Wunderground API call failed. Skipping a reading then continuing ..."
		else:
			humidity_pct = conditions['current_observation']['relative_humidity']
			o_humidity = float(humidity_pct.replace("%",""))
			o_temp = float(conditions['current_observation']['temp_f'])
			wind_mph = float(conditions['current_observation']['wind_mph'])
		ts = calendar.timegm(time.gmtime())
        	print("temp=%.1f Outside Temp=%.1f  Humidity%1f  Outside Humidity=%.1f  time=%.1f" % (temp_f, o_temp, humidity, o_humidity, ts))
		sense.show_message("Temperature F: " + str(temp_f) + " Humidity: " + str( humidity))
		delay_s = 14400
		sensor_sn =  '0000001'
		topic = 'myrpi/' + sensor_sn
		# write to AWS
        	msg1 =  '"device_id": "{:s}", "timestamp":"{}", "inside temp": "{}", "outside temp": "{}"'.format(sensor_sn, ts, temp_f, o_temp)
		msg2 =  '"inside humidity":"{}", "outside humidity":"{}","wind":"{}"'.format(humidity, o_humidity, wind_mph)
	        msg = '{'+msg1+','+msg2+'}'
        	myMQTTClient.publish(topic, msg, 1)

		topic = 'myrpi/' + sensor_sn
		time.sleep(delay_s)

if __name__ == "__main__":
    main()


