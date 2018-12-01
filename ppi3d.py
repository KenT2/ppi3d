#!/usr/bin/python
from __future__ import absolute_import, division, print_function, unicode_literals

"""
ppi3d aims to test whether vaarious aspects of pi3d can benefit Pi Presents. The main features of interest are:
a. Transitions between slides - fade, wipe and other geometric effects, Pi3d's blenders,  ken burns effect ( pan and zoom still image)
b. Text over videos
c. Fancy text effects like in stringmulti
d. Allow access to all pi3d passive 3d images and effects, Pi Presents woudl provide an environment for users to write python for this. 
e. Keep Tkinter as the current Pi Presents is implemented using this

Pi Presents plays shows, there are many types of shows. A show displays tracks, the different types of show
 mainly setting the control method for switching between tracks.
 There can be one or more shows running concurrently, usually occupying different parts of the screen.
 
ppi3d runs two identical shows in different parts of the screen. The show is a 'mediashow' which automatically
 cycles around a number of tracks
 
One of the aims of ppi3d was to show I could layer the presentation of each track, back to front.
a. a show background which stays the same for each track (implemented by Tkinter at desktop layer)
b. a video (implemented by omxplayer layer above desktop)
c. an alternative show background implemented by Pi3d so it appears in front of videos (pi3d layer above omxplayer)
d. A track image which will have transition effects between tracks (pi3d layer above omxplayer)
e. Text implemented as in stringmulti, maybe fixedstring as well (pi3d layer above omxplayer)

The other aims were to:
a. investigate transitions so there is fade, wipe and your blend_
b. To show Tkinter integration, mainly widget.after, keyboard and mouse

RUNNING
ppi3d should be self contained, all the images, videos, etc. should be there
use develop branch of pi3d or else the videos will appear in the wrong order. demo.py reflects this
sudo pip install pi3d
sudo pip3 install pi3d
sudo apt-get install python-imaging-tk

I have modified blend_include_fs.inc to set edge_alpha to 0.0

Run using python ppi3d.py python3 ppi3d.py. Use escape to exit. However when using python ppi3d.py after 
reboot escape leaves images on the screen. This can be corrected permanently by running the python3 versions

The shaders used can be changed around line 91 ????
You can run with one or two shows by altering line self.enable_show2 = True (line 490 ish)
Don't alter self.Tkinter=True, its for one day experimenting with your oother keyboard/mouse solutions

omxplayer sometimes does not quit properly and will leave unused tasks running, clesr omxplayyer .bin out of there are funny effects
The initial track is not initiated properly, ignore this.
"""

import sys
if sys.version_info[0] < 3:
    PY3=False
else:
    PY3=True

import math, random, time
import os
import demo
import pi3d
import subprocess
if PY3:
    from tkinter import *
else:
    from Tkinter import *
from PIL import Image
from PIL import ImageTk




