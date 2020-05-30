from __future__ import print_function
import os
import time
import speech_recognition as sr
from gtts import gTTS
import playsound
import webbrowser
import smtplib
import wikipedia
import pyttsx3
import datetime
import requests
from io import BytesIO
from io import StringIO
import pyowm
import sounddevice as sd 
from scipy.io.wavfile import write 
import numpy as np 
from PIL import ImageGrab
import time
from selenium import webdriver
import pyautogui as pg 
import clipboard
import pyperclip
from googletrans import Translator
from twilio.rest import Client
from twilio.twiml.messaging_response import MessagingResponse
from flask import Flask,request,redirect
from email.message import EmailMessage
import wolframalpha
import random
import datetime
import pickle
import os.path
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import pytz
import subprocess
import testcode
from tkinter import *
from tkinter import scrolledtext
from tkinter.ttk import *
import youtube_dl
import tkinter as tk
import roman
import PIL.Image, PIL.ImageTk









calendarscope = ['https://www.googleapis.com/auth/calendar']
gmailscope = ['https://www.googleapis.com/auth/gmail.readonly']
MONTHS = ["january", "february", "march", "april", "may", "june","july", "august", "september","october", "november", "december"]
DAYS =["sunday","monday", "tuesday", "wednesday", "thursday", "friday", "saturday"]
DAY_EXTENTIONS = ["rd", "th", "st", "nd"]

engine = pyttsx3.init('sapi5')
voices = engine.getProperty('voices')
# print(voices[1].id)
engine.setProperty('voice', voices[0].id)


def speak(audio):
    engine.say(audio)
    engine.runAndWait()
    print("DragonZpyder: " +audio)
    
    
    
#First of all you need to download rainmeter for this


speak("Starting Engine")
speak("Collecting required resources")
speak("initializing")
speak("Getting information from the CPU")
speak("contacting with mail services")
os.startfile("Your_rainmeter_url")
playsound.playsound('power up.mp3')


name="Aaryan"
age="15"
email_id="your-gmail-here"
email_id_password="your-gmail-password-here"
gender="Sir"
city="Kathmandu"
dad="your-contacts-gmail"
mom="your-contacts-gmail"
sis="your-contacts-gmail"
account_sid = 'your-twilio-acc-sid'
auth_token = 'your-twilio-acc-token'

client = Client(account_sid,auth_token)

startmin = int(datetime.datetime.now().hour)

def sleeptime():
    
    if os.path.exists("goodnight.txt"):
        starttime=int(datetime.datetime.now().minute)
        f = open("goodnight.txt", "r+")
        endtime = f.readlines()
        sleeptime = starttime - int(endtime[0])
        if sleeptime  < 1:
            speak("You Did not sleep at all Aaryan")
        else:    
            speak(f"You slept for {sleeptime} hours")


def authenticate_google():
    """Shows basic usage of the Google Calendar API.
    Prints the start and name of the next 10 events on the user's calendar.
    """
    creds = None
    if os.path.exists('calendar.pickle'):
        with open('calendar.pickle', 'rb') as token:
            creds = pickle.load(token)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'calendar.json', calendarscope)
            creds = flow.run_local_server(port=0)
        with open('calendar.pickle', 'wb') as token:
            pickle.dump(creds, token)

    service = build('calendar', 'v3', credentials=creds)

    return service 

def recievemsg():
    global msg 
    creds = None
    if os.path.exists('gmail.pickle'):
        with open('gmail.pickle', 'rb') as token:
            creds = pickle.load(token)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'gmail.json', gmailscope)
            creds = flow.run_local_server(port=0)
        with open('gmail.pickle', 'wb') as token:
            pickle.dump(creds, token)

    service = build('gmail', 'v1', credentials=creds)

    
    results= service.users().messages().list(userId="me",labelIds =['INBOX'],q="is:unread").execute()
    messages=results.get('messages', [])

    for message in messages:
        msg = service.users().messages().get(userId="me",id =message['id']).execute()
        no_of_messages = 0
        if not messages:
            print ("No new messages arrived yet")
        else:
            no_of_messages=no_of_messages+1
            email_data=msg['payload']['headers']
            for values in email_data:
                name=values["name"]
                if name=="From":
                    From_name=values["value"]
            speak(f"New message just recieved from {From_name}")
            speak("do you want me to read them?")
            ans = get_audio()
            if "yes" in ans:
                speak(msg["snippet"][:50])
            if "no" in ans:
                speak(f"okay {name} check your inbox as soon as possible")
            if "mark as read" in ans:
                service.users().messages().modify(userId='me', id =message['id'], body={'removeLabelIds': ['UNREAD']}).execute()

