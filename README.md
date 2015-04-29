# advDB
-------

An implementation of a simple auction system written in Python TCP sockets.
Under construction.

## Message Interfaces
Various message types are implemented, in correspondence to the project specification which can be found [here](http://mycourses.ntua.gr/courses/ECE1060/projects/course-project-auction-advanced-data-base-systems-2015.pdf). 
The message object model (not yet finalized) can be found in `messages.py`.

### Message Object Model
Each message is implemented as a class as it inherits the base `Message` class.
Any message is initialized with a type to be passed as its headed (`msg_type`)
as well as a dictionary of key-value pairs that correspond to the relevant
information that the message is expected to carry.

### Message Serialization
To serialize messages, a generic serialization interface is
[implemented](https://github.com/VHarisop/advDB/blob/master/serializer.py#L3) in
`serializer.py`. It receives an instance of the `Message` class and encodes it
in JSON using the following format:

```
{	
	'header': msg_type,
	'key_1' : value_1,
	'key_2' : value_2,
	...,
	'key_N' : value_N
}
```

As an example, the typical structure of a Connect message is presented. A user
with user id of 5 and username 'johndoe' sends this message via the `bidder`
client. The message is instantiated and serialized as follows:

```
{
	'header': 'connect',
	'username': 'johndoe',
	'uid': 5
}
```

Note that a `|` (pipe) character is appended to the JSON string to be used as a
delimiter.

### Message encoding/decoding
After serializing a message in JSON, encoding follows using the UTF-8 format.
This is achieved using the `bytes()` built-in function in Python 3.
Message encoding is done prior to sending, using the `Message.send()` method. 

Decoding is implemented in 2 stages (in `serialized.py`):
- Unpacking: decoding the raw bytes received over the socket connection to
  a UTF-8 formatted string
- Decoding: splitting a string of possibly more than 1 unpacked messages based
  on the `|` delimiter and using the `json.loads()` method on each of the
  resulting messages to obtain a `dict`-based representation.

## Items
Each item is stored as a dictionary structure, in a list that each server
maintains. Servers are expected to be consistent in terms of item queues, i.e. 
at each point of communication with any client the servers will be maintaining
the same list of items. 

Each item is denoted by a unique `item_id` which is used for indexing the
server's item list. The item structure itself is simple enough not to be
implemented in a separate class. Its fields are:
- `about`: a small description for the item - text in ASCII
- `price`: the highest price bid by the item so far - integer
- `holder`: the username of the highest bidder - text in ASCII
- `timeouts`: number of consecutive times the item had no bids - integer

A typical item structure follows:

```
{
	'about': 'A small pirate hat',
	'price':  100,
	'holder': 'johndoe',
	'timeouts': 0
}
```

All items are created with the initial price of 0, with 0 timeouts and with the
`holder` field set to None. In
[`base.py`](https://github.com/VHarisop/advDB/blob/master/base.py), the
`item_new(about, price)` function is defined, which is handy for creating new
items with their timeout and holder fields initialized properly. 

The server assigns items ids sequentially, i.e. a new item in the queue
received the next highest integer higher than the maximum current item id. This
is to work-around the issue of randomized next item selection, which would
impose extra overhead on the servers' synchronization. The item selection would
then have to be implemented either by communication with an extra server or
process, or by synchronization messages similarly to a voting protocol.

## Synchronization
Each server has its own private copies of variables (items, prices, etc.). Each
server also keeps track of time separately with its own internal clock. Time
handling and ticking is done using the `signal.alarm()` interface, by which the
timer is set to cause an interrupt after `L` seconds. `L` is the specified
timeout for price reduction / item discarding.

### Time/Price sync
While it may seem that such a scheme cannot enforce synchronized data, a
gossip-like scheme is available: upon an item's price update, the auctioneer
sends a `SyncPriceMsg` to the other server to inform it about the new bid. A
successful update (i.e. correct bid price) also causes `alarm()` to reset for
`L` seconds. If both the sending and the receiving server call the `alarm()`
function within milliseconds, we can achieve such accuracy in our
synchronization scheme. This requirement is feasible for 2 servers operating on
the same physical machine. 

A typical `SyncPriceMsg` is shown in JSON format:

```
{
    'header'   : 'sync_price',
    'item_id'  : 151,
    'username' : 'johndoe',
    'price'    : 1200
}
```

A server receiving this message is informed that (at least based on the other
auctioneer's private data) item no. `151` is currently pitched at a price of
`1200` and is held by user `johndoe`. 
Each server keeps its own registration table. 

### Item discarding / awarding
Based on the above synchronization scheme, we can assume that our servers are
millisecond-consistent. As a result, when an item exceeds its timeout limit, a
`StopBidMsg` can be sent to the other server to enforce removal from the
auction queue. 

The server that sends the message first (possibly while being inside the
interrupt routine after an `alarm()` has been fired) deletes the item and adds
another `stop_bid`-type message to the pending queue. This is delivered to its
clients to inform about the end of bidding for this item. 

The server that receives the message has either done this action already
(removal + client sync) based on its own timer, in which case it can ignore the
message. Otherwise it must also delete the item and add a `stop_bid` message to
its own pending queue to enforce client synchronization.

### Auctioneer message parsing
The details of the message parsing can be found inside the `parse_messages()`
method (in `base.py` which implements most of the auction server). The
`sigalrm_handler()` is also essential to synchronization. Appropriate actions
are defined for each case and each message type expected to be received. 

## The Bidder Client
The bidder client uses a socket to connect to a specified auction server the
address of which defaults to `localhost:50000` but can be passed explicitly as
an argument to its constructor. 

In short:
```
from bidder import Bidder
bidr = Bidder('yourname', your_id, 'localhost:50000')
bidr.run()
bidr.complete()
```

### Initializing a client
Each bidder client is associated with a username as well as a user id. To
create a bidder with username 'johndoe' and id 1 which connects to localhost at
port 4040, just do:

```
from bidder import Bidder
bidr = Bidder('johndoe', 1, 'localhost:4040')
```

Most of the work is done in the `__init__` method of the Bidder, which sends a
`ConnectMsg` to the auction server. This message initiates a connection
handshake which results either in acknowledgement or rejection. Acknowledgement
is indicated by an `ACK` message, while rejection is usually the result of
erroneous registration attempts (e.g. using a username that is already used by
someone else). 


### The `run()` method
The `run()` method should be called immediately after a bidder is initialized,
as it implements the main loop of the client. It accepts a single parameter,
`instream`, which defaults to standard input.

If input would be handled by another source, e.g. a GUI class, `instream` could
be a socket of `socket.AF_UNIX` type. The GUI should run in a separate thread
and write its input to the ipc socket, which would then be polled by
`select()`. 

### Items & status variable
Each bidder client uses a status variable and a dictionary of items. 

The status variable contains info for the current item id, the minimum allowed bid and the ability of the bidder to make an offer. 
The item dictionary contains info about all items currently in the auction
queue, namely their info, descriptions, current price, etc. It is populated
after the `ack` message has been received from the server, via a separate
message of `items` type. 


