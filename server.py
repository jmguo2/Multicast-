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

# server thread will constantly poll for new connections/writes from clients 
# if there is a new connection, accept it and associate that pid with a socket and address 
# otherwise try to read the message from the client and choose a receive handler based on the message's encoding

class listener_thread (threading.Thread):
    def __init__(self):
        super(listener_thread, self).__init__()
        self.running = True
    def stop(self):
        self.running = False
    def run(self):
        global inputs, pid_to_socket, address_to_pid
        while(self.running):
            readable, writable, exceptional = select.select(inputs, [], [], 0) 
            for s in readable:
                if s is server:
                    connection, client_address = s.accept()
                    client_pid = int(connection.recv(recv_limit))
                    pid_to_socket[client_pid] = connection
                    address_to_pid[client_address] = client_pid
                    inputs.append(connection)
                else:        
                    data = s.recv(recv_limit)
                    if(data):
                        for fmt_string in [casual_fmt_string, unicast_fmt_string]:
                            try:
                                decoded_msg = decode_message(fmt_string, data)      # decode will fail if the encoding doesn't match the format string
                                break
                            except struct.error:
                                continue
                        if fmt_string == unicast_fmt_string:
                            unicast_receive(s, decoded_msg)
                        else:
                            casual_order_receive(s, decoded_msg)

# initialize the server and listen the port specified by the config file

def server_init():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(server_binding_addr)
    server.listen(pid_count)
    return server 

# print the time that the message is received (note this isn't the same as delivery) 

def print_receive_time(client_pid, message):
    time = str(datetime.now())
    print("Received \"" + message + "\" from process " + str(client_pid) + ", system time is " + time)


# client code ----------------------------------------------------------------------------------------------------------------------------

# the client thread will read a command from stdin and perform a unicast or multicast send 
# unicast format: send destination message
# casual format: msend message casual

class client_thread (threading.Thread):
    def __init__(self, listener_thread):
        super(client_thread, self).__init__()
        self.listener_thread = listener_thread
        self.running = True
    def run(self):
        client_init()
        while(self.running):
            raw_argument = raw_input("Enter command line argument for client: \n")
            cli_arg = raw_argument.strip().split(' ')
            if(cli_arg[0] == 'send'): 
                unicast_send(cli_arg)
            elif(cli_arg[0] == 'msend' and cli_arg[2] == 'casual'):
                casual_order_send(cli_arg)
            elif(cli_arg[0] in ["q", "quit", "exit"]):
                self.running = False
                self.listener_thread.stop()
            else:
                print("Invalid CLI argument. Please follow this format: send destination message")
                print("[q]uit to disconnect")

# establish a connection between every pair of processes 
# send own pid after connection, so the server can map the client address/connection to the pid

def client_init():
    global inputs, pid_to_socket
    clients = []
    for i in range(pid_count):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        clients.append(sock)
    for client, pid, address in zip(clients, pid_to_address.keys(), pid_to_address.values()):        # establish a connection between every pair of processes 
            result = client.connect_ex(address)
            if(not result):
                print("Client connected to process " + str(pid))
                pid_to_socket[pid] = client
                inputs.append(client)
                client.send(str(server_pid)) # send process id to every other process  
            else:
                print("Could not connect to process " + str(pid))


# unicast functions ----------------------------------------------------------------------------------------------------------------------

# basic tcp send given a socket and a message  

def tcp_send(send_socket, message):
    send_socket.sendall(message)

# print the message, destination, and time upon sending the message   

def print_send_time(message, destination):
    time = str(datetime.now())
    print("Sent \"" + message + "\" to process " + str(destination) + ", system time is " + time)

# delay the unicast send by a random delay specified in the config file 

def delayed_send(send_socket, message):
    random_delay = random.uniform((float(min_delay)/1000), (float(max_delay)/1000))
    sender_thread = threading.Timer(random_delay, tcp_send, [send_socket, message])   
    sender_thread.start()

# parse the command line arguments for message, and destination
# encode the message and send it to the destination process
# also print the time that the message was sent 

def unicast_send(cli_arg):
    destination = int(cli_arg[1])
    message = cli_arg[2]
    send_socket = pid_to_socket[destination]
    print_send_time(message, destination)
    encoded_msg = encode_unicast_message(message)
    if(destination != server_pid):
        delayed_send(send_socket, encoded_msg)
    else:
        tcp_send(send_socket, encoded_msg)

# printing the time when the unicasted message was received 

def unicast_receive(server, decoded_msg):
    data = decoded_msg[0].strip()
    pid_from = address_to_pid[server.getpeername()]
    print_receive_time(pid_from, data)

# encode the unicasted message as binary data
# msg format is the extended_message

def encode_unicast_message(message):
    extended_message = extend_message(message)
    buf = struct.pack(unicast_fmt_string, extended_message)
    return buf 