def mailservices():
    global msg 
    creds = None
    if os.path.exists('gmail.pickle'):
        with open('gmail.pickle', 'rb') as token:
            creds = pickle.load(token)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'gmail.json', gmailscope)
            creds = flow.run_local_server(port=0)
        with open('gmail.pickle', 'wb') as token:
            pickle.dump(creds, token)

    service = build('gmail', 'v1', credentials=creds)

    
    results= service.users().messages().list(userId="me",labelIds =['INBOX'],q="is:unread").execute()
    messages=results.get('messages', [])
    if not messages:
        speak ("No new messages in your inbox")
    else:
        no_of_messages=0
        for message in messages:
            msg = service.users().messages().get(userId="me",id =message['id']).execute()
            no_of_messages=no_of_messages+1
            email_data=msg['payload']['headers']
            for values in email_data:
                name=values["name"]
                if name=="From":
                    From_name=values["value"]
        speak(f"You have {str(no_of_messages)} new messages")
        speak("do you want me to show them")
        ans= get_audio()
        if "yes" in ans:
            webbrowser.open_new_tab("https://mail.google.com/mail/u/0/#inbox")
        else:
            get_audio()
        

def get_events(day, service):
    # Call the Calendar API
    date = datetime.datetime.combine(day, datetime.datetime.min.time())
    end = datetime.datetime.combine(day, datetime.datetime.max.time())
    utc = pytz.UTC
    date = date.astimezone(utc)
    end = end.astimezone(utc)
    events_result = service.events().list(calendarId='primary', timeMin=date.isoformat(), timeMax=end.isoformat(),
                                        singleEvents=True,
                                        orderBy='startTime').execute()
    events = events_result.get('items', [])

    if not events:
        speak(f'Woohoo! Seems that you have a holiday on this day')
    else:
        speak(f"You have {len(events)} events on this day")
        for event in events:
            start = event['start'].get('dateTime', event['start'].get('date'))
            print(start, event['summary'])
            start_time = str(start.split("T")[1].split("-")[0])
            if "00" in start_time.split(":")[1]:
               start_time = str(int(start_time.split(":")[0])) 
            else:
                start_time = str(int(start_time.split(":")[0])) + " " + start_time.split(":")[1]
                

            speak(f'You have {event["summary"]}  at  {start_time}')

def get_date(text):
    text = text.lower()
    today = datetime.date.today()

    if text.count("today") > 0:
        return today

    day = -1
    day_of_week = -1
    month = -1
    year = today.year

    for word in text.split():
        if word in MONTHS:
            month = MONTHS.index(word) + 1
        elif word in DAYS:
            day_of_week = DAYS.index(word)
        elif word.isdigit():
            day = int(word)
        else:
            for ext in DAY_EXTENTIONS:
                found = word.find(ext)
                if found > 0:
                    try:
                        day = int(word[:found])
                    except:
                        pass

    if month < today.month and month != -1:  
        year = year+1

    if month == -1 and day != -1:  
        if day < today.day:
            month = today.month + 1
        else:
            month = today.month

    if month == -1 and day == -1 and day_of_week != -1:
        current_day_of_week = today.weekday()
        dif = day_of_week - current_day_of_week

        if dif < 0:
            dif += 7
            if text.count("next") >= 1:
                dif += 7

        return today + datetime.timedelta(dif)

    if day != -1:  
        return datetime.date(month=month, day=day, year=year)

def note(text):
    date = datetime.datetime.now()
    file_name = str(date).replace(":", "-") + "-note.txt"
    with open(file_name, "w") as f:
        f.write(text)

    subprocess.Popen(["notepad.exe", file_name])

#Put your contacts and their data

contacts=["put-your-contacts-here"]
number = ['put-your-contacts number-here']
mails=["put-your-contacts "]

