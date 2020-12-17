from kivy.app import App
from kivy.uix.widget import Widget
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.floatlayout import FloatLayout

# add the following 2 lines to solve OpenGL 2.0 bug
from kivy import Config
Config.set('graphics', 'multisamples', '0')
import os
os.environ['KIVY_GL_BACKEND'] = 'angle_sdl2'

from pathlib import Path
import cv2

from HoverBehavior import HoverBehavior
from kivy.animation import Animation
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.image import Image
from kivy.properties import ObjectProperty,NumericProperty,\
     BooleanProperty,StringProperty,ListProperty,OptionProperty
from kivy.graphics import PushMatrix,PopMatrix,Rotate, Rectangle, Fbo, Color,Callback
from kivy.clock import Clock, mainthread
import math
import ffmpeg
from functools import partial
import subprocess as sp
import shlex
import json
from kivy.graphics.texture import Texture
import moviepy.editor as mpe
import threading

import numpy as np
import audiofile as af
import ffmpeg
from array import array
from kivy.uix.stencilview import StencilView
import fpstimer
import numpy
from pydub import AudioSegment
import pyaudio
import pygame
import time

startupinfo = sp.STARTUPINFO()
startupinfo.dwFlags |= sp.STARTF_USESHOWWINDOW
startupinfo.wShowWindow = sp.SW_HIDE

class Mediaimg(ButtonBehavior,BoxLayout):
    path = StringProperty('')
    source = StringProperty('')
    fname = StringProperty('')

