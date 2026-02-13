'''
CS 3700 - Networking & Distributed Computing - Fall 2025
Instructor: Thyago Mota
Student(s): Momen Suliman
Description: Project 1 - Multiuser Chat: Client
'''

from socket import *
from struct import pack
from datetime import datetime
import tkinter as tk
from tkinter import simpledialog, messagebox, scrolledtext
from threading import Thread, Semaphore
import sys

# "constants"
MCAST_ADDR  = '224.1.1.1'
MCAST_PORT  = 2241
SERVER_PORT = 4321
BUFFER      = 1024
GEOMETRY    = '570x400'

# the semaphore for GUI updates
s = Semaphore(1)

class Window(tk.Tk):
    def __init__(self, server_addr):
        super().__init__()
        self.title('Chat Client')
        self.geometry(GEOMETRY)
        self.resizable(0, 0)

        # TODO #3 create the unicast UDP socket to send messages to the server
        self.sToServer = socket(AF_INET, SOCK_DGRAM)

        # TODO #4 save the server address in an instance variable
        self.server_addr = (server_addr, SERVER_PORT)

        # Prompt username. Hide the main window while the modal dialog is shown
        # so the dialog appears correctly on macOS and the root doesn't interfere.
        self.withdraw()
        self.username = simpledialog.askstring('Username', 'Enter your username:', parent=self)
        if not self.username:
            messagebox.showerror("Login error", "Username cannot be empty.")
            self.destroy()
            sys.exit(1)

        # send login message in required protocol format: "login,<user>"
        try:
            self.sToServer.sendto(f'login,{self.username}'.encode('utf-8'), self.server_addr)
        except Exception as e:
            messagebox.showerror("Connection error", f"Could not contact server: {e}")
            self.destroy()
            sys.exit(1)

        # TODO #5 build the GUI
        self.text_box = scrolledtext.ScrolledText(self, state='disabled', width=70, height=20, wrap='word')
        self.text_box.grid(row=0, column=0, columnspan=2, padx=10, pady=10)
        self.input_field = tk.Entry(self, width=50)
        self.input_field.grid(row=1, column=0, padx=10, pady=(0,8))
        self.input_field.bind('<Return>', self.enter)
        self.send_button = tk.Button(self, text='Send', command=lambda: self.enter(None))
        self.send_button.grid(row=1, column=1, padx=10, pady=(0,8))

        self.protocol("WM_DELETE_WINDOW", self.on_close)
        # will be set by FromServerThread
        self.mCast = None
        self.listening = None
        # Make sure the window is visible and ready for input
        self.deiconify()
        # call Tk's update (use super() to avoid calling Window.update(msg))
        try:
            super().update()
        except Exception:
            # fallback to update_idletasks if super().update() is unavailable
            try:
                self.update_idletasks()
            except Exception:
                pass
        try:
            self.lift()
            self.focus_force()
        except Exception:
            pass
        # put keyboard focus in the input field so typing is visible immediately
        try:
            self.input_field.focus_set()
        except Exception:
            pass

    # TODO #6 read the input text field, update the text box, and send the message to the server using the unicast UDP socket
    def enter(self, event):
        # read from the input widget, not the text box
        info = self.input_field.get().strip()
        if not info:
            return
        
        if info.lower() == "list,":
            self.sToServer.sendto("list,".encode('utf-8'), self.server_addr)
            self.display_outgoing("Requesting user list...")
            self.input_field.delete(0, tk.END)
            return
        elif info.lower() == "exit,":
            self.sToServer.sendto("exit,".encode('utf-8'), self.server_addr)
            self.on_close()
            return

        content = f"msg,{info}"
        try:
            self.sToServer.sendto(content.encode('utf-8'), self.server_addr)
        except Exception as e:
            messagebox.showerror("Send error", f"Could not send message: {e}")
        self.display_outgoing(info)
        self.input_field.delete(0, tk.END)

    def display_outgoing(self, msg):
        s.acquire()
        try:
            self.text_box.config(state='normal')
            self.text_box.insert(tk.END, "-> " + msg + '\n')
            self.text_box.see(tk.END)
            self.text_box.config(state='disabled')
        finally:
            s.release()

    # TODO #7 updated the text box avoiding race conditions
    def update(self, msg):
        s.acquire()
        try:
            self.text_box.config(state='normal')
            self.text_box.insert(tk.END, "<- " + msg + '\n')
            self.text_box.see(tk.END)
            self.text_box.config(state='disabled')
        finally:
            s.release()

    def on_close(self):
        try:
            self.sToServer.sendto("exit,".encode('utf-8'), self.server_addr)
        except Exception:
            pass

        try:
            if self.mCast:
                group = inet_aton(MCAST_ADDR)
                mreq = pack('4sL', group, INADDR_ANY)
                self.mCast.setsockopt(IPPROTO_IP, IP_DROP_MEMBERSHIP, mreq)
                self.mCast.close()
        except Exception:
            pass

        try:
            self.sToServer.close()
        except Exception:
            pass

        if self.listening and hasattr(self.listening, 'stop'):
            self.listening.stop()

        self.destroy()

class FromServerThread(Thread):
    def __init__(self, window):
        Thread.__init__(self, daemon=True)

        # TODO #8 create the mcast UDP socket to receive messages from the server; bind the socket to MCAST_PORT
        self.rFromServer = socket(AF_INET, SOCK_DGRAM, IPPROTO_UDP)
        self.rFromServer.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
        try:
            self.rFromServer.bind(('', MCAST_PORT))
        except Exception:
            self.rFromServer.bind((MCAST_ADDR, MCAST_PORT))

        # formats MCAST_ADDR to a network format
        group = inet_aton(MCAST_ADDR)
        # formats the multicast group into a multicast request structure (mreq)
        mreq = pack('4sL', group, INADDR_ANY)

        # TODO #9 configure the socket to read from the multicast group
        self.rFromServer.setsockopt(IPPROTO_IP, IP_ADD_MEMBERSHIP, mreq)

        # TODO #10 save the window reference in an instance variable
        self.window = window
        self.window.mCast = self.rFromServer
        self.window.listening = self
        self._running = True

    def stop(self):
        self._running = False
        try:
            self.rFromServer.close()
        except Exception:
            pass

    # TODO #11 read from the socket and update the window's text box
    def run(self):
        while self._running:
            try:
                data, addr = self.rFromServer.recvfrom(BUFFER)
                if not data:
                    continue
                text = data.decode('utf-8', errors='replace')
                # schedule GUI update on the main thread
                self.window.after(0, self.window.update, text)
            except OSError:
                break
            except Exception:
                continue

if __name__ == '__main__':

    if len(sys.argv) <= 1:
        print(f'Use: {sys.argv[0]} server_address')
        sys.exit(1)
    server_addr = sys.argv[1]

    window = Window(server_addr)
    from_server_thread = FromServerThread(window)
    from_server_thread.start()
    window.mainloop()