def twilio_send_msg():
    
    account_sid = 'AC4dd4c26fd55aa1cdf682fbae4665acc6'
    auth_token = 'f0e23b8379e87351127d055108bcd55c'


    client = Client(account_sid,auth_token)

    contact_name=text.split("text")
    contact=contact_name[1]
    try:
        if "dad" in contact:
            to="phone_number"

        if "mother" in contact:
            to ="phone_nuber"

        if "sister" in contact:
            to="phone_number"
    
    except: 
        speak(f"No contact named {contact} in my database")

    try:
        speak("okay Aaryan plz say me the content")
        body = get_audio()

        client.messages.create(body=body,
                        from_='your_twilio_num
                        to=to
                    )    
        speak("Message sent")

    except:
        speak("Faliure in sending message")


def twilio_call():

    global contacts 
    
    account_sid = 'AC4dd4c26fd55aa1cdf682fbae4665acc6'
    auth_token = 'f0e23b8379e87351127d055108bcd55c'

    client = Client(account_sid,auth_token)

    contact_name=text.split("call")
    contact=contact_name[1]
    if "dad" in contact or "Dad"  in contact:
        to="phone_number

    if "mother" in contact  or "Mother" in contact in contact:
        to ="phone_number

    if "sister" in contact or "Sister" in contact:
        to="phone_number

    else:
        speak(f"Hmmm seems like you have not registered the contact in my data base Aaryan so, I cant call {contact}")
    
    try:
        speak(f"Trying to call {contact} on {to}")
        call = client.calls.create(url='http://demo.twilio.com/docs/voice.xml',
                            to=to,
                            from_='+12675733927'
                        )
    except:
        print("Eror")


def twilio_reply():
    app=Flask(__name__)


    @app.route("/sms",methods=['GET','POST'])
    def twilio_recieve_msg():
        resp=MessagingResponse()
        speak("what do you want to reply")

        resp.message(get_audio)

        return str(resp)

    if __name__ == "__main__":
        app.run(debug=True)



def langtranslator():
    try:
        trans=Translator()
    

        speak("Say the language to translate in")
        language=get_audio().replace(" ","")
            

        
        speak("what to translate")
        content=get_audio()
            
        t=trans.translate(text=content,dest=language)
        speak(f"{t.origin} in {t.dest} is{t.text}")

    except:
        speak("error")


def convert():
    trans=Translator()
    

    speak("Say the language to translate in")
    language=get_audio().replace(" ","")
    pg.hotkey("ctrl",'c')
    tobespoken=pyperclip.paste()
    content=tobespoken
        
    t=trans.translate(text=content,dest=language)
    speak(f"{t.origin} in {t.dest} is{t.text}")


def database():
    Exception 
    if "what do I have" in text:
        get_audio()
    client = wolframalpha.Client('your_client')
    speak(f"Searching for {text} in my database")
    try:
        res = client.query(text)
        results = next(res.results).text
        speak(results)
    except:
        speak(f"Sir, your query {text} does not match any of the datani my data base.")
        speak("Try asking other things..")
        speak("sorry for in convinience sir")






def langtranslatorfromselectedin():
    trans=Translator()
    

    content=query[0]
    language=query[1]        

        
    t=trans.translate(text=content,dest=language)
    speak(f"{t.origin} in {t.dest} is{t.text}")


def locate():
    place=query[1]
    speak(f"according to my data base {place} lies here")
    webbrowser.open_new_tab("https://www.google.com/maps/place/"+place)

