#!/usr/bin/python

# imports here
import os
import time, json, socket, signal, select
from socket import error as SocketError
import sys

# import my modules
import messages, errors
from serializer import unpack_msg, decode_msg, encode_status

def log(msg):
   
    ''' logging function for standard error '''
    sys.stderr.write(msg + '\n')

class Bidder(object):
    
    ''' Bidder is, as expected, the class that implements
        an auction bidder. A socket is created, a connection
        to an auction server is attempted and, after a successful
        connection is established, the bidding logic is implemented.
    '''

    def __init__(self, username, server_address=('localhost', 50000)):

        # initialize my identifier(s)
        self.username = username

        # client status structure
        self.status = {
            'bidding': False,       # can i bid?
            'item_id': None,        # which item is now?
            'min_price': 0,         # minimum offer?
            'acknowledged': False,  # have i been acknowledged?
            'holder': None,         # who holds the item?
            'description': ''
        }

        # NOTE: using the **kwargs notation for initializing messages
        connmsg = messages.ConnectMsg(username=username)
        
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

        self.status['min_price'] = price
        self.status['holder'] = bidder


    def send_bid(self, bid_price):

        ''' insists on sending a Bid Message 
            to the auction server '''

        [_, wx, _] = select.select([], [self.sock], [])

        while True:

            if self.sock in wx:
                
                # insist on sending the message to the auction server
                self.sock.sendall(messages.BidMsg(
                                    item_id=self.status['item_id'],
                                    price=bid_price,
                                    username=self.username).send())

                # exit the "insist" loop
                break

    def parse_client(self, data):

        # NOTE: this function is a general-purpose function
        #       that parses input sources like sys.stdin.

        # if empty: skip
        if not data: return

        if data[0].lower() == 'bid':

            # if not acknowledged, client cannot bid
            if not self.status['acknowledged']:
                log('You have not been acknowledged for bidding!')
                return 
                
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
                                            item_id=self.status['item_id'],
                                            price=price,
                                            username=self.username).send())

                        break
        
        elif data[0].lower() == 'int':

            # send an InterestedMsg to the server to enable bidding
            self.sock.sendall(messages.InterestedMsg(
                                username=self.username).send())

        elif data[0].lower() == 'quit':

            # send a 'quit' message to the server to finish session
            self.sock.sendall(messages.QuitMsg(username=self.username).send())

            # close socket and exit application 
            self.sock.close()
            exit(1)

        elif data[0].lower() == 'list_bid':

            print('Highest bid: %d from %s' % (self.status['min_price'],
                                               self.status['holder']))

        elif data[0].lower() == 'list_description':
            
            print('Item: %s' % self.status['description'])

        else:

            log('Cannot handle command %s' % data[0])

    def parse_messages(self, data, connection):

        ''' Parses received data from auction servers '''

        response = []

        # split based on delimiter and advance buffer
        msg_list = [decode_msg(msg) for msg in data.strip('|').split('|')]
        data = data[sum(len(i) + 1 for i in msg_list):]

        # log
        # print('DATA: ', msg_list)


        for msg in msg_list:

            # TODO: define a meaningful return value 
            #       for the client's parse_messages() method

            if msg['header'] == 'sync_price':
                self.update_price(msg['price'], msg['username'])
                log('New price: %d' % msg['price'])

            if msg['header'] == 'new_high_bid':
                self.update_price(msg['price'], msg['bidder'])
                log('New price: %d' % msg['price'])

            if msg['header'] == 'ack_interest':
                self.status['acknowledged'] = True

                log('Can now bid for item')

            if msg['header'] == 'start_bid':
                
                # mark myself as participant, as a new item is introduced
                self.status['bidding'] = True

                # need an explicit acknowledgement message
                self.status['acknowledged'] = False

                # update status variable
                self.status['item_id'] = msg['item_id']
                self.status['min_price'] = msg['price']
                self.status['description'] = msg['description']

                log('New item: {0} - {1}'.format(
                        msg['description'],
                        msg['price']))


            if msg['header'] == 'stop_bid':

                # disable bidding until next item is presented
                self.status['bidding'] = False
                self.status['acknowledged'] = False

                # update log
                log('Item %d won by %s' % (msg['item_id'], msg['winner']))

                # update holder/price on status variable
                self.status['holder'] = None
                self.status['min_price'] = 0

            if msg['header'] == 'ack':
                log('acknowledged from server')

            if msg['header'] == 'complete':
                log('Auction has finished, will now terminate...')

                # send quit message before exiting and closing socket 
                self.sock.sendall(messages.QuitMsg(username=self.username).send())
                self.sock.close()
                exit(0)

            if msg['header'] == 'error':

                if msg['error'] == errors.invalid_item_id:
                    log('error: id {0} is not valid'.format(msg['item_id']))
                
                if msg['error'] == errors.reject_register:
                    log('error: username {0} is already used'.format(
                                                        msg['username']))
                    exit(1) # NOTE: fatal error!

                if msg['error'] == errors.low_price_bid:
                    log('error: bid price was too low')

                if msg['error'] == errors.max_connections:
                    log('error: maximum No. of connections reached')

                    exit(1) # NOTE: fatal error!

                if msg['error'] == errors.not_accepting:
                    log('Currently not accepting bids')

                if msg['error'] == errors.interest_phase:
                    log('We are not yet in the bidding phase! Please wait')

        # print(self.status)
        return response

    def run(self):

        # remove previous instances of socket
        try:
            os.unlink('./' + self.username)
        except OSError:
            if os.path.exists('./' + self.username):
                raise
            
        try:
            frontend = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            frontend.bind('./' + self.username)
            frontend.listen(1)
            log('Succesfully bound to socket %s' % self.username)
        except SocketError:
            log('Could not bind to socket %s' % self.username)
            exit(0)

        flag = True
        rdr_list = [self.sock, frontend]
        wrr_list = [self.sock, frontend]

        # boolean that indicates I have received a message from server
        msg_received = False

        # my unix socket connection
        usock_connection = None

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
                        msg_received = True
                    else:
                        log('Disconnected from {0}'.format(conn))
                        rdr_list.remove(conn)
                   
                elif conn == frontend:
                    
                    # connection in local UNIX socket attempted                    
                    usock_connection, client_address = conn.accept()
                    log('New connection from {0}'.format(client_address))

                    # nonblocking connection
                    usock_connection.setblocking(0)
                    
                    # add to lists
                    rdr_list.append(usock_connection)
                    wrr_list.append(usock_connection)

                else:
                    # AF_UNIX socket case!
                    data = conn.recv(512).decode('ascii')

                    if data:
                        log('Received from frontend: %s' % data)
                        self.parse_client(data.split())
                    else:
                        log('Removed {0}'.format(conn))
                        rdr_list.remove(conn)
                        wrr_list.remove(conn)

            # If i received something from server I must
            # echo my status to the frontend
            if msg_received and usock_connection in wx:
                usock_connection.sendall(encode_status(self.status))

                # reset msg flag
                msg_received = False

def parse_address(address_string):

    ''' parses an ip address given as a command line option
        in the form [address:port] '''

    s = address_string.split(':')
    return (s[0], int(s[1]))


if __name__ == '__main__':

    # default server address
    server_address = ('localhost', 50000)

    if len(sys.argv) >= 2:
        try:
            server_address = parse_address(sys.argv[2])
        except IndexError:
            server_address = ('localhost', 50000)
        finally:
            pass

        try:
            bidr = Bidder(sys.argv[1], server_address)
            bidr.run()
        finally:
            pass
    else:
        log('Usage: ./bidder.py username [host:port]')

