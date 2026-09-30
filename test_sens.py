import speech_recognition as sr
import audioop

r = sr.Recognizer()
r.energy_threshold = 90
r.dynamic_energy_threshold = False
r.pause_threshold = 0.4

print("SpeechRecognizer configured with high sensitivity (energy_threshold=90, pause=0.4s)")
