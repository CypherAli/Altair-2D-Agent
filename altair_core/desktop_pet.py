"""Small, transparent WebView2 companion, using the already installed shell."""
import ctypes,json,sys,threading,math,queue,time
from pathlib import Path

def work_area():
    from ctypes import wintypes
    rect=wintypes.RECT()
    if not ctypes.windll.user32.SystemParametersInfoW(48,0,ctypes.byref(rect),0):raise OSError('Cannot read Windows work area')
    # pywebview coordinates are logical pixels in the WinForms backend.
    return rect.left,rect.top,rect.right,rect.bottom

class PetBridge:
    def __init__(self,url):self._url=url;self._window=None;self._dashboard=None;self._chat=None;self._drag=None;self._lock=threading.Lock()
    def drag_start(self,x,y,dpr=1):
        with self._lock:self._drag=(float(x),float(y),self._window.x,self._window.y,max(1,min(4,float(dpr))))
    def drag_to(self,x,y):
        with self._lock:
            if not self._drag:return
            sx,sy,wx,wy,dpr=self._drag
            left,top,right,bottom=work_area()
            nx=int(max(left,min(right-100,wx+(float(x)-sx)/dpr)))
            ny=int(max(top,min(bottom-80,wy+(float(y)-sy)/dpr)))
            self._window.move(nx,ny)
    def _prepare(self):
        self._panels=[];self._bitmap=None;self._mask=[];self._viewport=(340.,640.);self._reported=False;self._received=False
        from System import Action
        from System.Drawing import Color
        def initialize_host():
            self._window.native.BackColor=Color.FromArgb(1,2,3)
            self._window.native.TransparencyKey=Color.FromArgb(1,2,3)
        self._window.native.Invoke(Action(initialize_host))
        self._enable_native_input()
        self._render_background()
        timer=threading.Timer(.8,self._diagnostic);timer.daemon=True;timer.start()
    def _enable_native_input(self):
        # Layered WinForms may hit the host instead of WebView2's composed child.
        # Forward only those host mouse events; child DOM events keep their path.
        if hasattr(self,'_input_queue'):return
        from System import Action
        from System.Drawing import Point
        from System.Windows.Forms import Control
        self._input_queue=queue.Queue(64);self._last_move=0
        def enqueue(kind,event):
            now=time.monotonic()
            if kind=='move' and now-self._last_move<.03:return
            if kind=='move':self._last_move=now
            form=self._window.native;screen=form.PointToScreen(Point(event.X,event.Y))
            if kind=='down':print('Altair host pointer:',event.X,event.Y,flush=True)
            message={'kind':kind,'x':event.X/form.ClientSize.Width*self._viewport[0],
                'y':event.Y/form.ClientSize.Height*self._viewport[1],
                'sx':screen.X,'sy':screen.Y,'button':2 if str(event.Button)=='Right' else 0,
                'alt': 'Alt' in str(Control.ModifierKeys)}
            try:self._input_queue.put_nowait(message)
            except queue.Full:pass
        def down(sender,event):
            if str(event.Button)=='Left':self._window.native.Capture=True
            enqueue('down',event)
        def up(sender,event):
            enqueue('up',event);self._window.native.Capture=False
        def move(sender,event):enqueue('move',event)
        def double(sender,event):enqueue('double',event)
        def install():
            form=self._window.native
            form.MouseDown+=down;form.MouseUp+=up;form.MouseMove+=move;form.MouseDoubleClick+=double
        self._window.native.Invoke(Action(install))
        def dispatch():
            while True:
                message=self._input_queue.get()
                try:self._window.evaluate_js('window.altairNativePointer && window.altairNativePointer('+json.dumps(message)+')')
                except Exception:pass
        threading.Thread(target=dispatch,daemon=True).start()
    def _diagnostic(self):
        try:
            value=self._window.evaluate_js("({bridge:typeof window.pywebview,methods:Object.keys(window.pywebview?.api||{}),renderer:document.querySelector('#altair-character')?.dataset.renderer,frames:document.querySelector('#altair-character')?.dataset.rigFrames,hitRows:document.querySelector('#altair-character')?.dataset.hitRows,hitError:document.querySelector('#altair-character')?.dataset.hitError,client:[innerWidth,innerHeight]})")
            print('Altair render diagnostic:',json.dumps(value),flush=True)
        except Exception as exc:print('Altair diagnostic:',type(exc).__name__,flush=True)
    def _render_background(self):
        from System import Action
        from System.Drawing import Color,Bitmap,Graphics,Brushes
        from System.Drawing.Drawing2D import GraphicsPath
        def apply():
            form=self._window.native;sx=form.ClientSize.Width/self._viewport[0];sy=form.ClientSize.Height/self._viewport[1]
            bitmap=Bitmap(form.ClientSize.Width,form.ClientSize.Height)
            graphics=Graphics.FromImage(bitmap);graphics.Clear(Color.FromArgb(1,2,3))
            # Eroded opaque artwork interiors supply native mouse hits, without
            # a visible box or bleed outside the moving character silhouette.
            for x,y,w,h in self._mask:
                graphics.FillRectangle(Brushes.Black,int(x*sx),int(y*sy),max(1,int(w*sx)),max(1,int(h*sy)))
            for x,y,w,h in self._panels:
                x=int((x+3)*sx);y=int((y+3)*sy);w=int((w-6)*sx);h=int((h-6)*sy);r=max(2,int(12*min(sx,sy)))
                if w<2*r or h<2*r:continue
                path=GraphicsPath()
                for ax,ay,start in [(x,y,180),(x+w-2*r,y,270),(x+w-2*r,y+h-2*r,0),(x,y+h-2*r,90)]:path.AddArc(ax,ay,2*r,2*r,start,90)
                path.CloseFigure();graphics.FillPath(Brushes.Black,path);path.Dispose()
            graphics.Dispose();old=self._bitmap;self._bitmap=bitmap;form.BackgroundImage=bitmap
            if old is not None:old.Dispose()
        if self._window.native is not None:self._window.native.Invoke(Action(apply))
    def _set_viewport(self,viewport):
        if not isinstance(viewport,list) or len(viewport)!=2:return
        try:w,h=map(float,viewport)
        except (ValueError,TypeError):return
        if 100<=w<=2500 and 100<=h<=2500:self._viewport=(w,h)
    def hitmask(self,rows,viewport=None):
        if not getattr(self,'_received',False):
            self._received=True;print('Altair mask received:',len(rows) if isinstance(rows,list) else type(rows).__name__,viewport,flush=True)
        if not hasattr(self,'_mask') or not isinstance(rows,list) or len(rows)>400:return
        self._set_viewport(viewport);vw,vh=self._viewport
        validated=[]
        for rect in rows:
            if not isinstance(rect,list) or len(rect)!=4:continue
            try:x,y,w,h=map(float,rect)
            except (ValueError,TypeError):continue
            if not all(math.isfinite(v) for v in (x,y,w,h)):continue
            if -10<=x<vw and -10<=y<vh and 0<w<=vw and 0<h<=vh:
                nx=max(0,x);ny=max(0,y);validated.append((nx,ny,max(0,min(vw,x+w)-nx),max(0,min(vh,y+h)-ny)))
        if validated!=self._mask:
            self._mask=validated;self._render_background()
        if not self._reported and validated:
            self._reported=True;print('Altair hit surface:',len(validated),'viewport',self._viewport,'bitmap',self._window.native.ClientSize.Width,self._window.native.ClientSize.Height,flush=True)
    def interactive(self,panels=None,viewport=None):
        if not hasattr(self,'_mask'):return
        if not isinstance(panels,list) or len(panels)>5:return
        self._set_viewport(viewport);vw,vh=self._viewport
        validated=[]
        for rect in panels:
            if not isinstance(rect,list) or len(rect)!=4:continue
            try:x,y,w,h=map(float,rect)
            except (TypeError,ValueError):continue
            if 0<=x<vw and 0<=y<vh and 0<w<=vw and 0<h<=vh:validated.append((x,y,w,h))
        self._panels=validated;self._render_background()
    def trace(self,value):
        if isinstance(value,dict) and len(json.dumps(value))<1000:print('Altair pointer trace:',json.dumps(value),flush=True)
    def chat(self):
        import webview,faulthandler
        print('Altair chat requested',threading.current_thread().name,bool(webview.guilib),len(webview.windows),flush=True)
        watchdog=threading.Timer(5,lambda:faulthandler.dump_traceback(file=sys.stderr));watchdog.daemon=True;watchdog.start()
        if self._chat is None:
            self._chat=webview.create_window('Altair · Hội thoại',self._url+'/chat.html',width=470,height=600,
                background_color='#101923',on_top=True,x=300,y=100,js_api=ChatBridge(self))
            watchdog.cancel();print('Altair chat created',self._chat.uid,'native',self._chat.native is not None,'title',self._chat.title,flush=True)
            self._chat.show()
            print('Altair chat visible',self._chat.native.Visible,self._chat.native.Text,self._chat.native.Bounds,flush=True)
            def closed():
                self._chat=None
                try:self._window.evaluate_js("window.altairCharacter && window.altairCharacter.lockDemo(false)")
                except Exception:pass
            self._chat.events.closed+=closed
        else:watchdog.cancel();self._chat.show()
    def studio(self):
        import webview
        if self._dashboard is None:
            self._dashboard=webview.create_window('Altair · Bảng điều khiển',self._url,width=1080,height=780)
            def closed():self._dashboard=None
            self._dashboard.events.closed+=closed
        else:self._dashboard.show()
    def close(self):
        from . import runtime,tts,asr
        asr.cancel();tts.cancel();runtime.cancel()
        if self._chat:self._chat.destroy()
        if self._dashboard:self._dashboard.destroy()
        self._window.destroy()

class ChatBridge:
    def __init__(self,parent):self._parent=parent
    def relay(self,kind,data=None):
        if kind not in ('state','respond','demo','stop','busy') or not isinstance(data,dict):return
        raw=json.dumps(data,ensure_ascii=False)
        if len(raw.encode('utf-8'))>24000:return
        self._parent._window.evaluate_js('window.altairFromChat && window.altairFromChat('+json.dumps(kind)+','+raw+')')

def create(url):
    import webview
    left,top,right,bottom=work_area()
    bridge=PetBridge(url)
    window=webview.create_window('Altair · Đồng hành',url+'/pet.html',width=340,height=640,
        x=max(left,right-356),y=max(top,bottom-656),frameless=True,transparent=True,
        background_color='#000000',on_top=True,easy_drag=False,resizable=False,shadow=False,
        min_size=(340,640),js_api=bridge)
    bridge._window=window
    window.events.loaded+=bridge._prepare
    return window
