import pyaudio
import audioop
import time

p = pyaudio.PyAudio()

try:
    stream = p.open(format=pyaudio.paInt16, channels=1, rate=16000, input=True, frames_per_buffer=1024)
    print("Stream opened successfully! Recording 2 seconds of audio levels...")
    for _ in range(20):
        data = stream.read(1024, exception_on_overflow=False)
        rms = audioop.rms(data, 2)
        bars = int(min(20, rms / 150))
        print(f"RMS: {rms:5d} | {'|' * bars}")
        time.sleep(0.05)
    stream.stop_stream()
    stream.close()
    print("PyAudio live meter test passed successfully!")
except Exception as e:
    print(f"Error testing PyAudio stream: {e}")
finally:
    p.terminate()
