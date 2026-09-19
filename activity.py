"""Read activity signals only. Never record keys, text, audio or media titles."""
import asyncio
import ctypes
from ctypes import wintypes
import os
import threading
import time


class ActivityState:
    def __init__(self):
        self.last_key=float('-inf')
        self.sampled=float('-inf')
        self.stable={'microphone':False,'music':False}
        self.pending={}

    def key(self,now=None):
        self.last_key=time.monotonic() if now is None else now

    def sample(self,microphone,music,now=None):
        now=time.monotonic() if now is None else now
        self.sampled=now
        for name,value in [('microphone',microphone),('music',music)]:
            if value is None:
                value=False
            if value==self.stable[name]:
                self.pending.pop(name,None)
                continue
            previous=self.pending.get(name)
            if previous is None or previous[0]!=value:
                self.pending[name]=(value,now)
            elif now-previous[1] >= (.4 if value else 1.5):
                self.stable[name]=value
                self.pending.pop(name,None)

    def state(self,now=None,usage_open=False,codex_working=False):
        now=time.monotonic() if now is None else now
        if usage_open:return 'usage'
        if codex_working:return 'working'
        if now-self.sampled<5:
            if self.stable['microphone']:return 'microphone'
            if self.stable['music']:return 'music'
        return 'typing' if now-self.last_key<1.5 else 'idle'


class KeyboardActivity:
    def __init__(self,state):
        self.state=state
        self.thread_id=None
        self.ready=threading.Event()
        self.error=None
        self.thread=threading.Thread(target=self.run,daemon=True,name='typing-activity')

    def run(self):
        if os.name!='nt':return
        user=ctypes.WinDLL('user32',use_last_error=True)
        kernel=ctypes.WinDLL('kernel32',use_last_error=True)
        callback_type=ctypes.WINFUNCTYPE(ctypes.c_ssize_t,ctypes.c_int,ctypes.c_size_t,ctypes.c_ssize_t)
        user.SetWindowsHookExW.argtypes=[ctypes.c_int,callback_type,ctypes.c_void_p,ctypes.c_uint32]
        user.SetWindowsHookExW.restype=ctypes.c_void_p
        user.CallNextHookEx.argtypes=[ctypes.c_void_p,ctypes.c_int,ctypes.c_size_t,ctypes.c_ssize_t]
        user.CallNextHookEx.restype=ctypes.c_ssize_t
        user.UnhookWindowsHookEx.argtypes=[ctypes.c_void_p]
        kernel.GetModuleHandleW.argtypes=[wintypes.LPCWSTR]
        kernel.GetModuleHandleW.restype=ctypes.c_void_p

        @callback_type
        def on_key(code,kind,data):
            if code>=0 and kind in (0x100,0x104):
                # Read virtual code only to ignore bare modifiers. Never decode,
                # retain, emit or log which key was pressed.
                vk=ctypes.cast(data,ctypes.POINTER(wintypes.DWORD))[0]
                if vk not in (16,17,18,20,91,92,160,161,162,163,164,165):
                    self.state.key()
            return user.CallNextHookEx(None,code,kind,data)

        self.thread_id=kernel.GetCurrentThreadId()
        hook=user.SetWindowsHookExW(13,on_key,kernel.GetModuleHandleW(None),0)
        if not hook:self.error='Keyboard activity unavailable'
        self.ready.set()
        if not hook:return
        message=wintypes.MSG()
        try:
            while user.GetMessageW(ctypes.byref(message),None,0,0)>0:
                user.TranslateMessage(ctypes.byref(message))
                user.DispatchMessageW(ctypes.byref(message))
        finally:
            user.UnhookWindowsHookEx(hook)

    def close(self):
        if self.thread_id:
            ctypes.windll.user32.PostThreadMessageW(self.thread_id,0x12,0,0)
        if self.thread.is_alive():self.thread.join(timeout=1)


def microphone_active():
    from pycaw.pycaw import AudioUtilities
    from pycaw.constants import EDataFlow,DEVICE_STATE
    # Re-enumerate capture endpoints/sessions to cover newly opened sessions
    # and hot-plugged microphones. This never opens a recording stream.
    failed=False
    for device in AudioUtilities.GetAllDevices(EDataFlow.eCapture.value,DEVICE_STATE.ACTIVE.value):
        try:
            sessions=device.AudioSessionManager.GetSessionEnumerator()
            if any(sessions.GetSession(i).GetState()==1 for i in range(sessions.GetCount())):
                return True
        except Exception:
            failed=True
    return None if failed else False


class ActivityMonitor:
    def __init__(self):
        self.state=ActivityState()
        self.stop=threading.Event()
        self.keyboard=KeyboardActivity(self.state)
        self.status={'microphone':None,'music':None}
        self.thread=threading.Thread(target=self.run,daemon=True,name='media-activity')

    def start(self):
        self.keyboard.thread.start()
        self.thread.start()

    async def watch(self):
        import comtypes
        from winrt.windows.media.control import GlobalSystemMediaTransportControlsSessionManager as Manager
        from winrt.windows.media.control import GlobalSystemMediaTransportControlsSessionPlaybackStatus as Status
        comtypes.CoInitialize()
        manager=None
        next_retry=0
        try:
            while not self.stop.is_set():
                mic=music=None
                try:
                    mic=microphone_active()
                except Exception:
                    pass
                try:
                    if manager is None and time.monotonic()>=next_retry:
                        manager=await asyncio.wait_for(Manager.request_async(),timeout=3)
                    if manager is not None:
                        music=any(s.get_playback_info().playback_status==Status.PLAYING for s in manager.get_sessions())
                except Exception:
                    manager=None;next_retry=time.monotonic()+10
                self.status={'microphone':mic,'music':music}
                self.state.sample(mic,music)
                await asyncio.sleep(.5)
        finally:
            comtypes.CoUninitialize()

    def run(self):
        try:
            asyncio.run(self.watch())
        except Exception:
            self.status={'microphone':None,'music':None}

    def close(self):
        self.stop.set()
        self.keyboard.close()
        if self.thread.is_alive():self.thread.join(timeout=1)
