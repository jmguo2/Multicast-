#!/usr/bin/env python
import socket
import Queue 
import time, threading
import random 
import sys
import signal
from datetime import datetime
import select
import struct
from collections import defaultdict

class listener_thread (threading.Thread):
    def __init__(self):
        super(listener_thread, self).__init__()
    def run(self):
        global inputs
        global pid_to_socket
        global address_to_pid
        while(1):
            readable, writable, exceptional = select.select(inputs, [], [], 0) 
            for s in readable:
                if s is server:
                    connection, client_address = s.accept()
                    client_pid = int(connection.recv(recv_limit))
                    inputs.append(connection)
                    pid_to_socket[client_pid] = connection
                    address_to_pid[client_address] = client_pid
                else:      # case where s is a client socket 
                    data = s.recv(recv_limit)
                    if(data):
                        for fmt_string in [casual_fmt_string, unicast_fmt_string]:
                            try:
                                decoded_msg = decode_message(fmt_string, data)
                                break
                            except struct.error:
                                print('Message not decoded properly')
                                continue
                        if fmt_string == unicast_fmt_string:
                            decoded_msg = decoded_msg[0].strip()
                            unicast_receive(s, decoded_msg)
                        else:
                            casual_order_receive(s, decoded_msg)


def server_init():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    # server.setblocking(0)
    server.bind(server_binding_addr)
    print('Server binding to ' + str(server_binding_addr[1]))
    server.listen(pid_count-1)
    return server 

def print_receive_time(client_pid, message):
    time = str(datetime.now())
    print("Received \"" + message + "\" from process " + str(client_pid) + ", system time is " + time)


# client code ----------------------------------------------------------------------------------------------------------------------------

class client_thread (threading.Thread):
    def __init__(self):
        super(client_thread, self).__init__()
    def run(self):
        client_init()
        while(1):
            raw_argument = raw_input("Enter command line argument for client: ")
            cli_arg = raw_argument.strip().split(' ')
            if(cli_arg[0] == 'send'): 
                unicast_send(cli_arg)
            elif(cli_arg[0] == 'msend' and cli_arg[2] == 'casual'):
                casual_order_send(client, cli_arg)
            else:
                print("Invalid CLI argument. Please follow this format: send destination message")

# establish a connection between every pair of processes 

def client_init():
    clients = []
    global inputs
    for i in range(pid_count):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        clients.append(sock)
    for client, pid, address in zip(clients, pid_to_address.keys(), pid_to_address.values()):        # establish a connection between every pair of processes 
            result = client.connect_ex(address)
            if(not result):
                print("Client connected to process " + str(pid))
                global pid_to_socket
                pid_to_socket[int(pid)] = client
                inputs.append(client)
                client.send(str(server_pid)) # send process id to every other process  
            else:
                print("Could not connect to process " + str(pid))


# unicast functions are below ----------------------------------------------------------------------------------------------------------------------

def tcp_send(send_socket, message):
    send_socket.sendall(message)

def print_time(message, destination):
    time = str(datetime.now())
    print("Sent \"" + message + "\" to process " + str(destination) + ", system time is " + time)

def delayed_send(send_socket, message):
    random_delay = random.uniform((float(min_delay)/1000), (float(max_delay)/1000))
    sender_thread = threading.Timer(random_delay, tcp_send, [send_socket, message])   
    sender_thread.start()

def unicast_send(cli_arg):
    destination = int(cli_arg[1])
    message = cli_arg[2]
    send_socket = pid_to_socket[destination]
    print_time(message, destination)
    encoded_msg = encode_unicast_msg(message)
    if(destination != server_pid):
        delayed_send(send_socket, encoded_msg)
    else:
        tcp_send(send_socket, encoded_msg)

def unicast_receive(server, data):
    pid_from = address_to_pid[server.getpeername()]
    print_receive_time(pid_from, data)

def encode_unicast_msg(message):
    extended_message = message 
    for i in range(len(extended_message), msg_limit):
        extended_message += ' '
    buf = struct.pack(unicast_fmt_string, extended_message)
    return buf 

def decode_message(format_string, encoded_string):
    return struct.unpack(format_string, encoded_string)

