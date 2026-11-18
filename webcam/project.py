import ctypes
from datetime import datetime
import queue
import socket
import sys
import time
import urllib.parse
import subprocess
import os
import re
import webbrowser
import keyboard
import pyaudiowpatch as pyaudio
import pyautogui as pa
import pyttsx3
import json
import pyperclip
from vosk import Model, KaldiRecognizer
import threading
from playsound3 import playsound
import speech_recognition as sr
sys.modules["pyaudio"] = pyaudio

command_queue = queue.Queue()
speech_lock = threading.Lock()
recognizer = sr.Recognizer()

model_path = "vosk-model-small-en-us-0.15"
if not model_path:
  raise FileNotFoundError("Download a Vosk model folder into your directory.")

model = Model(model_path)
rec = KaldiRecognizer(model, 16000)

def speak(text):
  if not text:
    return
  with speech_lock:
    try:
      engine = pyttsx3.init("sapi5")
      voices = engine.getProperty("voices")
      engine.setProperty("voice", voices[0].id)
      engine.say(text)
      engine.runAndWait()
      engine.stop()
    except Exception as e:
      print(f"[Speech Error]: {e}")

def listen():
  with sr.Microphone() as source:
    print("🎤 Say something...")
    try:
      recognizer.adjust_for_ambient_noise(source, duration=0.8)
      audio = recognizer.listen(source, timeout=5, phrase_time_limit=8)
      voice = recognizer.recognize_google(audio)
      return voice.lower()
    except sr.WaitTimeoutError:
      speak("I did not hear you.")
    except sr.UnknownValueError:
      speak("I could not understand.")
    except sr.RequestError:
      speak("Check your internet connection and try again.")
    except Exception:
      speak("Say that again please...")
  return None

def vosk_listener_thread():
  pa_audio = pyaudio.PyAudio()
  stream = pa_audio.open(
      format=pyaudio.paInt16,
      channels=1,
      rate=16000,
      input=True,
      frames_per_buffer=8192,
  )
  stream.start_stream()

  print("listener active...")

  while True:
    data = stream.read(4000, exception_on_overflow=False)
    if rec.AcceptWaveform(data):
      result = json.loads(rec.Result())
      text = result.get("text", "").lower()

      if "jarvis" in text:
        print(f"\n[WAKE WORD DETECTED]: {text}")
        speak("Yes boss")

        command = text.replace("jarvis", "").strip()

        if command:
          print(f"[EXTRACTED COMMAND]: {command}")
          command_queue.put(command)
        else:
          voice_text = listen()
          if voice_text:
            print(f"[HEARD]: {voice_text}")
            command_queue.put(voice_text)

def check_internet():
  try:
    socket.create_connection(("8.8.8.8", 53), timeout=2)
  except OSError:
    speak("Check the internet connection.")


COMMANDS = {}


def register_command(*keywords):
  def wrapper(func):
    for kw in keywords:
      COMMANDS[kw] = func
    return func
  return wrapper


@register_command("exit", "quit", "goodbye")
def handle_exit(com):
  speak("Have a good day, boss.")
  os._exit(0)



@register_command("open")
def handle_open_apps(com):
    app_name = re.sub(r"\bopen\b", "", com, count=1).strip()
    if not app_name:
        speak("What application would you like me to open?")
        return
    if "settings" in app_name:
        subprocess.Popen("start ms-settings:", shell=True)
        speak("Opening settings.")
        return
    elif "file explorer" in app_name or "explorer" in app_name:
        subprocess.Popen("explorer")
        speak("Opening File Explorer.")
        return
    try:
        if "terminal" in app_name or "cmd" in app_name:
            app_name = "cmd"
        subprocess.Popen(f"start {app_name}", shell=True)
        speak(f"Opening {app_name}.")
    except Exception as e:
        print(f"[App Error]: {e}")
        speak(f"I could not open {app_name}.")


@register_command("play")
def handle_youtube(com):
  query = re.sub(r"\bplay\b", "", com, count=1).strip()
  if not query:
    speak("What would you like me to play?")
    return
  encoded_query = urllib.parse.quote(query)
  webbrowser.open(
      f"https://youtube.com/results?search_query={encoded_query}"
  )
  speak(f"Searching YouTube for {query}")

