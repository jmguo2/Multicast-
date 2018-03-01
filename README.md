# Multicast-

## How to use
Launch an instance with `python server.py {1, 2, 3...}`
Make sure to launch instances in order of PID, starting with the smallest.

To send an unicast message, type `send destination {1, 2, 3...}`
To multicast a message, type `msend message {casual, total}`



## Implementation details
### Network delays
We created a shell function (delayed_send()) over a standard tcp_send() function. We read in the min/max delay at runtime and generate an uniform random value *delay* within [min, max]. We then launch a thread on tcp_send() after *delay* seconds. 

### Common Details
Total ordering and casual are implemented with the same listener/server code. Message queues and time vectors are reset when you switch in between methods. We use the *struct* module to package our messages, and required metadata. The client is able to see which type (TO, casual) of message it received based on the message structure. 

### Causal multicast
Messages are sent to all connected clients. When the client receives the message, it checks for causality. If causality is not found, the message goes into a queue and waits for additional messages. If the message is delivered, it recursively checks to see if other messages are ready to be delivered.

### Total order multicast
At runtime, the sequencer is determined by the lowest PID that is connected. Messages are sent to this sequencer with a Redistribute flag. The sequencer, resends the message (with Redistribute flag off) to every other connected client, including itself. When the clients receive them, the message gets added to the queue. Client then goes through the queue. Every time the client finds a message to be delivered, it goes back into the queue to see if anything else is now ready.