def get_unicast_fmt_string():
    string_lim = str(msg_limit)
    return (string_lim + 's')

# multicast functions -------------------------------------------------------------------------------------------------------------------------------

def casual_order_send(client, cli_arg):
    # for every server in pid_to_address aside from own pid, call tcp_send
    message = cli_arg[1]
    encoded_msg = encode_vector(message)
    pid_to_vector[server_pid][server_pid] = pid_to_vector[server_pid][server_pid]+1 # increment process i's count of messages from i 
    for pid, socket in pid_to_socket.iteritems():
        socket = pid_to_socket[pid]
        print_time(message, pid)
        if(pid != server_pid):
            delayed_send(socket, encoded_msg)
        else:
            tcp_send(socket, encoded_msg)

def casual_order_delivery(client_pid, message):
    global pid_to_vector
    print_receive_time(client_pid, message)
    pid_to_vector[server_pid][client_pid] = pid_to_vector[server_pid][client_pid] + 1

def casual_order_receive(server, decoded_vec):
    global message_queue
    client_pid = address_to_pid[server.getpeername()]
    message = decoded_vec[0]
    message = message.strip()
    if(client_pid == server_pid):
        print_receive_time(client_pid, message)
    else:
        will_deliver = check_casuality(decoded_vec, client_pid)
        if(will_deliver):
            casual_order_delivery(client_pid, message)
            recursive_delivery()
        else:
            message_queue[client_pid].append(decoded_vec)

def recursive_delivery():
    global message_queue
    for client_pid, vector_list in message_queue.iteritems():
        for index, vector in enumerate(vector_list):
            if(check_casuality(vector, client_pid)):
                del vector_list[index]
                casual_order_delivery(client_pid, vector[0])
                recursive_delivery()


def get_casual_fmt_string():
    vec_len = str(pid_count)
    string_lim = str(msg_limit)
    fmt_string =  string_lim + 's ' + vec_len + 'i'
    return fmt_string 

# message format will be (message, vec[1], vec[2], vec[3], vec[4])

def encode_vector(message):
    own_vector = pid_to_vector[server_pid]
    extended_message = message
    for i in range(len(extended_message), msg_limit):
        extended_message += ' '
    own_vector[0] = extended_message
    buf = struct.pack(casual_fmt_string, *own_vector)
    return buf 

def check_casuality(client_vec, client_pid):
    valid = 1
    if(client_vec[client_pid] == pid_to_vector[server_pid][client_pid]+1): # check to make sure its the right message from the client
        for i in range(pid_count):  # make sure we've seen everything that the client has seen 
            k = i+1 
            if(k != client_pid and pid_to_vector[server_pid][k] < client_vec[k]):
                valid = 0
    return valid 

# entry function --------------------------------------------------------------------------------------------------------------------------
# set up a server for each process in the config file, and bind it to its assigned ip and port 

message_queue = defaultdict(list)
pid_to_vector = {}
pid_to_address = {}
address_to_pid = {}
pid_to_socket = {}
socket_to_pid = {}
pid_count = 0
msg_limit = 128
recv_limit = 1024
server_pid = int(sys.argv[1])


with open("config.txt", "r") as file:
    delay = file.readline()
    for row in file:
        if(row not in ['\n', '\r\n']):
            stripped = row.strip()
            pid, ip, port = stripped.split(' ')
            pid = int(pid)
            client_address = (str(ip), int(port))
            pid_to_address[pid] = client_address
            address_to_pid[client_address] = pid
            pid_count = pid_count + 1 

for i in range(pid_count):
    pid = i + 1
    pid_to_vector[pid] = [0] * (pid_count+1) 
    # if(pid != server_pid):
    #     message_queue[pid] = 
 
casual_fmt_string = get_casual_fmt_string()
unicast_fmt_string = get_unicast_fmt_string()
server_binding_addr = pid_to_address[server_pid]
client_port_offset = 0 
min_delay, max_delay = delay.strip().split(' ')
server = server_init()
inputs = [server]
outputs = []
listener = listener_thread()
listener.start()
client = client_thread()
client.start()
