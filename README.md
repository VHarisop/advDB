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

