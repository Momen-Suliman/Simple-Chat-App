'''
CS 3700 - Networking & Distributed Computing - Fall 2025
Instructor: Thyago Mota
Student(s): Momen Suliman
Description: Project 1 - Multiuser Chat: Server
'''

import os
import sys
import importlib
import signal
import atexit
from datetime import datetime

# AI Usage: Import the system's socket module while allowing a local src/socket.py to exist.
project_dir = os.path.dirname(os.path.abspath(__file__))
removed = False
if project_dir in sys.path:
    sys.path.remove(project_dir)
    removed = True
std_socket = importlib.import_module('socket')
if removed:
    sys.path.insert(0, project_dir)

socket_mod = std_socket

# socket names
AF_INET = socket_mod.AF_INET
SOCK_DGRAM = socket_mod.SOCK_DGRAM
SOL_SOCKET = socket_mod.SOL_SOCKET
SO_REUSEADDR = socket_mod.SO_REUSEADDR

# "constants"
MCAST_ADDR = '224.1.1.1'
MCAST_PORT = 2241
SERVER_ADDR = '0.0.0.0'
SERVER_PORT = 4321
BUFFER = 1024


# suggested dictionary to keep track of logged in users
users = {}


def timestamp(msg: str):
    print(f"{datetime.now()}: {msg}")


def multicast(sSend, message: str):
    try:
        sSend.sendto(message.encode(), (MCAST_ADDR, MCAST_PORT))
    except Exception as e:
        timestamp(f"Error sending multicast: {e}")


# global sockets so cleanup/signal handlers can close them
sReceive = None
sSend = None

#AI Usage: Define cleanup function to close sockets and perform cleanup.
def cleanup():
    """Close sockets and perform any cleanup. Safe to call multiple times."""
    global sReceive, sSend
    try:
        if sReceive is not None:
            try:
                sReceive.close()
            except Exception:
                pass
            sReceive = None
    finally:
        try:
            if sSend is not None:
                try:
                    sSend.close()
                except Exception:
                    pass
                sSend = None
        finally:
            return

#AI Usage: Define signal handler to invoke cleanup on termination signals.
def _handle_signal(signum, frame):
    timestamp(f"Received signal {signum}, shutting down...")
    cleanup()
    sys.exit(0)


# register signal handlers and atexit cleanup
signal.signal(signal.SIGINT, _handle_signal)
signal.signal(signal.SIGTERM, _handle_signal)
atexit.register(cleanup)


def server():
    global sReceive, sSend

    # create sockets
    try:
        sSend = socket_mod.socket(AF_INET, SOCK_DGRAM)
    except Exception as e:
        print('Error: unable to create sending socket.', e)
        sys.exit(1)

    try:
        sReceive = socket_mod.socket(AF_INET, SOCK_DGRAM)
        sReceive.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
        sReceive.bind((SERVER_ADDR, SERVER_PORT))
    except Exception as e:
        print(f'Error: unable to bind to port {SERVER_PORT}. Is another instance of the server running? ({e})')
        cleanup()
        sys.exit(1)

    timestamp("Multiuser server is ready on " + f"{SERVER_ADDR}:{SERVER_PORT}")
    try:
        while True:
            data, addr = sReceive.recvfrom(BUFFER)
            try:
                msg = data.decode('utf-8', errors='replace')
            except Exception as e:
                timestamp(f"Error decoding message from {addr}: {e}")
                continue
            if not msg:
                continue

            split = msg.split(',', 1)
            overhead = split[0].strip().lower()
            content = split[1] if len(split) > 1 else ''

            if overhead == 'login':
                name = content.strip()
                users[name] = addr
                timestamp(f"User '{name}' logged in from {addr}.")
                multicast(sSend, f"welcome,{name}")
            elif overhead == 'msg':
                checkName = None
                for name, address in users.items():
                    if address == addr:
                        checkName = name
                        break
                if not checkName:
                    checkName = "unknown"
                text = content
                timestamp(f"Msg '{text}' received from '{checkName}' at {addr}.")
                multicast(sSend, f"msg,{checkName}: {text}")
            elif overhead == 'list':
                timestamp(f"List request received from {addr}.")
                userList = ', '.join(users.keys())
                multicast(sSend, f"list,{userList}")
            elif overhead == 'exit':
                name = None
                for n, address in list(users.items()):
                    if address == addr:
                        name = n
                        break
                if name:
                    del users[name]
                    timestamp(f"User '{name}' logged out from {addr}.")
                    multicast(sSend, f"bye,{name}")
                else:
                    timestamp(f"Exit request from unknown user at {addr}.")
            else:
                timestamp(f"Unknown overhead '{overhead}' from {addr}.")
    finally:
        timestamp("Server shutting down.")
        cleanup()


if __name__ == '__main__':
    server()