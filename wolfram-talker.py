'''
	Stolen from some random stackoverflow thread and mixed with other code...
'''

from array import array
from struct import unpack, pack

import os, sys
import pyaudio
import wave
import random
import tempfile
import subprocess
import urllib, urllib2
import json
import festival
import wap
import thread
import time


THRESHOLD = 4500
CHUNK_SIZE = 1024
FORMAT = pyaudio.paInt16
RATE = 44100

def is_silent(L):
    "Returns `True` if below the 'silent' threshold"
    return max(L) < THRESHOLD

def normalize(L):
    "Average the volume out"
    MAXIMUM = 16384
    times = float(MAXIMUM)/max(abs(i) for i in L)

    LRtn = array('h')
    for i in L:
        LRtn.append(int(i*times))
    return LRtn

def trim(L):
    "Trim the blank spots at the start and end"
    def _trim(L):
        snd_started = False
        LRtn = array('h')

        for i in L:
            if not snd_started and abs(i)>THRESHOLD:
                snd_started = True
                LRtn.append(i)

            elif snd_started:
                LRtn.append(i)
        return LRtn

    # Trim to the left
    L = _trim(L)

    # Trim to the right
    L.reverse()
    L = _trim(L)
    L.reverse()
    return L

def add_silence(L, seconds):
    "Add silence to the start and end of `L` of length `seconds` (float)"
    LRtn = array('h', [0 for i in xrange(int(seconds*RATE))])
    LRtn.extend(L)
    LRtn.extend([0 for i in xrange(int(seconds*RATE))])
    return LRtn

def record():
    """
    Record a word or words from the microphone and 
    return the data as an array of signed shorts.

    Normalizes the audio, trims silence from the 
    start and end, and pads with 0.5 seconds of 
    blank sound to make sure VLC et al can play 
    it without getting chopped off.
    """
    p = pyaudio.PyAudio()
    stream = p.open(format=FORMAT, channels=1, rate=RATE, 
                    input=True, output=True,
                    frames_per_buffer=CHUNK_SIZE)

    num_silent = 0
    snd_started = False

    LRtn = array('h')

    while 1:
        data = stream.read(CHUNK_SIZE)
        L = unpack('<' + ('h'*(len(data)/2)), data) # little endian, signed short
        L = array('h', L)
        LRtn.extend(L)

        silent = is_silent(L)
        #print silent, num_silent, L[:10], max(L)
        if max(L) > THRESHOLD:
        	color = '\033[91m'
        else:
        	color = '\033[81m'
        sys.stdout.write('\r[%s] %8d' % (color+'|'*(max(L)/512)+'\033[0m'+'-'*(64-max(L)/512), max(L)))
        sys.stdout.flush()
		
        if silent and snd_started:
            num_silent += 1
        elif not silent and not snd_started:
            snd_started = True
        elif not silent:
            num_silent = 0 # clear the counter
        if snd_started and num_silent > 30:
            break
    print
    sample_width = p.get_sample_size(FORMAT)
    stream.stop_stream()
    stream.close()
    p.terminate()

    LRtn = normalize(LRtn)
    LRtn = trim(LRtn)
    LRtn = add_silence(LRtn, 0.5)
    return sample_width, LRtn

def record_to_file(path):
    "Records from the microphone and outputs the resulting data to `path`"
    sample_width, data = record()
    data = pack('<' + ('h'*len(data)), *data)
    
    wf = wave.open(path, 'wb')
    wf.setnchannels(1)
    wf.setsampwidth(sample_width)
    wf.setframerate(RATE)
    wf.writeframes(data)
    wf.close()

class EnhancedFile(file):
    def __init__(self, *args, **keyws):
        file.__init__(self, *args, **keyws)

    def __len__(self):
        return int(os.fstat(self.fileno())[6])
        
if __name__ == '__main__':

    while(1):
        print("please speak a word into the microphone")
        record_file = tempfile.mkstemp('.wav')[1]
        
        thread.start_new_thread(festival.say, ("Listening for commands.",))
        time.sleep(1.5); #wait until festival stops speaking
        #festival.say("Listening for commands.")
        record_to_file(record_file)     
        
        print("done - result written to %s" % record_file)
        print 'now converting...'
        subprocess.call(['sox', record_file, record_file+'.flac', 'rate', '16k'])
        print 'done, sending to google voice recognition...'
        
        theFile = EnhancedFile(record_file+'.flac', 'r')
        theRequest = urllib2.Request("https://www.google.com/speech-api/v1/recognize?xjerr=1&client=chromium&lang=en-EN", theFile, {'Content-Type': 'audio/x-flac; rate=16000'})
        response = urllib2.urlopen(theRequest)
        theFile.close()
        
        response_obj = json.loads(response.read())
        print response_obj['hypotheses'][0]['utterance']
        
        waeo = wap.WolframAlphaEngine('VVQEQU-WA6TQUJGUK', 'http://api.wolframalpha.com/v1/query.jsp')
        query = waeo.CreateQuery(response_obj['hypotheses'][0]['utterance'])
        result = waeo.PerformQuery(query)
        waeqr = wap.WolframAlphaQueryResult(result)
        
        
        processed = False
        for pod in waeqr.Pods():
            waep = wap.Pod(pod)
            title = waep.Title()[0]
            print '-',title
            if not "input" in title.lower():
                subpods = waep.Subpods()
                for subpod in subpods:
                    waesp = wap.Subpod(subpod)
                    #print '   =>',waesp.Title(), '=>', waesp.Plaintext(),type(waesp.Plaintext()[0]) == str
                    if (type(waesp.Plaintext()[0]) == str or type(waesp.Plaintext()[0]) == unicode) and waesp.Plaintext()[0].strip() != '' and not processed:
                        string_to_speech = waesp.Plaintext()[0].strip().encode('iso-8859-2')
                        string_to_speech = string_to_speech.replace('=','')
                        string_to_speech = string_to_speech.replace('<','')
                        string_to_speech = string_to_speech.replace('>','')
                        string_to_speech = string_to_speech.replace('|',', ')
                        string_to_speech = string_to_speech.replace('[','')
                        string_to_speech = string_to_speech.replace(']','')
                        string_to_speech = string_to_speech.replace("\\n2",'')
                        string_to_speech = string_to_speech.replace('\n',". . ")
                        
                        print string_to_speech
                        festival.say(string_to_speech)
                        processed = True
        #festival.say(response_obj['hypotheses'][0]['utterance'].encode('iso-8859-2'))
        
        print 'cleanup'
        os.unlink(record_file)
        os.unlink(record_file+'.flac')