# ensure that the messsage is length msg_limit for encoding purposes 

def extend_message(message):
    extended_message = message 
    for i in range(len(extended_message), msg_limit):
        extended_message += ' '
    return extended_message

# unpack decoded message and return a tuple 

def decode_message(format_string, encoded_string):
    return struct.unpack(format_string, encoded_string)

# return the unicast format string for struct.pack

def get_unicast_fmt_string():
    string_lim = str(msg_limit)
    return (string_lim + 's')

# multicast functions -------------------------------------------------------------------------------------------------------------------------------

# increment the server's vector element corresponding to its own pid
# encode the message and send it to all connected processes

def casual_order_send(cli_arg):
    global pid_to_socket, pid_to_vector, server_pid
    message = cli_arg[1]
    pid_to_vector[server_pid][server_pid] = pid_to_vector[server_pid][server_pid]+1 # increment process i's count of messages from i 
    print("Send casual: ")
    print_vector(pid_to_vector[server_pid])
    encoded_msg = encode_vector(message)
    for pid, socket in pid_to_socket.iteritems():
        socket = pid_to_socket[pid]
        print_send_time(message, pid)
        if(pid != server_pid):
            delayed_send(socket, encoded_msg)
        else:
            tcp_send(socket, encoded_msg)

# increment the value of the vector corresponding to the client_pid upon delivery

def casual_order_delivery(client_pid):
    global pid_to_vector
    pid_to_vector[server_pid][client_pid] = pid_to_vector[server_pid][client_pid] + 1
    print("Delivery casual: ")
    print_vector(pid_to_vector[server_pid])

# receive handler for casual ordering, which checks if the received message can be delivered 
# if client == server, print the received time 
# if client != server, deliver message if its ready and then recursively deliver queued messages
# if message can't be delivered, put the vector in the hold back queue  

def casual_order_receive(server, decoded_vec):
    global message_queue
    client_pid = address_to_pid[server.getpeername()]
    message = decoded_vec[0].strip()
    print_receive_time(client_pid, message)
    if(client_pid != server_pid):
        will_deliver = check_casuality(decoded_vec, client_pid)
        if(will_deliver):   
            casual_order_delivery(client_pid)
            recursive_delivery()
        else:
            message_queue[client_pid].append(decoded_vec)

# recursively check for casuality of messages in hold back queue  
# called after delivering a message, since casuality may be fulfilled 

def recursive_delivery():
    global message_queue
    for client_pid, vector_list in message_queue.iteritems():
        for index, vector in enumerate(vector_list):
            if(check_casuality(vector, client_pid)):
                del vector_list[index]
                casual_order_delivery(client_pid)
                recursive_delivery()

# return a format string for casual ordering 
# used by struct module to encode/decode data 

def get_casual_fmt_string():
    vec_len = str(pid_count)
    string_lim = str(msg_limit)
    fmt_string =  string_lim + 's ' + vec_len + 'i'
    return fmt_string 

# encode the server's vector as binary data 
# casual message format will be (extended_message, vec[1], vec[2], vec[3], vec[4])

def encode_vector(message):
    own_vector = pid_to_vector[server_pid]
    extended_message = extend_message(message)
    own_vector[0] = extended_message
    buf = struct.pack(casual_fmt_string, *own_vector)
    return buf 

# verify whether we can deliver the multicasted message
# compare the client broadcasted vector to the server's vector 

def check_casuality(client_vec, client_pid):
    if(client_vec[client_pid] != pid_to_vector[server_pid][client_pid]+1):      # check to make sure its the right message from the client
        return 0
    for pid in range(1, pid_count+1):        
        if(pid != client_pid and pid_to_vector[server_pid][pid] < client_vec[pid]):  # make sure we've seen everything that the client has seen 
            return 0
    return 1

# testing functions -----------------------------------------------------------------------------------------------------------------------

def print_vector(vector):
    vec_list = []
    for index, item in enumerate(vector):
        if(index != 0):
            vec_list.append(item)
    print(tuple(vec_list))
    


# entry point --------------------------------------------------------------------------------------------------------------------------

# read the config file and initialize various dictionaries that map between pid and info about the server
# initialize format strings and initialize any global variables that are commonly accessed 
# start the client and server threads 
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
inputs = []

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

for pid in range(1, pid_count+1):
    pid_to_vector[pid] = [0] * (pid_count+1)

casual_fmt_string = get_casual_fmt_string()
unicast_fmt_string = get_unicast_fmt_string()
server_binding_addr = pid_to_address[server_pid]
min_delay, max_delay = delay.strip().split(' ')
server = server_init()
inputs = [server]
listener = listener_thread()
client = client_thread(listener)
listener.start()
client.start()

listener.join()
client.join()
