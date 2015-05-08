#!/usr/bin/python

import sys, socket, select, signal, time
from socket import error as SocketError
from serializer import unpack_status

class Messenger(object):

    def sigalrm_handler(self, signum, frame):

        # renew my alarm
        signal.alarm(self.frequency)

        # get my next action
        self.next_response = self.actions()


    def __init__(self, username, freq, min_bid, max_bid, offers):
        self.username = username
        self.frequency = freq
        self.min_bid = min_bid
        self.max_bid = max_bid
        self.offers = offers

        # status variable to be retrieved from bidder client
        self.status = None

        # register my signal handler
        signal.signal(signal.SIGALRM, self.sigalrm_handler)

    def actions(self):

        response = None

        if not self.status: return response

        status = self.status

        # if my offers are over, I must quit
        if not self.offers:
            response = "quit"
            return response 

        if status['bidding'] and not status['acknowledged']:
            response = "int"
        
        elif status['bidding'] and status['acknowledged']:

            offer = self.offers.pop(0)

            # if my offer is good, send it to the auctioneer
            if offer > status['min_price']:
                response = "bid " + str(offer)
                                     
            else:
                # wait for next item
                response = None

        # return my next to-do response
        return response

    def simulate(self):

        # wait for other socket to be setup succesfully
        time.sleep(1)
        # create the UNIX socket to communicate with client
        try:
            client_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            client_socket.connect(self.username)
        except SocketError:
            exit(0)
           
        # initially I don't do anything
        self.next_response = None
        signal.alarm(self.frequency)

        while True:

            # main loop
            #       given a client bidding frequency and bid limits,
            #       make bids to the client without violating constraints

            rx, wx, _ = select.select([client_socket], [client_socket], [])

            if client_socket in rx:

                sock_data = client_socket.recv(512)
                if sock_data:
                    self.status = unpack_status(sock_data)
                    print(self.status)
                else:
                    exit(0)


            if client_socket in wx:

                if self.next_response: 
                    # TODO: send messages here
                    client_socket.sendall(bytes(self.next_response, 'ascii'))

                    # reset my to-do response until it is update
                    # by my sigalrm handler
                    self.next_response = None
                    

if __name__ == '__main__':

    try:
        client_name = './' + sys.argv[1]
        
        # get message from command line
        msg = ' '.join(sys.argv[i] for i in range(2, len(sys.argv)))

        # serialize
        msg = bytes(msg, "ascii")

    except IndexError:
        print('Usage: ./messenger.py <client> <message>')
        exit(0)

    try:
        client_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        client_socket.connect(client_name)
    except SocketError:
        exit(0)

    client_socket.sendall(msg)

    while True:

        # main loop
        # TODO: given a client bidding frequency and bid limits,
        #       make bids to the client without violating constraints

        rx, _, _ = select.select([client_socket], [], [])

        if client_socket in rx:

            sock_data = client_socket.recv(512)
            if sock_data:
                log = unpack_status(sock_data)
                print(log)
            else:
                exit(0)

