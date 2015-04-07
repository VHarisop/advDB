#!/usr/bin/python

# imports here
import time, json, socket, signal, select
from socket import error as SocketError
import sys
import messages
from serializer import unpack_msg, decode_msg

def log(msg):
   
    ''' logging function for standard error '''
    sys.stderr.write(msg + '\n')

class Bidder(object):
    
    ''' Bidder is, as expected, the class that implements
        an auction bidder. A socket is created, a connection
        to an auction server is attempted and, after a successful
        connection is established, the bidding logic is implemented.
    '''

    def __init__(self, username, uid, server_address=('localhost', 50000)):

        # initialize my identifiers
        self.uid = uid
        self.username = username

        # client status structure
        self.status = {
            'bidding': False,       # can i bid?
            'item_id': None,        # which item is now?
            'min_price': 0,         # minimum offer?
        }

        # list of items to be auctioned
        # + index of current item in auction
        # NOTE: these are received after a successful connect + ack handshake
        self.items = {}
        self.current_item = None

        # can i participate in the auction?
        # this flag is updated after receiving the Items msg.

        # NOTE: using the **kwargs notation for initializing messages
        connmsg = messages.ConnectMsg(uid=uid, username=username)
        
        # try to initialize socket
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        except SocketError:
            log('Unable to initialize socket')
            exit(1)

        # attempt a connection to the server
        try:
            self.sock.connect(server_address)
        except ConnectionRefusedError:
            log('Connection refused on {0}:{1}'.format(server_address[0],
                                                         server_address[1]))
            exit(1)

        # send a connection message in order to become registered
        self.sock.sendall(connmsg.send())

    def update_price(self, price, bidder):

        ''' Update the price of an item after a 
            new_high_bid message. '''

        self.items[self.current_item]['price'] = price
        self.items[self.current_item]['holder'] = bidder

        # also update my status variable
        self.status['min_price'] = price

    def send_bid(self, bid_price):

        ''' insists on sending a Bid Message 
            to the auction server '''

        [_, wx, _] = select.select([], [self.sock], [])

        while True:

            if self.sock in wx:
                
                # insist on sending the message to the auction server
                self.sock.sendall(messages.BidMsg(
                                    item_id=self.current_item,
                                    price=bid_price,
                                    username=self.username).send())

                # exit the "insist" loop
                break

    def complete(self):
        
        ''' Sends a CompleteMsg to finish session with server '''

        self.sock.sendall(messages.CompleteMsg().send())

    def parse_client(self, data):

        # NOTE: this function is a general-purpose function
        #       that parses input sources like sys.stdin.
        # FIXME: To be replaced with input from UI

        # if empty: skip
        if not data: return

        if data[0].lower() == 'bid':

            # get bid amount
            price = int(data[1])

            if price <= self.status['min_price']:
                # only allow bids greater than current highest
                log('The amount you bid is incorrect!')

            else:
                # submit the client's bid
                while True:

                    [_, rx, _] = select.select([], [self.sock], [])

                    if self.sock in rx:
                        self.sock.sendall(messages.BidMsg(
                                            item_id=self.current_item,
                                            price=price,
                                            username=self.username).send())

                        break

        elif data[0].lower() == 'exit':

            # exit bidder application
            self.sock.close()
            exit(1)

    def parse_messages(self, data, connection):

        ''' Parses received data from auction servers '''

        response = []

        # split based on delimiter and advance buffer
        msg_list = [decode_msg(msg) for msg in data.strip('|').split('|')]
        data = data[sum(len(i) + 1 for i in msg_list):]

        for msg in msg_list:
            
            # TODO: handle all cases

            if msg['header'] == 'items':
                # iterate over all keys
                for key in msg['items'].keys():
                    self.items[int(key)] = msg['items'][key]
                
                # update current item info
                self.current_item = msg['current']
                # also update status variable
                self.status['item_id'] = self.current_item
            
                if self.items[self.current_item]['holder'] == None:    
                    # mark me as participant
                    self.status['bidding'] = True
                    log('Can participate!')

                else:

                    log('Cant participate')

                print(self.items)

            if msg['header'] == 'sync_price':
                # update item info
                self.update_price(msg['price'], msg['username'])
                log('New price: %d' % msg['price'])

            if msg['header'] == 'new_high_bid':
                # update item info
                self.update_price(msg['price'], msg['bidder'])
                log('New price: %d' % msg['price'])

            if msg['header'] == 'stop_bid':

                # mark myself as participant 
                self.status['bidding'] = True

                try:
                    del self.items[msg['item_id']]
                    log('Deleted item %d won by %s' % (msg['item_id'],
                                                         msg['winner']))
                    # NOTE: 2 approaches here:
                    #       a. autoincrement current item OR
                    #       b. wait for an auctioneer message with
                    #       c. the new item
                    
                    self.current_item += 1 

                    # update status variable
                    self.status['item_id'] = self.current_item
                    # minimum price is reset
                    self.status['min_price'] = 0

                    log('New item: {0}'.format(
                                self.items[self.current_item]))
                    
                except KeyError:
                    # item was already deleted (erroneous, but can be handled)
                    # log('Item %d already deleted' % msg['item_id'])
                    pass
                
            if msg['header'] == 'ack':
                log('acknowledged from server')

            if msg['header'] == 'error':
                log('error')

        print(self.status)
        return response

    def run(self):

        flag = True
        rdr_list = [self.sock, sys.stdin]
        wrr_list = [self.sock]

        while flag:

            # wait until something is ready
            [rx, wx, ex] = select.select(rdr_list,
                                         wrr_list,
                                         [])
 
            for conn in rx:

                # something was received
                if conn == self.sock:
                    # receive 1K packet
                    data = unpack_msg(conn.recv(1024))

                    # parse data if available
                    if data:
                        self.parse_messages(data, conn)
                    else:
                        log('Disconnected from {0}'.format(conn))
                        rdr_list.remove(conn)
                   
                    # TODO: handle all cases!

                elif conn == sys.stdin:

                    # TODO: handle user input!
                    # pass
                    # flag = False
                    data = sys.stdin.readline().strip().split()
                    self.parse_client(data)


def parse_address(address_string):
    
    s = address_string.split(':')
    return (s[0], int(s[1]))


if __name__ == '__main__':

    server_address = ('localhost', 50000)

    # FIXME: fix message concatenation on auctioneer.py
    # FIXME: omission of time.sleep(2) results in buggy behavior

    if len(sys.argv) >= 3:

        try:
            server_address = parse_address(sys.argv[3])
        except IndexError:
            server_address = ('localhost', 50000)
        finally:
            pass

        try:
            price = int(sys.argv[4])
        except IndexError:
            price = 100
        try:
            bidr = Bidder(sys.argv[1], int(sys.argv[2]), server_address)
            bidr.run()
            bidr.complete()
        finally:
            pass
    else:
        log('Usage: ./bidder.py username id')