def weather_info():
    owm=pyowm.OWM('your_api)
    location=owm.weather_at_place(f'{city}')
    weather=location.get_weather()
    temp=weather.get_temperature('celsius')
    humidity=weather.get_humidity()
    date=datetime.datetime.now().strftime("%A:%d:%B:%Y")
    current_temp=temp['temp']
    maximum_temp=temp['temp_max']
    min_temp=temp['temp_min']
    speak(f'The current temperature on {city} is {current_temp} degree celsius ')
    speak(f'The estimated maximum temperature for today {date} on {city} is {maximum_temp} degree celcius')
    speak(f'The estimated minimum temperature for today {date} on {city} is {min_temp} degree celcius')
    speak(f'The air is {humidity}% humid today')

def weather_at_place():
    owm=pyowm.OWM('your-api-key')
    location=owm.weather_at_place(f'{city}')
    weather=location.get_weather()
    temp=weather.get_temperature('celsius')
    humidity=weather.get_humidity()
    date=datetime.datetime.now().strftime("%A:%d:%B:%Y")
    current_temp=temp['temp']
    maximum_temp=temp['temp_max']
    min_temp=temp['temp_min']
    speak(f'The current temperature on {city} is {current_temp} degree celsius ')
    speak(f'The estimated maximum temperature for today {date} on {city} is {maximum_temp} degree celcius')
    speak(f'The estimated minimum temperature for today {date} on {city} is {min_temp} degree celcius')
    speak(f'The air is {humidity}% humid today on {city}')






def wishMe():
    hour = int(datetime.datetime.now().hour)
    if hour>=0 and hour<12:
        speak("Good Morning!")

    elif hour>=12 and hour<18:
        speak("Good Afternoon!")   

    else:
        speak("Good Evening!")  

    strTime = datetime.datetime.now().strftime("%I:%M:%p").replace(":","").replace("None","")  

    speak(f"I am  DragonSpyder, {gender} Now it is {strTime} {weather_info()}")
    sleeptime()
    text="what do i have on " + datetime.datetime.now().strftime("%A")
    service=authenticate_google()        
    date = get_date(text)
    if date:
        get_events(date, service)
    mailservices()
    speak("Now, I am ready for your commands Please tell me how may I help you ")
    


def get_audio():

    #It tane input from the user and returns string outputkes micropho

    r = sr.Recognizer()
    with sr.Microphone() as source:
        print(" I am Listening...")
        r.phrase_time_limit=10
        audio = r.listen(source)

    try:   
        said = r.recognize_google(audio, language='en-in')
        print(f"{name} {gender} said: {said}\n")
    except: 
        return "None"
    return said

def wake_audio():
    r = sr.Recognizer()
    with sr.Microphone() as source:
        print("Waiting to help you")
        r.pause_threshold = 1
        audio = r.listen(source)

    try:   
        said = r.recognize_google(audio, language='en-in')
        print(f"{name} {gender} said: {said}\n")

    except: 
        return "None"
    return said
def calendar_audio():
    r = sr.Recognizer()
    with sr.Microphone() as source:
        print("Waiting to help you")
        r.pause_threshold = 1
        audio = r.listen(source)

    try:   
        said = r.recognize_google(audio, language='en-in')
        print(f"{name} {gender} said: {said}\n")

    except: 
        return "None"
    return said

def read():
    pg.hotkey("ctrl",'c')
    tobespoken=pyperclip.paste()
    speak(tobespoken)

def openafile():
    query=text.split("play")
    speak(f"searching for {query[1]} in my database")
    dir_path = os.path.dirname(os.path.realpath(__file__)) 
            
    try:
        for root,dirs,files in os.walk("G:\\VCS\\music"):
             for file in files:
                file_name=query[1]
                if file.startswith(file_name):
                    path= "C:"+'\\'+str(file) 
                    speak(f"opening {file_name}")
                    os.startfile(path)
    except:
        speak(f"no music named: {file_name}")

def sendEmail(to, content):
    server = smtplib.SMTP('smtp.gmail.com', 587)
    server.ehlo()
    server.starttls()
    server.login(email_id, email_id_password)
    server.sendmail(email_id, to, content)
    server.close()





def repeatmyspeech():
    speak("Okay starting to listen")
    speak(f"{name} {gender} start speaking")
    
    r = sr.Recognizer()
    with sr.Microphone() as source:
        print(" I am Listening...")
        r.pause_threshold = 1
        audio = r.listen(source)

    try:   
        said = r.recognize_google(audio, language='en-in')
        speak(f"{name} {gender} said: {said}\n")
        print(f"{name} {gender} hre is ur repetition by me {said}\n")
        try:
            speak("should i save the file?")
            ans=get_audio()
            if "yes" in ans:
                try:
                    speak("What should i keep the file name")
                    filename=get_audio().lower
                    said.save(filename+".mp3")   
                    speak("File saved sucessfully")
                    try:
                        speak("Do you want me to show it?")
                        reply=get_audio()
                        if "yes" in reply:
                            os.startfile(filename+".mp3")
                            speak("here it is")

                    except: 
                            if "no" in reply:
                                speak("Never mind")

                except: 
                    speak("Error in keeping filename")

        except: 
                speak("Okay")

    except:
            return "None"
    return said


    


def recsound():
    fs=44100
    speak("what should be the length of your sound wave Plz answer in seconds")
    ans=int(get_audio())
    seconds=ans

    recorded=sd.rec(int(seconds*fs),samplerate=fs,channels=2)
    sd.wait()
    speak("sucessfully recoreded")
    speak("what should i keep the file name")
    filename=get_audio()
    write(filename+'.mp3',fs,recorded)
    speak("sucessfuly saved")
    try:
        speak("should i show you")
        reply=get_audio()
        if "yes" in reply:
            os.startfile(filename+".mp3")

    except:
        if "no" in reply:
            speak("okay next command sir")

def Screenshot():
    image=pg.screenshot()
    speak("screen shot taken")
    speak("what do you want to save it as?")
    filename=get_audio()
    image.save(filename+".png")
    speak("do you want me to show it")
    ans=get_audio()
    if "yes" in ans:
        os.startfile(filename+".png")
    else:
        speak("never mind")

if __name__ == '__main__':
    wishMe()
    recievemsg() 
    while True:
                    if  startmin < 50 and startmin + 10 == int(datetime.datetime.now().minute):
                        recievemsg()
                    elif startmin >= 50 and abs(startmin - 50) == int(datetime.datetime.now().minute):
                        recievemsg()
                    text = get_audio()

                    if "what do I have" in text or "do I have plans" in text or "am I busy on" in text:
                        service=authenticate_google()
                        date = get_date(text)
                        if date:
                            get_events(date, service)
                            get_audio()
                        else:
                            get_audio()

                    if "wikipedia" in text or "Wikipedia" in text:
                        speak("Searching wikipedia...")
                        text=text.replace("wikipedia","")
                        results = wikipedia.summary(text, sentences=3)
                        speak("According to wikipedia")
                        print(results)
                        speak(results)

                    if "What is the weather out" in text:
                        city=(f"{city}")
                        weather_info()

                    if "what is the weather in" in text:
                        query=text.split("what is the weather in")
                        city=query[1]
                        weather_info()

                    if "search for"  in text:
                        test=text.replace("search for","")
                        database()
                    
                    if "what" in text or "What" in text:
                        database()

                    if "who" in text or "Who" in text:
                        database()

                    if "why" in text or "Who" in text:
                        database()
                    
                    if "where" in text or "Where" in text:
                        database()

                    if "play music" in text:
                        music_dir ="G:\\vcs\\music"
                        songs = os.listdir(music_dir)
                        print(songs)    
                        os.startfile(os.path.join(music_dir, songs[0]))
                    
                    if "open youtube" in text:
                        speak("Opening youtube")
                        webbrowser.open_new_tab("youtube.com")

                    if "open discord" in text:
                        speak("Opening Discord")
                        webbrowser.open_new_tab("discord.com")

                    if "open discord app" in text:
                        discord=input("Enter the path of discord: ")
                        os.startfile ("explorer.exe")
                        os.startfile(discord)


                    if "open terminal" in text:
                        os.startfile ("cmd")


                    if "what is the time" in text:
                                strTime = datetime.datetime.now().strftime("%I:%M:%p")    
                                speak(f"the time is {strTime}")

                    if"what is today's date" in text:
                                date=datetime.datetime.now().strftime("%A:%d:%B:%Y")
                                speak(f"Today is {date} ")

                    if "message" in text:
                        try:
                            speak("To whom")
                            identity=get_audio()
                            if identity in contacts:
                                index=contacts.index(identity)
                                to=mails[index]
                            else:
                                speak(f"Looks like {identity} is not in your contact   Plz typethe reciever's email address")
                                speak("Plz wait until the recipent taker window pops up")
                                root = Tk()
                                root.title("DragonZpyder")

                                root.geometry=("300x300")

                                label1=Label(root,text="Enter the recipient's mail: ",font = ("algerian",19,"bold")fg ='black').place(x=10,y=200)

                                entry=Entry(root,textvariable=to,width=25).place(x=200,y=210)
                                to=str(to.get())
                                submit = Button(root,text="submit",command=root.destroy).place(x=250,y=300)
                                root.mainloop()
                            
                            speak("say me the content")
                            content=get_audio()
                            sendEmail(to, content)
                            speak("Email has been sent!")
                        except Exception as e:
                            print(e)
                            speak("Sorry sir  I am not able to send this email")  

                    if "Dragon" in text or "hey" in text or "hello dragon" in text:
                        stMsgs = ['on your command sir', f'yes {name}', f'hello {name}', 'Waiting for your command sir']
                        speak(random.choice(stMsgs))

                    if "Thank You" in text or  "Thank you" in text or "thank you" in text or "thanks" in text:
                        rep=['Welcome','Well you know Aaryan im cool','Dont mention','By the way I should thank you for creating me']
                        speak(random.choice(rep))

                    if"say something" in text:
                        speak("what's your name?")

                    if "who created you" in text:
                        speak("I was created by Aaryan on eleventh of april on 2020")

                    if "who made you" in text:
                        speak("I was created by Aaryan on eleventh of april on 2020")  

                    if "how were you developed" in text:
                        speak("Sorry boss  I am not allowed to reveval all my secrets  ")

                    if "how are you developed" in text:
                        speak("Sorry boss  I am not allowed to reveval all of my secrets  ")

                    if "tell me a joke" in text or "Crack a joke" in text or "crack a joke" in text:
                        jokes =["A Doctor said to a patient , I'm sorry but you suffer from a terminal illness and have only 10 to live , then the Patient said What do you mean, 10, 10 what, Months, Weeks, and the Doctor said Nine.","Once my Brother who never used to drink was arrested for over drinking,When I lates had gone and asked him why were you arressted, He replied he had not brushed since a week","A Teacher said Kids, what does the chicken give you? The Student replied Meat Teacher said  Very good Now what does the pig give you? Student said BaconTeacher said  Great  And what does the fat cow give you? Student said Homework!","A child asked his father, How were people born? So his father said, Adam and Eve made babies, then their babies became adults and made babies, and so on  The child then went to his mother, asked her the same question and she told him, We were monkeys then we evolved to become like we are now  The child ran back to his father and said, You lied to me  His father replied, No, your mom was talking about her side of the family."]
                        speak(random.choice(jokes))
                        speak("Do you want more?")
                        ans=get_audio()
                        if "yes" in ans:
                            speak(random.choice(jokes))

                        if "no" in ans:
                            speak(random.choice(jokes))

                    if "who is Aryan" in text:
                        speak("Aaryan is my developer my teacher the one who taught me how be a good wise smart and a intelligent person Dragonspyder was previously his name And since he left the hacking world he gave this name to me and started programming with python then created me  Now i Am proud to be dragonspyder at last  ")
                                    
                    if "good morning" in text:
                        strTime = datetime.datetime.now().strftime("%H:%M:%S") 
                        speak(f"Good morning {name} {gender} it is {strTime} now,Hope you had a good sleep.")

                    if "good night" in text:
                        strTime = datetime.datetime.now().strftime("%X").replace(":"," ") 
                        gtime=strTime.replace(":"," ") 
                        speak(f"Good night {name} {gender} it is {gtime} sleep tight..")

                    if "open my inbox" in text:
                        webbrowser.open_new_tab("https://mail.google.com/mail/u/0/#inbox")

                    if "open my sent mail" in text:
                        webbrowser.open_new_tab("https://mail.google.com/mail/u/0/#sent")

                    if "open youtube and search for" in text:
                        query=text.split("open youtube and search for"),
                        speak("opening youtube")
                        webbrowser.open_new_tab(f"https://www.youtube.com/results?search_query={query[1]}")


                    if "repeat my speech" in text:
                        repeatmyspeech()

                    if "close chrome" in text:
                        os.system('TASKKILL /F /IM Google Chrome.exe')

                    if "close task manager" in text:
                        os.system('TASKKILL /F /IM Taskmgr.exe')


                    if "delete" in text:
                        final=text.split("delete")
                        os.system("del "+final[1])

                    if "shutdown" in text:
                        speak("okay,shutting down your pc")
                        os.system('shutdown/s')

                    if "restart my pc" in text:
                        speak("okay, restarting your pc")
                        os.system('shutdown/r')

                    if "record my voice" in text:
                        recsound()

                    if "take a screenshot" in text:
                        Screenshot()
                    
                    if "quit" in text:
                        speak(f"Thank you {name} for giving your time i had fun serving you,have a good time")
                        speak("closing engine")
                        speak("closing required applications")
                        endTime = int(datetime.datetime.now().hour)
                        f = open("goodnight.txt", "w+")
                        end = int(datetime.datetime.now().hour)
                        f.write(str(end))
                        f.close()
                        os.system('TASKKILL /F /IM Rainmeter.exe')
                        playsound.playsound("power down.mp3")
                        quit()
                    
                    if "type" in text:
                        speak(f"okay i am listening speak{name} {gender}")
                        pg.typewrite(get_audio())

                    if "select all" in text:
                        pg.hotkey('ctrl','a')

                    if "close this window" in text:
                        pg.hotkey('alt','f4')

                    if "open a new tab" in text:
                        pg.hotkey('ctrl','n')

                    if "open a new incognito window" in text:
                        pg.hotkey('ctrl','shift','n')

                    if "copy" in text:
                        pg.hotkey('ctrl','c')
                        speak('text copied to clipboard')

                    if "paste" in text:
                        pg.hotkey('ctrl','v')

                    if "undo" in text:
                        pg.hotkey('ctrl','z')

                    if "redo" in text:
                        pg.hotkey('ctrl',)

                    if "save" in text:
                        pg.hotkey('ctrl','s')

                    if "back" in text:
                        pg.hotkey('browserback')

                    if "go up" in text:
                        pg.hotkey('pageup') 

                    if "go to top" in text:
                        pg.hotkey('home')

                    if "read" in text:
                        try:
                            read()
                        except:
                            speak("no text selected plz select a text")

                    if "translate to" in text: 
                        query=text.split("translate to")
                        dest=query[1]
                        langtranslator()

                    if "Introduce yourself" in text:
                        speak("Okay,Let me start by The time I was born,,")
                        speak("I was a dream of a boy dreaming to make a perfect virtual assistant")
                        speak("He soon established the company named Dragonspyder")
                        speak("Slowly,I came to life")
                        speak("I started learning various things like calculations,General knowldge etc etc")
                        speak("Now I am capable of doing various things like Beatboxing,opening applications,Cracking jokes,Playing music etc.")
                        speak("Okay,thats a wrap I wont say more ")
                    
                    if "translate" in text:
                        langtranslator()

                    if "in" in text:
                        query=text.split("in")
                        text=query[0]
                        dest=[1]

                    if "convert selected " in text:
                        convert()

                    if "I am sad" in text:
                        playsound.playsound("hopetone.mp3")
                        playsound.playsound("alarm.mp3")
                        playsound.playsound("hopetone.mp3")
                        playsound.playsound("alarm.mp3")
                        playsound.playsound("hopetone.mp3")
                        playsound.playsound("alarm.mp3")

                    if "text" in text:
                        twilio_send_msg()

                    if "call" in text:
                        twilio_call()

                    if "remind me" in text:
                        os.system("python pyautogui1.py")

                    if "play" in text:
                        openafile()

                    if "locate" in text:
                        query=text.split("locate")
                        locate()

            

                    if "where is" in text:
                        query=text.split("where is")
                        locate()

                    if "none" in text:
                        get_audio()

                    if "I know that" in text:
                        speak("Ya, ure right")

                    if "what do I have" in text or "do I have plans" in text or "am I busy on" in text:
                        service=authenticate_google()
                        date = get_date(text)
                        if date:
                            get_events(date, service)
                            get_audio()
                        else:
                            get_audio()

                    if "beatbox" in text or "Beatbox" in text:
                        beatboxes=['beatbox (1).wav','beatbox (2).wav','beatbox (3).wav','beatbox (4).wav','beatbox (5).wav','beatbox (6).wav','beatbox (7).wav' ]
                        playsound.playsound(random.choice(beatboxes))
                    
                    if "make a note" in text or "write this down"  in text or "remember this" in text:
                        NOTE_STRS = ["make a note", "write this down", "remember this"]
                        for phrase in NOTE_STRS:
                            if phrase in text:
                                speak("What would you like me to write down? ")
                                write_down = get_audio()
                                note(write_down)
                                speak("I've made a note of that.")
                        break
