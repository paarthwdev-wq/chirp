import pyaudio

p = pyaudio.PyAudio()
default_host_api = p.get_default_host_api_info()
print(f"Default Host API: {default_host_api.get('name')}")

try:
    default_input = p.get_default_input_device_info()
    print(f"Default Input Device: [{default_input.get('index')}] {default_input.get('name')}")
except Exception as e:
    print(f"Could not get default input device: {e}")

print("\nAll Recording Devices:")
for i in range(p.get_device_count()):
    try:
        dev = p.get_device_info_by_index(i)
        if dev.get('maxInputChannels') > 0:
            print(f"Index {i:2d}: {dev.get('name')} | Channels: {dev.get('maxInputChannels')} | Rate: {dev.get('defaultSampleRate')}")
    except Exception:
        pass

p.terminate()