@register_command("volume up", "increase volume")
def handle_vol_up(com):
  pa.press("volumeup", presses=5)


@register_command("volume down", "decrease volume")
def handle_vol_down(com):
  pa.press("volumedown", presses=5)


@register_command("mute", "unmute")
def handle_mute(com):
  pa.press("volumemute")


@register_command("pause", "resume", "stop music")
def handle_media_pause(com):
  pa.press("playpause")


@register_command("say")
def handle_say(com):
  text_to_say = re.sub(r"\bsay\b", "", com, count=1).strip()
  print(f"[SAY]: {text_to_say}")
  speak(text_to_say)

@register_command("change tab", "switch tab")
def handle_change_tab(com):
  numbers = re.findall(r"\d+", com)
  times = int(numbers[0]) if numbers else 1

  if times == 1:
    pa.hotkey("alt", "tab")
  elif times > 1:
    pa.keyDown("alt")
    for _ in range(times):
      pa.press("tab")
      time.sleep(0.1)
    pa.keyUp("alt")

@register_command("now", "time")
def handle_time(com):
  current_time = datetime.now().strftime("%I:%M %p")
  speak(f"It is {current_time}")

def parse_number_from_text(text):
  digits = re.findall(r"\d+", text)
  if digits:
    return int(digits[0])

  number_words = {
      "one": 1,
      "two": 2,
      "three": 3,
      "four": 4,
      "five": 5,
      "six": 6,
      "seven": 7,
      "eight": 8,
      "nine": 9,
      "ten": 10,
      "eleven": 11,
      "twelve": 12,
      "fifteen": 15,
      "twenty": 20,
      "thirty": 30,
      "forty": 40,
      "fifty": 50,
      "sixty": 60,
  }

  words = text.split()
  for word in words:
    if word in number_words:
      return number_words[word]
  return None

@register_command("alarm", "timer")
def handle_alarm(com):
  minutes = parse_number_from_text(com)

  if minutes is None:
    speak("Sir, you have not mentioned the duration.")
    return

  seconds = minutes * 60
  speak(f"Timer started for {minutes} minutes.")

  def alarm_worker():
    time.sleep(seconds)
    threading.Thread(target=playsound, args=("music.wav",)).start()
    #speak("Hey boss! The timer is completed.")

  threading.Thread(target=alarm_worker, daemon=True).start()

@register_command("lock screen", "lock pc")
def handle_lock_screen(com):
  speak("Locking screen.")
  ctypes.windll.user32.LockWorkStation()

@register_command("photo", "camera", "take a picture")
def handle_media(com):
  pa.press("win")
  time.sleep(0.3)
  pa.write("camera")
  time.sleep(0.8)
  pa.press("enter")
  time.sleep(3)
  pa.press("space")

@register_command("read")
def reading(com):
    statement = pyperclip.paste()

    if statement and statement.strip():
        speak(statement)
        print(f"the code was   ~~~~~   {statement}")
    else:
        speak("BOSS. you have not copied any text")
        print("hey NOTHING")

def execute_command(com):
  com = com.lower().strip()
  sub_com = " ".join(com.split()[:2])
  print("~~~~~~~~~~~~~~~~", sub_com)

  for keyword, action in COMMANDS.items():
    if re.search(rf"\b{re.escape(keyword)}\b", com):
      print( re.search(rf"\b{re.escape(keyword)}\b", com))
      action(com)
      return

  speak(f"Sorry boss, I don't have a command for {com}.")


# def on_hotkey_triggered():
#   print("\n[TRIGGERED] Hotkey pressed!")
#   speak("Yes boss")
#   voice_text = listen()
#   if voice_text:
#     print(f"[HEARD]: {voice_text}")
#     command_queue.put(voice_text)


def greet_user():
  hour = datetime.now().hour
  if hour < 12:
    speak("Good morning boss")
  elif hour < 18:
    speak("Good afternoon boss")
  else:
    speak("Good evening boss")


if __name__ == "__main__":
    check_internet()
    greet_user()
    threading.Thread(target=vosk_listener_thread, daemon=True).start()

    try:
        while True:
          com = command_queue.get()
          execute_command(com)
    except (KeyboardInterrupt, RuntimeError):
        speak("Goodbye boss.")
        sys.exit(0)