class MediaPlayer(HoverBehavior,FloatLayout):
    source = StringProperty('')
    player_texture = ObjectProperty()
    
    fps = StringProperty()
    h = NumericProperty()
    w = NumericProperty()
    apect_ratio = StringProperty('')
    duration = StringProperty('')
    duration_ts = NumericProperty()
    nb_frames = NumericProperty()

    pipe = ObjectProperty()
    
    clock_frames = ObjectProperty()
    cur_frame = NumericProperty(0)
    rec = ObjectProperty()
    val_video = ObjectProperty()
    val_sound = ObjectProperty()
    sample_rate= ObjectProperty()
    channels= ObjectProperty()
    channel_width= ObjectProperty()
    
    def __init__(self, **kwargs):
        super(MediaPlayer, self).__init__(**kwargs)
        self.bind(source=self.on_source)
       
        

        
    def on_source(self, *args):
        self.cur_frame =0
        metadata = self.findVideoMetada(self.source)
        probe = ffmpeg.probe(self.source)
        video_stream = next((stream for stream in probe['streams'] if stream['codec_type'] == 'video'), None)
        width = int(video_stream['width'])
        height = int(video_stream['height'])
        
        self.fps = metadata[0]['avg_frame_rate']
        self.h = height #metadata['coded_height']
        self.w =width #metadata['coded_width']
        self.apect_ratio = metadata[0]['display_aspect_ratio']
        self.duration = metadata[0]['duration']
        self.duration_ts = metadata[0]['duration_ts']
        self.nb_frames = metadata[0]['nb_frames']
        self.sample_rate = metadata[1]['sample_rate']
        self.channels = metadata[1]['channels']

        self.bits_per_raw_sample = int(metadata[0]['bits_per_raw_sample'])
        
        with self.canvas:
            self.cb = Callback(self.update_video)

        self.reset_context = True
        self.player_texture = Texture.create(size=(self.w, self.h), colorfmt='rgb')
        
        
    def play(self):
        self.th =threading.Thread(target=self.playvideo)
        self.th.start()
        
        self.th =threading.Thread(target=self.playsound)
        self.th.start()
        
        
    def playvideo(self, *args):
        f = self.fps.split('/')
        avg_fps =int(f[0])/int(f[1])

        video_cmd = ['ffmpeg', '-i',self.source,
                     '-f','image2pipe',
                    '-pix_fmt','rgb24',
                    '-vcodec','rawvideo',
                    '-vf','vflip',
                    '-'
                    ]
        proc_video = sp.Popen(video_cmd,
                            stdin=sp.PIPE,
                            stdout=sp.PIPE,
                            startupinfo=startupinfo
                              , bufsize=self.w * self.h * 3)
        
        
        while True:            
            self.val_video = proc_video.stdout.read(self.w * self.h * 3)
            
            if proc_video.poll() is not None:
                break
            if self.val_video:
                timer = fpstimer.FPSTimer(avg_fps)
                self.cb.ask_update()
                timer.sleep()
            
    @mainthread
    def update_video(self, *args):
        if self.val_video != None:
            self.player_texture.blit_buffer(self.val_video, colorfmt='rgb', bufferfmt='ubyte')
            

    def playsound(self,*args):
        f = self.fps.split('/')
        avg_fps=int(f[0])/int(f[1])

        audio_cmd = ['ffmpeg', '-i',self.source,
                    '-f', 's16le',
                    '-acodec', 'pcm_s16le',
                    '-ac', '%s'%self.channels, # stereo (set to '1' for mono)
                    '-ar', '%s'%self.sample_rate,
                    '-'
                    ]
        
        proc_audio = sp.Popen(audio_cmd,
                            stdin=sp.PIPE,
                            stdout=sp.PIPE,
                            startupinfo=startupinfo,
                         bufsize=10**8)

        pygame.init()
        pygame.mixer.init(int(self.sample_rate), -self.bits_per_raw_sample, int(self.channels)) # 44100 Hz, 16bit, 2 channels

        while True:
            self.val_sound = proc_audio.stdout.read(88200*4)
            
            if proc_audio.poll() is not None:
                break
            if self.val_sound:
                audio_array = numpy.fromstring(self.val_sound, dtype="int32")

                audio_array = audio_array.reshape((len(audio_array)//2),2)
                
                timer = fpstimer.FPSTimer(0.8)
                self.playbytesound(audio_array)
                timer.sleep()


    @mainthread
    def playbytesound(self,audio_array):
        
        rang = audio_array[1][0]/int(self.sample_rate)
        #sub-bass
        if rang >=20 and rang <50:           
            no = 120 + (50/rang)*30
            for i in self.children[0].children:
                if isinstance(i, Spike):
                    if i.angle > 90 and i.angle <= 180:
                        Clock.schedule_once(partial(self.children[0].show_pikes_height, int(no), i,),1)
        #Bass
        elif rang > 50 and rang <=200:            
            no = 120 + (200/rang)*30
            for i in self.children[0].children:
                if isinstance(i, Spike):
                    if i.angle >= 0 and i.angle <= 90:
                        Clock.schedule_once(partial(self.children[0].show_pikes_height, int(no), i,),1)
        #mid - range
        elif rang > 200 and rang <=5000:            
            no = 120 + (5000/rang)*30
            for i in self.children[0].children:
                if isinstance(i, Spike):
                    if i.angle > 180 and i.angle <= 270:
                        Clock.schedule_once(partial(self.children[0].show_pikes_height, int(no), i,),1)
        #high freq
        elif rang > 10000 and rang <=20000:            
            no = 120 + (20000/rang)*30
            for i in self.children[0].children:
                if isinstance(i, Spike):
                    if i.angle > 270 and i.angle <= 360:
                        Clock.schedule_once(partial(self.children[0].show_pikes_height, int(no), i,),1)
             
        sound = pygame.sndarray.make_sound( audio_array )
        sound.play()
        
    # function to find the resolution of the input video file
    def findVideoMetada(self, pathToInputVideo):
        cmd = "bin/ffprobe.exe -v quiet -print_format json -show_streams"
        args = shlex.split(cmd)
        args.append(pathToInputVideo)
        # run the ffprobe process, decode stdout into utf-8 & convert to JSON
        ffprobeOutput = sp.check_output(args).decode('utf-8')
        ffprobeOutput = json.loads(ffprobeOutput)

		# prints all the metadata available:
##        import pprint
##        pp = pprint.PrettyPrinter(indent=2)
##        pp.pprint(ffprobeOutput)
        
        return ffprobeOutput['streams']
        
    def on_enter(self):
        anim = Animation(opacity=1,duration =.3)
        anim.start(self.children[0])
        if hasattr(self,'cf'):
            self.cf.cancel()
        
    def fadedeck(self, *args):
        anim = Animation(opacity=0,duration =.3)
        anim.start(self.children[0])
        
    def on_leave(self):
        self.cf = Clock.schedule_once(self.fadedeck, 2)

class Spike(Widget):
    angle=NumericProperty(0)
    no=NumericProperty(0)
    
class Deck(ButtonBehavior, FloatLayout):
    angle=NumericProperty(0)
    dc_angle=NumericProperty(0)
    spike_data=ListProperty()
    prev_no=NumericProperty(0)
    c_ter=NumericProperty(0)
    
    def __init__(self, **kwargs):
        super(Deck, self).__init__(**kwargs)
        self.angle = 1
        self.dc_angle=1
        self.add_spikes()

    def show_pikes_height(self, no, pike, *args):
        if self.prev_no != no and self.c_ter < 10: 
            a = Animation(no = 120+int(no), duration = .6)
            a.start(pike)
        self.prev_no = no
        self.c_ter +=1
        if self.prev_no != no:
            self.c_ter =0
        Clock.schedule_once(self.spike_height_change, 1)
        
    
    def add_spikes(self):
        for i in range(1, 360,2):
            spike = Spike()
            spike.no=0
            spike.pos_hint={'center_x':.5,'center_y':.5}
            spike.angle = i
            self.spike_data.append(i)
            self.add_widget(spike)

    def spike_height_change(self, *args):
        for child in self.children:
            if isinstance(child,Spike):
                a = Animation(no=80, duration=.3)
                a.start(child)
                
        
    def show_seeker(self, *args):
        pass

    def on_touch_down(self,touch):
        if self.ids.wd_seeker.collide_point(*touch.pos):
            self.get_angle(touch)

    def on_touch_move(self, touch):
        if self.ids.wd_seeker.collide_point(*touch.pos):
            self.get_angle(touch)

    def get_angle(self, touch):
        radius = self.width/2
        x_cord = touch.x - self.center[0]
        y_cord = touch.y - self.center[1]
        
        if x_cord <0:
            angle = math.degrees(math.atan(y_cord/x_cord))
            angle1 =  math.degrees(math.asin(y_cord/radius))
            if angle >=-90 and angle <=0:
                self.angle = angle
                self.dc_angle =-self.angle
        elif x_cord>0:
            angle = math.degrees(math.atan(y_cord/x_cord))
            angle1 =  math.degrees(math.asin(y_cord/radius))
            if x_cord >0 and y_cord >0:
                self.angle = angle1-360-180
                self.dc_angle = abs(self.angle)-360
        
        

    


class mainpage(BoxLayout):

    def __init__(self, **kwargs):
        super(mainpage, self).__init__(**kwargs)
        self.load_files()
        
    def load_files(self):
        i=0
        dwnl_path =str(Path.home() / "Downloads")
        for r, d, f in os.walk(dwnl_path):
            for file in f:
                if '.mp4' in file:
                    # Opens the Video file
                    cap= cv2.VideoCapture(os.path.join(r, file))
                    
                    if(cap.isOpened()):
                        total_frames = cap.get(7)
                        cap.set(1, 10)
                        ret, frame = cap.read()
                        if ret == False:
                            break
                        cv2.imwrite('media'+str(i)+'.jpg',frame)
                        
                    cap.release()
                    cv2.destroyAllWindows()

                    img = Mediaimg(size=(80,80),
                                         pos_hint={"center_y":.5})
                    img.source="assets\\track.png"
                    img.fname = file
                    img.path =os.path.join(r, file)
                    self.ids.boxmedia.add_widget(img)
                    img.bind(on_press=partial(self.play_video,img))
                    i+=1

    def play_video(self,img, *args):
        self.ids.vd.source = img.path
        self.ids.vd.play()
        
class MainApp(App):
    
    def build(self):
        return mainpage()
    
if __name__=="__main__":
    MainApp().run()