class Show(object):

    def __init__(self,display,win,canvas,background_image,x,y,width,height,camera,fps):

        # configuration

        self.media_path='./media/'
        self.fonts_path = './fonts/'
        self.shaders_path = './shaders/'
        self.dwell_time = 10
        self.fade_time = 8


        # z values for the various layers
        self.z_show_background_uv = 9000      #100
        self.z_show_background_2d =  0.3    #orig 0.2  2d_flat   0.3
        self.z_track_image_uv = 50      # orig 0.1   blend_xxxx  = 2d  0.2
        self.z_track_image_blend = 0.2     # orig 0.1   blend_xxxx  = 2d  0.2
        self.z_track_text = 1          # orig 1   uv_flat  FixedString  1
        self.z_track_pointtext = 0.05     # orig 0.1 uv_pointsprite which is a bit odd z wise 0.05

        self.videos=['1sec.mp4','5sec.mp4','1sec.mp4','5s ec.mp4','1sec.mp4','5sec.mp4']
        self.images=['mountain.jpg','river.jpg','space.jpg','mountain.jpg','river.jpg','space.jpg']
        self.texts=['text0','text1','text2','text3','text4','text5']
        #self.shaders=['fade','wipe-right','fade',"wipe-left","fade"]
        self.shaders=['wipe-right','wipe-right',"blend_holes",'fade']
        #self.shaders = ["blend_star","blend_holes","blend_false","blend_burn","blend_bump","blend_false"]
          

        # unpack arguments
        self.display=display
        self.win=win
        self.background_image=background_image
        self.canvas=canvas
        self.show_canvas_x=x
        self.show_canvas_y=y
        self.show_canvas_width=width
        self.show_canvas_height=height
        self.camera=camera
        self.fps=fps


        # variables
        self.previous_track_image=None  #next track
        self.track_image=None  # current track
        self.current_slide=None
        self.previous_slide=None
        self.fade=0  # progress of fade 0 -> 1
        self.fade_step = 0  # amount to increment fade each frame        

    # Process the Show
    # ------------------
    def start_show(self):

        print ('\n\rStart Show\r')
        
        self.media=self.next_media()
        self.fade_step = 1.0 / (self.fps * self.fade_time)

        self.load_show_background()
        self.load_tk_show_background()
        self.create_click_areas()
        # load the media for the initial track
        i,video,image,text=next(self.media)
        self.load_first_track_image(image)
        self.next_track()

    def next_track(self):
        self.next_track_signal=True       
        self.win.after(self.dwell_time*1000,self.next_track)

    def terminate_show(self):
        if self.video_process.poll() == None:
            if PY3:
                b='q'.encode()
                self.video_process.communicate(b)
            else:
                self.video_process.communicate('q')
        
    def draw_show(self):
        self.do_next_track()
        self.draw_show_background()
        self.draw_track_image()
        self.draw_track_text()
        self.draw_track_pointtext()



    def do_next_track(self):
        if self.next_track_signal is True:
            self.next_track_signal=False
            i,video,image,text=next(self.media)
            self.load_track_image(image,self.shaders[i])
            self.load_track_video(video)
            self.load_track_text(text + ' ' + self.shaders[i])
            self.load_track_pointtext(text)

            
    def next_media(self):
        i=0
        while True:
            yield i,self.videos[i],self.images[i],self.texts[i]
            if i == len(self.shaders)-1:
                i=0
            else:
                i+=1

    # Show Background Image
    # ----------------------
    
    # tk implemented show background that appears behind a video 
    def load_tk_show_background(self):
        if not os.path.isfile(self.background_image):
            print ('not found ' + self.backgound_image)
            return None
        ppil_image=Image.open(self.background_image)
        ppil_image=ppil_image.resize((int(self.show_canvas_width), int(self.show_canvas_height)),eval('Image.NEAREST'))
        self.tk_img=ImageTk.PhotoImage(ppil_image)
        del ppil_image
        self.track_image_obj = self.canvas.create_image(self.show_canvas_x,
                                                                    self.show_canvas_y,
                                                                   image=self.tk_img, anchor=NW)
        self.canvas.itemconfig(self.track_image_obj,state='normal')
    
    
    # an alternative show background which is implemented by Pi3d so appears in front of the video
    def load_show_background(self):

        self.show_background = pi3d.Sprite(camera=self.camera,w = self.show_canvas_width-200,h=self.show_canvas_height-150,
                                   x=self.tktouv_x(self.show_canvas_x),y=self.tktouv_y(self.show_canvas_y),z=self.z_show_background_uv)
        if not os.path.isfile(self.background_image):
            print ('not found ' + self.background_image)
            return None
        tex = pi3d.Texture(self.background_image, blend=True, mipmap=True, m_repeat=True)

        self.show_background.set_draw_details( pi3d.Shader("uv_flat"),[tex])
        self.position_2d(self.show_background,self.show_canvas_x,self.show_canvas_y,self.z_show_background_uv)

        print ('load background',self.background_image,self.show_canvas_x,self.show_canvas_y,tex.ix,tex.iy,"\n\r")

    """  
    
    # this is implemented by Pi3d so appears in front of the video
    # 2d-flat version which I am trying not to use.
    def load_show_background(self):
        self.show_background = pi3d.Sprite(camera=self.camera,w = self.show_canvas_width,h=self.show_canvas_height,
                                     x=self.show_canvas_x,y=self.show_canvas_y,z=self.z_show_background_2d)
        if not os.path.isfile(self.background_image):
            print ('not found ' + self.backgound_image)
            return None
        tex = pi3d.Texture(self.background_image, blend=True, mipmap=True, m_repeat=True)

        self.show_background.set_draw_details( pi3d.Shader("2d_flat"),[tex])
        self.show_background.set_2d_size(x=self.show_canvas_x,y=self.show_canvas_y,w = self.show_canvas_width-200,h=self.show_canvas_height-150)
        print ('load background',self.background_image,self.show_canvas_x,self.show_canvas_y,tex.ix,tex.iy,"\n\r")
    """
        
    def draw_show_background(self):
        self.show_background.draw()




    # click areas
    # ===========
    # click areas are rectangles areas that can be clicked on to produce events, main use is touchscreens.
    # in pp they will be transparent and overlaid by pi3d images
    # show1 and show2 have click areas which just print to the terminal
    
    def create_click_areas(self):
        x1 = self.show_canvas_x
        y1 = self.show_canvas_y
        width = self.show_canvas_width
        height = self.show_canvas_height
        points= [str(x1),str(y1),str(x1+width),str(y1),str(x1+width),str(y1+height),str(x1),str(y1+height)]
        self.canvas.create_polygon(points,
                                       fill='',
                                       outline='red',
                                       tags="pp-click-area",
                                       state='normal')


                    
    # Track Image
    # -----------

    def load_first_track_image(self,image):
        self.track_image = pi3d.Sprite(w = self.show_canvas_width/2,h=self.show_canvas_height/2,z=self.z_track_image_uv)
        path = self.media_path + image
        self.current_slide = self.tex_load(path)
        self.track_image.set_alpha(0.0)

    def load_track_image(self,image,shader_name):
        self.shader_name=shader_name
        self.fade=0
        if shader_name == 'fade':
            """
            # 2d_flat version which seems not to allow .set_offset and which I am trying to avoid as 2d
            self.previous_track_image=self.track_image
            self.previous_track_image.positionZ(self.z_track_image_blend+0.05)
            self.track_image = pi3d.Sprite(w = self.show_canvas_width/2,h=self.show_canvas_height/2,z=self.z_track_image_blend)
            # self.current_image=self.next_image
            tmp_slide = self.tex_load(self.media_path + image) 
            if tmp_slide != None: # checking in case file deleted
                self.next_image = tmp_slide
                self.track_image.set_draw_details(pi3d.Shader('2d_flat'),[self.next_image.tex]) # reset two textures
                self.track_image.set_2d_size(x=self.show_canvas_x,y=self.show_canvas_y,w = self.show_canvas_width/2,h=self.show_canvas_height/2)
                self.track_image.set_alpha(0.0)
            """
            
            self.previous_track_image=self.track_image
            self.previous_slide=self.current_slide
            # move previous behind so blend works properly
            self.previous_track_image.positionZ(self.z_track_image_uv+0.05)
            self.track_image = pi3d.Sprite(w = self.show_canvas_width/2,h=self.show_canvas_height/2,z=self.z_track_image_uv)
            tmp_slide = self.tex_load(self.media_path + image) 
            if tmp_slide != None: # checking in case file deleted
                self.current_slide = tmp_slide
                self.track_image.set_draw_details(pi3d.Shader('uv_flat'),[self.current_slide.tex])
                self.position_2d(self.track_image,self.show_canvas_x,self.show_canvas_y,self.z_track_image_uv)
                self.track_image.set_alpha(0.0)

        elif shader_name in  ('wipe-right','wipe-left','wipe-up','wipe-down'):
            # wipe does not work using set_offset
            self.previous_track_image=self.track_image
            self.previous_slide=self.current_slide
            # move previous behind so blend works properly
            self.previous_track_image.positionZ(self.z_track_image_uv+0.05)
            self.track_image = pi3d.Sprite(w = self.show_canvas_width/2,h=self.show_canvas_height/2,
            z=self.z_track_image_uv)
            tmp_slide = self.tex_load(self.media_path + image) 
            if tmp_slide != None: # checking in case file deleted
                self.current_slide = tmp_slide
                self.track_image.set_draw_details(pi3d.Shader('uv_flat'),[self.current_slide.tex],umult=1.0,vmult=1.0)
                self.position_2d(self.track_image,self.show_canvas_x,self.show_canvas_y,self.z_track_image_uv)
                self.track_image.set_alpha(1.0)
                if shader_name=='wipe-left':
                    self.track_image.set_offset((-1.0,0))
                elif shader_name=='wipe-right':
                    self.track_image.set_offset((+1.0,0))

        else:
            # blend shaders
            shader=pi3d.Shader(self.shaders_path+shader_name)
            self.previous_track_image=self.track_image
            self.previous_slide=self.current_slide
            self.track_image = pi3d.Sprite(w = self.show_canvas_width/2,h=self.show_canvas_height/2,z=self.z_track_image_blend)
            tmp_slide = self.tex_load(self.media_path + image) 
            if tmp_slide != None: # checking in case file deleted
                self.current_slide = tmp_slide
                self.track_image.set_draw_details(self.previous_track_image.shader,[self.previous_slide.tex, self.current_slide.tex]) # reset two textures
                self.track_image.set_2d_size(x=self.show_canvas_x,y=self.show_canvas_y,w = self.show_canvas_width/2,h=self.show_canvas_height/2)
                self.track_image.unif[48:54] = self.track_image.unif[42:48] #need to pass shader dimensions for both textures
                self.track_image.set_shader(shader)
                self.track_image.set_alpha(1.0)

    def draw_track_image(self):
        if self.shader_name == 'fade':
            self.alpha_step()
            if self.previous_track_image != None:
                self.previous_track_image.draw()
            self.track_image.draw()
            
        elif self.shader_name in ('wipe-right','wipe-left','wipe-up','wipe-down'):
            self.wipe_step()
            if self.previous_track_image != None:
                self.previous_track_image.draw()
            self.track_image.draw()
        else:
            # blend shaders
            self.morph_step()
            self.track_image.draw()


    def tex_load(self,fname):
        slide = Slide()
        if not os.path.isfile(fname):
            print ('not found ' + fname)
            return None
        tex = pi3d.Texture(fname, blend=True, mipmap=True, m_repeat=True)
        wi=tex.ix
        hi=tex.iy
        xi=self.show_canvas_x
        yi=self.show_canvas_y
        
        slide.tex = tex
        slide.dimensions = (wi, hi, xi, yi)
        print ('load image',fname,xi,yi,wi,hi,"\r")
        return slide


    def morph_step(self):
        # print ('morph step ', self.fade,self.fade_step)
        if self.fade < 1.0:
            self.fade += self.fade_step # increment fade
            if self.fade > 1.0: # more efficient to test here than in pixel shader
              self.fade = 1.0
            self.track_image.unif[44] = self.fade # pass value to shader using unif list   

    def alpha_step(self):
        # print ('alpha step ', self.fade,self.fade_step)
        if self.fade < 1.0:
            self.fade += self.fade_step # increment fade
            if self.fade > 1.0: # more efficient to test here than in pixel shader
              self.fade = 1.0
            self.track_image.set_alpha(self.fade)
            #self.track_image.set_offset((-self.alpha, 0.0))
            self.previous_track_image.set_alpha(1.0-self.fade)

    def wipe_step(self):
        # print ('wipe step ', self.fade,self.fade_step)
        if self.fade < 1.0:
            self.fade += self.fade_step # increment fade
            if self.fade > 1.0: # more efficient to test here than in pixel shader
              self.fade = 1.0
            #self.track_image.set_alpha(self.fade)
            #self.previous_track_image.set_alpha(1.0-self.fade)
            if self.shader_name=='wipe-left':
                self.track_image.set_offset((self.fade-1.0, 0.0))
                self.previous_track_image.set_offset((-self.fade,0.0))
            elif self.shader_name=='wipe-right':
                self.track_image.set_offset((1.0-self.fade, 0.0))
                self.previous_track_image.set_offset((self.fade,0.0))


    # Track Video
    # -------------
    def load_track_video(self,video):
        # start omxplayer
        x2= self.show_canvas_x + self.show_canvas_width - 100
        y2= self.show_canvas_y + self.show_canvas_height - 100
        window = " --win '"+str(self.show_canvas_x)+" "+ str(self.show_canvas_y) + " " + str(x2) + " " + str(y2)+ "'"
        self.omxplayer_cmd='omxplayer ' + self.media_path + video + ' --layer 1 ' + window
        print (self.omxplayer_cmd)
        if PY3:
            self.video_process=subprocess.Popen(self.omxplayer_cmd,shell=True,stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            self.video_process=subprocess.Popen(self.omxplayer_cmd,shell=True,stdin=subprocess.PIPE,
                stdout=file('/dev/null','a'),stderr=file('/dev/null','a'))

    # Track Text (FixedString)
    # -----------

    def load_track_text(self,text):
        self.text_shader=pi3d.Shader('uv_flat')
        # 'normal' FixedString on a (fairly) solid background
        self.str1 = pi3d.FixedString(self.fonts_path+'NotoSans-Regular.ttf', text, font_size=32, 
                        background_color=(200,140,20,235),
                        camera=self.camera, shader=self.text_shader, f_type='SMOOTH')
        self.position_2d(self.str1.sprite,self.show_canvas_x,self.show_canvas_y,self.z_track_text ) #NB note Shape methods act on FixedString.sprite
        
        # shadow outline FixedString to show up against light or dark backgrounds
        # try setting shadow_radius to 0 to see what the issue is
        self.str1a = pi3d.FixedString(self.fonts_path+'NotoSans-Regular.ttf', text+'a', font_size=48, 
                        color=(70, 70, 180, 255), background_color=None, shadow_radius=1, 
                        camera=self.camera, shader=self.text_shader, f_type='SMOOTH')
        self.position_2d(self.str1a.sprite,self.show_canvas_x+100,self.show_canvas_y+100,self.z_track_text )



    def draw_track_text(self):
        self.str1.draw()
        self.str1a.draw()



    # Track Text (Pointtext)
    # ######################

    def load_track_pointtext(self,text):
        font_colour = (255, 255, 255, 255)
        font= 'NotoSans-Regular.ttf'
        # Create pointFont and the text manager to use it
        pointFont = pi3d.Font(self.fonts_path + font, font_colour, codepoints=list(range(32,128)))
        self.pointtext = pi3d.PointText(pointFont, self.camera, max_chars=200, point_size=64)
        #Basic static text
        # !!!!! number of chars must be longer than length of string
        newtxt = pi3d.TextBlock(self.tktouv_x(self.show_canvas_x),self.tktouv_y(self.show_canvas_y), self.z_track_pointtext, -45.0, 50, text_format="POINT Text "+text,
          size=0.99, spacing="F", space=0.05, colour=(0.0, 1.0, 0.0, 1.0))
        self.pointtext.add_text_block(newtxt)
        print ('load pointtext '+text)


    def draw_track_pointtext(self):
        self.pointtext.regen()   
        self.pointtext.draw()

    # coordinate conversions
    # =======================
    #converts from  Tk coordinates to pi3d coordinates - top left of display to top left of sprite instead of centre of display and sprite


    def tktouv_x(self,x):
        xpos= x - (self.display.width) / 2.0
        print ('xpos',xpos)
        return xpos

    def tktouv_y(self,y):
        ypos = -y + (self.display.height) / 2.0
        print ('ypos',ypos)
        return ypos

    def position_2d(self,shape,x,y,z):
        (lt, bm, ft, rt, tp, bk) = shape.get_bounds()
        xpos = x - (self.display.width - rt + lt) / 2.0         
        ypos = -y + (self.display.height  - tp + bm) / 2.0 
        shape.position(xpos, ypos, z)



# class to store details of a slide
class Slide(object):
  def __init__(self):
    self.tex = None
    self.dimensions = None


class App(object):


    def __init__ (self):

        # configuration
        self.enable_show2 = True
        self.fps = 20
        self.winw_fs,self.winh_fs= 1920,1080 #screen dimensions
        self.tkinter=True  # use tkinter for some images, keyboard and mouse
        self.show_pointer=True  # if not Tkinter

        #variables
        self.display=None  #pi3d display
        self.mymouse=None
        if self.tkinter:
            self.win=None  # Tkinter window

    def init_display(self):

        #Create a pi3d display the size of the screen, its transparent to show the Tkinter created show background
        self.display= pi3d.Display.create(tk=self.tkinter, window_title='Pi3d Pi Presents Experiment',
                            w=self.winw_fs, h=self.winh_fs, far=100000.0,
                             frames_per_second=self.fps, background=(0.0, 0.0,0.0,0.0),layer = 2)
        self.winh=self.winh_fs
        self.winw=self.winw_fs


        if self.tkinter:
            #create a Tkinter window that is fullscreen
            self.win = self.display.tkwin
            self.win.attributes('-fullscreen', True)
            # self.win.geometry("%dx%d%+d%+d"  % (self.winw,self.winh,0,0))
            # self.win.attributes('-zoomed','1')

            print('start - before resize ', self.win.winx, self.win.winy, self.win.width, self.win.height,
                              self.display.left,self.display.top,self.display.width,self.display.height,'\r')

            # Update display before we begin (needed after making the Tkinter window fullscreen)
            self.win.update()
            # !!!! the resize causes layer to be corrupted - not any more :-)
            self.display.resize(0, 0, self.winw, self.winh)

            print('start  - after resize ', self.win.winx, self.win.winy, self.win.width, self.win.height,
                              self.display.left,self.display.top,self.display.width,self.display.height,'\r')
            
            # define response to main window closing.
            self.win.protocol ("WM_DELETE_WINDOW", self.handle_user_abort)
 
        
        # orthographic camera
        self.camera = pi3d.Camera(is_3d=False)
        self.camera.was_moved = False #to save a tiny bit of work each loop
        
        #create and start the mouse and keyboard
        if self.tkinter:
            pass
            # uses Tkinter bindings and pointer for keyboard and mouse
        else:
            self.mymouse = pi3d.Mouse(restrict = False,width=self.winw,height=self.winh,use_x=False)
            self.mymouse.start()
            self.current_buttons=self.mymouse.BUTTON_UP
            self.mouse_event=False
            self.mouse_state = self.mymouse.BUTTON_UP
            
            self.mykeys = pi3d.Keyboard()

        # create the pointer, not used by Tk
        self.pointer_shader = pi3d.Shader("uv_flat")
        if self.show_pointer:
            tex = pi3d.Texture("pointer.png", blend=True, mipmap=False)
            self.pointer = pi3d.Sprite(camera=self.camera, w=tex.ix, h=tex.iy, z=0.5)
            self.pointer.set_draw_details(self.pointer_shader, [tex])
            self.p_dx, self.p_dy = tex.ix/2.0, -tex.iy/2.0

        # setup a whole screen Tkinter canvas onto which will be drawn the Tk show background images
        self.canvas = Canvas(self.win, bg='green')

        self.canvas.config(height=self.display.height,
                               width=self.display.width,
                               highlightthickness=0)

        self.canvas.place(x=0,y=0)
        # self.canvas.config(bg='black')
        self.canvas.focus_set()


    # start the player
    def start(self):
        self.init_display()

        self.show1=Show(self.display,self.win,self.canvas,'./media/river.jpg',100,100,800,400,self.camera,self.fps)
        self.show1.start_show()
        if self.enable_show2:
            self.show2=Show(self.display,self.win,self.canvas,'./media/river.jpg',901,501,800,400,self.camera,self.fps)
            self.show2.start_show()
        self.pi3d_loop()


    #pi3d loop
    def pi3d_loop (self):
                                 

        while self.display.loop_running():

            """
            #draw the shows one aafter the other
            # !!!! this fails in various ways with 2 shows
            self.show1.draw_show()
            if self.enable_show2:
                self.show2.draw_show()
            """
            
            # draw shows interleaved
            self.show1.do_next_track()
            if self.enable_show2:
                self.show2.do_next_track()
                
            self.show1.draw_show_background()
            if self.enable_show2:
                self.show2.draw_show_background()    
                
            # !!!!!!! only the first of these are displayed with blend_shaders
            if self.enable_show2:
                self.show2.draw_track_image()            
            self.show1.draw_track_image()

            self.show1.draw_track_text()
            if self.enable_show2:
                self.show2.draw_track_text()

            self.show1.draw_track_pointtext()
            if self.enable_show2:            
                self.show2.draw_track_pointtext()
             
            
            
            if self.tkinter:
                try:
                    self.win.update()
                except Exception as e:
                    print("win.update() failed", e)
                    self.handle_user_abort()

                
                if self.win.ev == "resized":
                    print('event  - before resize ', self.win.winx, self.win.winy, self.win.width, self.win.height,
                          self.display.left,self.display.top,self.display.width,self.display.height,)
                    self.win.update()
                    # self.display.resize(0, 0, self.winw, self.winh)
                    self.win.resized = False

                    
                if self.win.ev == "key":
                    if self.win.key == "n":
                        print('n key')
                        self.next_track_signal=True
                    if self.win.key == "p":
                        pi3d.screenshot("MarsStation.jpg")
                        
                    if self.win.key == "Escape":
                        print("Escape Pressed")
                        self.handle_user_abort()

                    

                if self.win.ev == "click":
                    self.mouse_x=self.win.x
                    self.mouse_y=self.win.y
                    print ('mouse click ',self.mouse_x,self.mouse_y,"\r")
                    self.click_pressed(self.win.x,self.win.y)
                else:
                    self.win.ev=""  #clear the event so it doesn't repeat
            
                if self.win.ev=="drag" or self.win.ev=="wheel":
                    pass
                else:
                    self.win.ev=""  #clear the event so it doesn't repeat
                    
            else:
            
                omx, omy = self.mymouse.position()
                mouse_x=omx-self.winw/2
                mouse_y=omy+self.winh/2
                self.draw_pointer(omx,omy)
            
                k = self.mykeys.read_code()
                if k !='':
                    if ord(k)==27: #ESC
                        self.handle_user_abort()
                    print ('key',k)
                    if k == 'n':
                        print ('next track')
                        self.show1.next_track_signal=True


                buttons=self.mymouse.button_status()
                if buttons != self.current_buttons:
                    self.mouse_event=True
                    self.mouse_state=buttons
                    self.current_buttons=buttons
                    
                if self.mouse_event == True and self.mouse_state != self.mymouse.BUTTON_UP:
                    self.mouse_event=False
                    omx, omy = self.mymouse.position()
                    self.mouse_x=omx+self.winw/2
                    self.mouse_y=-omy+self.winh/2
                    print ('mouse click ',omx,omy,self.mouse_x,self.mouse_y,"\r")
                    self.show1.next_track_signal=True


     # callback for click on screen
    def click_pressed(self,event_x,event_y):
        overlapping =  self.canvas.find_overlapping(event_x-5,event_y-5,event_x+5,event_y+5)
        for item in overlapping:
            # print (self.canvas.gettags(item))
            if ('pp-click-area' in self.canvas.gettags(item)):
                print ('mouse click in CLICK AREA ',event_x,event_y,"\r")
                # need break as find_overlapping returns two results for each click, one with 'current' one without.
                break


    def draw_pointer(self, x, y):
        if self.show_pointer:
            self.pointer.position(x + self.p_dx, y + self.p_dy, 0.5)
            self.pointer.draw()


    def handle_user_abort(self):
        print ('close window\r')
        self.show1.terminate_show()
        if self.enable_show2 == True:
            self.show2.terminate_show()
        try:
            self.display.destroy()
            if self.tkinter:
                self.win.destroy()
            self.mymouse.stop()
            exit()
        except:
            pass



if __name__ == '__main__':
    app=App()
    app.start()
