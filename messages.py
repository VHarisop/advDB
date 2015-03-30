#!/usr/bin/python

import serializer as serial
import json

class Message(object):

    ''' Message is the base class that implements the 
        control message type.
    '''

    def __init__(self, msg_type, msg_details):
        self.msg_type = msg_type
        self.msg = msg_details
        self.msg_data = serial.encode_msg(msg_type, msg_details)

    def __str__(self):
        return self.msg_type

    def __repr__(self):
        return 'msg: {0}'.format(self.msg_data)[:-1]

    def send(self):

        ''' Serializes JSON encoded data using UTF-8 encoding
            in order for them to be sent via a TCP/IP connection.
        '''
        return bytes(self.msg_data, 'UTF-8')

    def details(self):

        ''' Returns a structured (i.e. dict) representation of 
            the message data
        '''
        return json.loads(self.msg_data)


class ConnectMsg(Message):
    
    ''' ConnectMsg is the message that initializes a connection
        between bidder and auctioneer right after a socket 
        connection is established. Contains user data in JSON format.
    '''

    def __init__(self, **user_data):
        super().__init__(msg_type='connect', msg_details=user_data)

class NewItemMsg(Message):

    ''' NewItemMsg is almost identical to StartBidMsg, as it contains
        the item's initial price along with a text description (in ASCII).
        All data are encoded in JSON. 

        Bidders that are interested in the item should send an
        <i_am_interested> control message (InterestMsg) within 
        L time units. 
        If no responses of type <i_am_interested> are received within
        these L time units, the item is discarded and bidding resumes
        with the next item (or finishes).
    '''

    def __init__(self, **bid_data):
        super().__init__(msg_type='new_item', msg_details=bid_data)

class InterestedMsg(Message):

    ''' Msg of interest about an item. 
        It contains the item's initial bid from the user that sent it,
        as well as user data.
    '''

    def __init__(self, **bid_data):
        super().__init__(msg_type='interested', msg_details=bid_data)

class StartBidMsg(Message):

    ''' StartBidMsg is the message that contains the initial price
        of the item and is sent to each of the bidders. 
        It contains data encoded in JSON format.
    '''

    def __init__(self, **bid_data):
        super().__init__(msg_type='start_bid', msg_details=bid_data)


class StopBidMsg(Message):

    ''' StopBidMsg is sent if L time units have passed since the 
        last successful (high) bid for an item to all the participants
        of the auction process.
        Alongside acting as a means of terminating an auction for a 
        specific item, it contains the username of the bidder that made
        the highest bid, to whom the item is eventually awarded.
        Contains user and item data in JSON format.
    '''

    def __init__(self, **bid_data):
        super().__init__(msg_type='stop_bid', msg_details=bid_data)

class NewHighBidMsg(Message):

    ''' NewHighBidMsg is sent each time a new bid is made for 
        an item whose auction is in process. This message is sent
        to all bidders as well as all other auctioning servers.
        Contains data in JSON format.
    '''

    def __init__(self, **bid_data):
        super().__init__(msg_type='new_high_bid', msg_details=bid_data)


class ErrorMsg(Message):

    ''' A standard error msg. Error types are defined at errors.py.
        For example, an error about registration has the form of:

            {
                header: 'error'
                error: 'REJECT_REGISTER',
                username: 'johndoe'
            }
    '''


    def __init__(self, **error_data):
        super().__init__(msg_type='error', msg_details=error_data)


class BidMsg(Message):
    
    ''' BidMsg is the message that is sent from the bidders
        to one of the auctioneers. Bid data (item_id etc.) 
        are formatted in JSON and serialized so to be passed
        as the msg_details field in the Message base class.
    '''

    def __init__(self, **bid_data):
        super().__init__(msg_type='bid', msg_details=bid_data)


class RequestSyncMsg(Message):

    ''' RequestSync is a message sent by an auctioneer who 
        requests a timestamp for a pending transaction (a bid).

        Route: Auctioneer -> Timer
    '''
    
    def __init__(self):
        super().__init__(msg_type='request_sync', msg_details={})


class SyncPriceMsg(Message):

    ''' SyncPriceMsg is sent to another auctioneer to update price for
        a specific item. 

        Contains price, item_id, and user with highest bid.
    '''

    def __init__(self, **bid_data):
        super().__init__(msg_type ='sync_price', msg_details=bid_data)


    def __gt__(self, other):

        try:
            return self.msg['item_id'] == other.msg['item_id'] and self.msg['price'] > other.msg['price']
        except AttributeError:
            return False


class SyncMsg(Message):

    ''' SyncMsg is a synchronization message sent to an auctioneer
        in response to a RequestSync message.
        Contains a (logical) timestamp in JSON format.

        Route: Timer -> Auctioneer 
    '''

    def __init__(self, **time_data):
        super().__init__(msg_type='sync', msg_details=time_data)

class CompleteMsg(Message):

    ''' CompleteMsg is sent once the auction is complete and all items
        have been sold or discarded. All bidders must then terminate 
        gracefully.

        Route: Auctioneer -> Everyone
    '''

    def __init__(self):
        super().__init__(msg_type='complete', msg_details={})
