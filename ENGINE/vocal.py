import pyttsx3


def initialize():
    global engine
    engine = pyttsx3.init('sapi5')
    voices = engine.getProperty('voices')
    # print(voices[1].id)
    engine.setProperty('voice', voices[0].id)


def speak(audio):
    global engine
    engine.say(audio)
    engine.runAndWait()
    print("DragonZpyder: " + audio)