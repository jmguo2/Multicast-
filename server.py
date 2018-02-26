#!/usr/bin/env python
import socket
import Queue 
import time, threading
import random 
import sys
import signal
from datetime import datetime
import select

class listener_thread (threading.Thread):
    def __init__(self, queue):
        super(listener_thread, self).__init__()
        self.queue = queue
    def run(self):
        global inputs
        global pid_to_socket
        global address_to_pid
        while(1):
            readable, writable, exceptional = select.select(inputs, [], [], 0) 
            for s in readable:
                if s is server:
                    connection, client_address = s.accept()
                    client_pid = int(connection.recv(1024))
                    inputs.append(connection)
                    pid_to_socket[client_pid] = connection
                    address_to_pid[client_address] = client_pid
                else:      # case where s is a client socket 
                    data = s.recv(1024)
                    if data:
                        pid_from = address_to_pid[s.getpeername()]
                        time = str(datetime.now())
                        print("Received \"" + data + "\" from process " + str(pid_from) + ", system time is " + time)
                    else:
                        print("client connection is over")
                        s.close()

                

class client_thread (threading.Thread):

    def __init__(self, queue):
        super(client_thread, self).__init__()
        self.queue = queue
    def run(self):
        client_init()
        while(1):
            raw_argument = raw_input("Enter command line argument for client: ")
            cli_arg = raw_argument.strip().split(' ')
            if(cli_arg[0] == 'send'): 
                unicast_send(cli_arg)
            elif(cli_arg[0] == 'msend' and cli_arg[2] == 'casual'):
                casual_order_send(client, cli_arg, self.queue)
            else:
                print("Invalid CLI argument. Please follow this format: send destination message")

# establish a connection between every pair of processes 

def client_init():
    clients = []
    global inputs
    for i in range(pid_count-1):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        clients.append(sock)
    for client, pid, address in zip(clients, pid_to_address.keys(), pid_to_address.values()):        # establish a connection between every pair of processes 
            result = client.connect_ex(address)
            if(not result):
                print("Client connected to process " + str(pid))
                global pid_to_socket
                pid_to_socket[pid] = client
                inputs.append(client)
                client.send(server_pid) # send process id to every other process  
            else:
                print("Could not connect to process " + str(pid))

# unicast functions are below ----------------------------------------------------------------

def tcp_send(destination, send_socket, message):
    send_socket.send(message)
    time = str(datetime.now())
    print("Sent \"" + message + "\" to process " + str(destination) + ", system time is " + time)

# todo: check to make sure you aren't sending a message to yourself 

def unicast_send(cli_arg):
    destination = int(cli_arg[1])
    message = cli_arg[2]
    send_socket = pid_to_socket[destination]
    random_delay = random.uniform((float(min_delay)/1000), (float(max_delay)/1000))
    sender_thread = threading.Timer(random_delay, tcp_send, [destination, send_socket, message])   
    sender_thread.start()
    sender_thread.join()

# multicast functions 

def casual_order_send(client, cli_arg, pid_to_address, queue):
    # for every server in pid_to_address aside from own pid, call tcp_send
    message = cli_arg[1]
    queue[server_binding_address].put(message)
    pid_to_vector[server_pid][server_pid] = pid_to_vector[server_pid][server_pid]+1 # increment process i's count of messages from i 
    for pid, address in pid_to_address.iteritems():
        if(pid != server_pid):
            random_delay = random.uniform((float(min_delay)/1000), (float(max_delay)/1000))
            client.connect(address)
            sender_thread = threading.Timer(random_delay, tcp_send, [address, client, message])   
            sender_thread.start()



def server_init():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    # server.setblocking(0)
    server.bind(server_binding_addr)
    print('Server binding to ' + str(server_binding_addr[1]))
    server.listen(pid_count-1)
    return server 


# set up a server for each process in the config file, and bind it to its assigned ip and port 
message_queue = {} 
pid_to_vector = {}
pid_to_address = {}
address_to_pid = {}
pid_to_socket = {}
socket_to_pid = {}
pid_count = 0
server_pid = sys.argv[1]

with open("config.txt", "r") as file:
    delay = file.readline()
    for row in file:
        if(row not in ['\n', '\r\n']):
            stripped = row.strip()
            pid, ip, port = stripped.split(' ')
            if(pid != server_pid): 
                pid = int(pid)
                client_address = (str(ip), int(port))
                pid_to_address[pid] = client_address
                address_to_pid[client_address] = pid
            else:
                server_binding_addr = (str(ip), int(port)) 
            pid_count = pid_count + 1 

for i in range(pid_count):
    pid_to_vector[i+1] = [0] * pid_count 

lock = threading.Lock()
client_port_offset = 0 
min_delay, max_delay = delay.strip().split(' ')
server = server_init()
inputs = [server]
outputs = []
listener = listener_thread(message_queue)
listener.start()
client = client_thread(message_queue)
client.start()
