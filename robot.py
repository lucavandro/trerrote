import TB6612
import speech_recognition
import pyttsx
import socket
import RPi.GPIO as GPIO
import time
from threading import Thread
import logging


class NoInternetConnection(Exception):
    pass


class Robot:

    UNKNOWN_CMD = "UNKNOWN"
    TIMEOUT = "TIMEOUT"
    GOOGLE_CLOUD_SPEECH_CREDENTIALS = None
    motorA = TB6612.Motor(17)
    motorB = TB6612.Motor(18)
    is_connected = False  # Indica la presenza o meno della connessione ad internet
    checking_for_internet = False  # True se il thread per il controllo di internet sta girando
    recognizer = speech_recognition.Recognizer()
    command_list = [
        "avanti",
        "indietro",
        "destra",
        "sinistra"
    ]

    def __init__(self, debug=False):
        self.DEBUG = debug
        # Inizializzazione logger
        logging.basicConfig(
            filename='robot.log',
            level=logging.DEBUG,
            format='[%(asctime)s][%(levelname)s] %(message)s',
            datefmt='%d/%m/%Y %H:%M:%S'
            )
        logging.info("Session started" if not debug else "Session started DEBUG MODE")

        try:
            self.mic = speech_recognition.Microphone(sample_rate=16000)
        except Exception:
            self.mic = speech_recognition.Microphone()
            logging.error("Microphone can't be started with sample_rate=16000. SUGGESTION: change microphone")

    def __enter__(self):
        """
        Imposta i motori e avvia la calibrazione del microfono
        """
        self.setup_motors()
        self.calibrate_microphone()

    def recognize_with_google(self, audio):
        """
        Effettua il riconoscimento vocale con google in presenza di
        connessione di rete, altrimenti genera un eccezione
        """
        if not self.is_connected:
            raise NoInternetConnection("Robot not connected to the Internet")

        # Fallback in caso di mancato caricamento delle credenziali di Google Cloud Speech
        if self.GOOGLE_CLOUD_SPEECH_CREDENTIALS is None:
            return self.recognize_with_sphinx(audio)

        return self.recognizer.recognize_google_cloud(
            audio_data=audio,
            credentials_json=self.google_cloud_speech_credentials,
            language="it-IT",
            preferred_phrases=self.command_list
        )

    def recognize_with_sphinx(self, audio):
        """
        Effettua il riconoscimento vocale con pocketsphinx
        """
        return self.recognizer.recognize_sphinx(
            audio_data=audio,
            language="it-IT",
            keyword_entries=[(cmd, 1.0) for cmd in self.command_list]
        )

    def recognize(self, audio):
        """
        Converte un file audio in una stringa utilizzando Google Cloud
        """
        try:
            result = self.recognize_google_cloud(audio) if self.is_connected else self.recognize.sphinx(audio)
        except speech_recognition.UnknownValueError:
            logging.error("Could not understand audio")
            result = Robot.UNKNOWN_CMD
        except speech_recognition.RequestError as e:
            logging.error("Recog Error; {0}".format(e))
            result = Robot.TIMEOUT
        except speech_recognition.WaitTimeoutError:
            logging.error("Timeout")
            result = Robot.TIMEOUT
        result = result.strip()

        if not any(result in cmd for cmd in self.command_list):
            logging.info("Command not in command list: " + result)

        return result

    def execute_command(self, cmd):
        if("avanti" in cmd or "anti" in cmd):
            self.say("Ok, vado avanti")
            if not self.DEBUG:
                self.go_forward()
        elif("indietro" in cmd or "dietro" in cmd):
            self.say("Ok, vado indietro")
            if not self.DEBUG:
                self.go_backward()
        elif("sinistra" in cmd):
            self.say("Ok, giro a sinistra")
            if not self.DEBUG:
                self.turn_left()
        elif("destra" in cmd):
            self.say("Ok, giro a destra")
            if not self.DEBUG:
                self.turn_right()
        elif(cmd == Robot.UNKNOWN_CMD):
            self.say("Non ho capito, ripeti")

    def start_listening(self):
        """
        Resta in ascolto per 2 secondi ogni 0.5s
        """
        while True:
            self.listen()
            time.sleep(0.5)

    def listen(self, time_limit=2):
        with self.mic as source:
            audio = self.recognizer.listen(source, phrase_time_limit=time_limit)
            cmd = self.recognize(audio)
            self.execute_command(cmd)

    def say(self, what):
        """
        Prodouce un suono data una stringa (what)
        """
        engine = pyttsx.init(driverName="espeak", debug=self.DEBUG)
        engine.setProperty("voice", "italian")
        engine.say(what)
        engine.runAndWait()
        engine.stop()
        del engine

    def start_checking_internet(self):
        """
        Attiva un thread in background che controlla ogni 2 secondi
        la connessione ad internet.
        """
        if not self.checking_for_internet:

            def checking_thread_func():
                while self.checking_for_internet:
                    self.is_connected = self.internet_on()
                    time.sleep(2)

            self.intenet_checking_thread = Thread(target=checking_thread_func)
            self.intenet_checking_thread.daemon = True
            self.intenet_checking_thread.start()
            self.checking_for_internet = True

    def stop_checking_internet(self):
        """
        Invia il comanda per la chiusura del thread di controllo della connessione
        e attende la sua terminazione
        """
        self.checking_for_internet = False
        self.intenet_checking_thread.join()
        while self.intenet_checking_thread.isAlive():
            time.sleep(1)

    def go_forward(self, interval=3, speed=100):
        self.motorA.forward()
        self.motorB.forward()
        self.motorA.speed = self.motorB.speed = speed
        time.sleep(interval)
        self.stop_motors()

    def go_backward(self, interval=3, speed=100):
        self.motorA.backward()
        self.motorB.backward()
        self.motorA.speed = self.motorB.speed = speed
        time.sleep(interval)
        self.stop_motors()

    def turn_left(self, interval=0.8, speed=100):
        """
        Esegue una rotazione in senso antiorario
        """
        self.motorA.backward()
        self.motorB.forward()
        self.motorA.speed = self.motorB.speed = speed
        time.sleep(interval)
        self.stop_motors()

    def turn_right(self, interval=0.8, speed=100):
        """
        Esegue una rotazione in senso orario
        """
        self.motorA.forward()
        self.motorB.backward()
        self.motorA.speed = self.motorB.speed = speed
        time.sleep(interval)
        self.stop_motors()

    def internet_on(self, host="8.8.8.8", port=53, timeout=1):
        """
        Controllo della connessione con ping al DNS di google
        Host: 8.8.8.8 (google-public-dns-a.google.com)
        OpenPort: 53/tcp
        Service: domain (DNS/TCP)
        """
        try:
            socket.setdefaulttimeout(timeout)
            socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect((host, port))
            return True
        except Exception:
            return False

    def calibrate_microphone(self):
        """
        Calibrazione del microfono
        """
        with self.mic as source:
            self.recognizer.adjust_for_ambient_noise(source)
            logging.info("Calibration completed. Energy threshold set to " + self.recognizer.energy_threshold)

    def setup_motors(self):
        """
        Inizializzazione motori
        """
        GPIO.setmode(GPIO.BCM)
        GPIO.setup((27, 22), GPIO.OUT)
        a = GPIO.PWM(27, 60)
        b = GPIO.PWM(22, 60)
        a.start(0)
        b.start(0)

        self.motorA.debug = self.DEBUG
        self.motorB.debug = self.DEBUG
        self.motorA.pwm = lambda value: a.ChangeDutyCycle(value)
        self.motorB.pwm = lambda value: b.ChangeDutyCycle(value)

    def stop_motors(self):
        """
        Ferma i motori se attivi. Per sicurezza fermare i motori dopo averli utilizzati
        e al termine del programma
        """
        self.motorA.stop()
        self.motorB.stop()

    def __exit__(self, type, value, traceback):
        self.stop_motors()
        self.stop_checking_internet()

    def load_google_cloud_credentials(self):
        try:
            with open('google-cloud-speech-credentials.json', 'r') as credentials:
                self.GOOGLE_CLOUD_SPEECH_CREDENTIALS = credentials.read()
        except:
            logging.error("Google cloud speech credentials can not be found")
