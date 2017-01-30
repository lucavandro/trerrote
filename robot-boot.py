import pyttsx
import speech_recognition
import time
import TB6612
import RPi.GPIO as GPIO
import pdb

motorA = TB6612.Motor(17)
motorB = TB6612.Motor(18)
Zitto = False

def speak(what):
	if(not Zitto):
	        engine = pyttsx.init(driverName="espeak", debug=True)
	        engine.setProperty("voice", "italian")
	    	engine.say(what)
	        engine.runAndWait()
	        engine.stop()
        	del engine
        
recognizer = speech_recognition.Recognizer()
mic = speech_recognition.Microphone(sample_rate=16000)
with mic as source:
    recognizer.adjust_for_ambient_noise(source)
    speak("Calibrazione completata")

DEBUG = False

with open('google-cloud-speech-credentials.json', 'r') as credentials:
    GOOGLE_CLOUD_SPEECH_CREDENTIALS = credentials.read()



def internet_on():
	import urllib2
  
	try:
		response=urllib2.urlopen('http://google.com',timeout=5)
    		return True
        except urllib2.URLError as err: pass
    	
    	return False
    
INTERNET_ON = internet_on()
    
def listen():
	try:	
		with mic as source:
			audio = recognizer.listen(source, phrase_time_limit=2)
			if INTERNET_ON:
				result = recognizer.recognize_google_cloud(
					audio_data = audio, 
					credentials_json=GOOGLE_CLOUD_SPEECH_CREDENTIALS,
					language = "it-IT", 
					preferred_phrases = ["avanti", "indietro", "destra", "sinistra","zitto","apertura"]
				)
			else:
				result = recognizer.recognize_sphinx(
	                    		audio_data=audio,
	                    		language="it-IT",
	                    		keyword_entries=[("avanti", 1.0), ("indietro", 1.0), ("destra", 1.0), ("sinistra", 1.0), ("zitto", 1.0), ("apertura", 1.0)]
	                    		
                		)	
                	
		
	except speech_recognition.UnknownValueError:
		print("Could not understand audio")
		result = "NoUnder"
	except speech_recognition.RequestError as e:
		print("Recog Error; {0}".format(e))
		result = "Timeout"
	except speech_recognition.WaitTimeoutError:
		print "Timeout"
            	result = "Timeout"
       	
       	return result.strip()

def destroy():
     motorA.stop()
     motorB.stop()


def setup_motors():
	GPIO.setmode(GPIO.BCM)
	GPIO.setup((27, 22), GPIO.OUT)
	a = GPIO.PWM(27, 60)
	b = GPIO.PWM(22, 60)
	a.start(0)
	b.start(0)

	def a_speed(value):
		a.ChangeDutyCycle(value)

	def b_speed(value):
		b.ChangeDutyCycle(value)

	
	motorA.debug = True
	motorB.debug = True
	motorA.pwm = a_speed
	motorB.pwm = b_speed
	

def go_forward():
	
	motorA.forward()
	motorB.forward()
	motorA.speed = 100
	motorB.speed = 100
        
       	time.sleep(3)
       	destroy()

def go_backward():

	motorA.backward()
        motorB.backward()
        motorA.speed = 100

	motorB.speed = 100
        
        time.sleep(1.5) 
       	destroy()

def turn_left():
	motorA.backward()
        motorB.forward()
        motorA.speed = 100
	motorB.speed = 100
        time.sleep(0.8)
       	destroy()   	

def turn_right():
	motorA.forward()
        motorB.backward()
        motorA.speed = 100
	motorB.speed = 100
        time.sleep(0.8)
       	destroy() 
       	
def main():
	global INTERNET_ON
	global Zitto
	if not DEBUG:
		setup_motors()
	
	result = None
	no_under_count = 0
	while(1):
		if result == "NoUnder":
			speak("Non ho capito, ripeti")
			if DEBUG:
				if INTERNET_ON:
					speak("Google")
				else:
					speak("Sphinx")
					
		else:
            		speak("Ciao, dammi un comando")
            	print "In ascolto"
            	#result = listen().strip()
		result = listen()
            	print result
            	if(("avanti" in result or "anti" in result) and not Zitto):
            		speak("Ok, vado avanti")
            		if not DEBUG: go_forward()
               	
            	elif("dietro" in result and not Zitto):
            		speak("Ok, vado indietro")
            		if not DEBUG: go_backward()
            		
            	elif( "sinistra" in result and not Zitto):
            	
            		speak("Ok, giro a sinistra")
            		if not DEBUG: turn_left()
            		
            	elif("destra" in result and not Zitto):
            		speak("Ok, giro a destra")
            		if not DEBUG: turn_right()
            	elif("zitto" in result):
            		speak("Ok padrone, sto zitto")
            		Zitto = True;
            	elif("apertura" in result and Zitto):
            		Zitto = False;
			speak("Buongiorno mondo")
            	elif(result == "Timeout" or result =="NoUnder"):
                        no_under_count += 1
                        if no_under_count > 10:
                        	speak("Sto verificando la connessione")
                        	INTERNET_ON = internet_on()
                        	no_under_count = 0
                else:
                	result = "NoUnder"
            	
       
if __name__ == '__main__':
	try:
		main()
							
	except KeyboardInterrupt:
		destroy()



