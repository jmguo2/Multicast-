#!/usr/bin/env python
import socket
import Queue 
import time, threading
import random 
import sys
import signal
from datetime import datetime

class listener_thread (threading.Thread):
    def __init__(self, queue, address_to_pid):
        super(listener_thread, self).__init__()
        self.queue = queue
        self.address_to_pid = address_to_pid
    def run(self):
        while(1):
            lock.acquire()
            # print "Waiting for incoming connections..."
            try: 
                connection, client_address = server.accept()
            except socket.error, strerror:
                lock.release()
                continue 
            self.queue[connection] = Queue.Queue()
            data = ''
            while(not data):
                try: 
                    data = connection.recv(1024)
                    self.queue[connection].put(data)
                except socket.error, strerror:
                    continue 
            remote_server_address = (client_address[0], client_address[1] - client_address[1]%10)
            pid_from = self.address_to_pid[remote_server_address]
            time = str(datetime.now())
            print("Received \"" + data + "\" from process " + pid_from + ", system time is " + time)
            connection.close()
            lock.release()


class client_thread (threading.Thread):

    def __init__(self, listener, pid_to_address):
        super(client_thread, self).__init__()
        self.listener = listener
        self.pid_to_address = pid_to_address

    def run(self):
        while(1):
            client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            cli_arg = raw_input("Enter command line argument for client: ")
            lock.acquire()
            command, destination, message = cli_arg.strip().split(' ')
            if(command == 'send'): 
                global client_port_offset
                client_port_offset = (client_port_offset + 1) % 10
                client_port = (server_binding_addr[1] + 1) if client_port_offset == 0 else (client_port_offset + server_binding_addr[1])
                client.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                client_binding_addr = (server_binding_addr[0], client_port)
                client.bind(client_binding_addr)
                # print('Client addr is: ' + client_binding_addr[0] + ':' + str(client_binding_addr[1]))
                dest = self.pid_to_address[destination]
                # print('Destination addr is: ' + dest[0] + ':' + str(dest[1]))
                random_delay = random.uniform((float(min_delay)/1000), (float(max_delay)/1000))
                client.connect(dest)
                sender_thread = threading.Timer(random_delay, unicast_send, [destination, client, message])   
                sender_thread.start()
                sender_thread.join()
            else:
                print("Invalid CLI argument. Please follow this format: send destination message")
            lock.release()


def unicast_send(destination, client, message):
    client.send(message)
    time = str(datetime.now())
    print("Sent \"" + message + "\" to process " + destination + ", system time is " + time)
    client.close()


def server_init():
    global server
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.setblocking(0)
    server.bind(server_binding_addr)
    server.listen(4)
    return server 


# set up a server for each process in the config file, and bind it to its assigned ip and port 
message_queue = {} 
pid_to_address = {}
address_to_pid = {}
with open("config.txt", "r") as file:
    delay = file.readline()
    for row in file:
        if(row not in ['\n', '\r\n']):
            stripped = row.strip()
            pid, ip, port = stripped.split(' ')
            server_address = (str(ip), int(port))
            pid_to_address[pid] = server_address
            address_to_pid[server_address] = pid


lock = threading.Lock()
server_pid = sys.argv[1]
server_binding_addr = pid_to_address[server_pid]
client_port_offset = 0 
min_delay, max_delay = delay.strip().split(' ')
server = server_init()
listener = listener_thread(message_queue, address_to_pid)
listener.start()
client = client_thread(server, pid_to_address)
client.start()








