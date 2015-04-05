#!/usr/bin/python

import socket, sys, select, signal, time
import random
from socket import error as SocketError


from base import Server_Base

# imports from own code
import serializer as serial
import messages, errors

L = 2
M = 2
# L is the timeout in seconds for bidding actions
# M is the number of price lowering timeouts allowed
# before the item must be awarded to highest bidder

def max_bid(message_list):
 
    ''' returns max priced bid out of a list
        of bid type messages 
    '''

    return max(message_list, 
               key = lambda mesg: mesg.msg['price'])

def item_new(about, price):

    ''' helper function for handy item representation '''

    return {
        'about': about, 
        'price': price, 
        'holder': None, 
        'timeouts': 0
    }

class Auctioneer(Server_Base):

    ''' The Auctioneer class emulates an auctioning web server.
        It listens, by default, on port 50000 of localhost and
        for 27 connections maximum (25 clients + other server +
        sync server).

    '''
    def handle_responses(self, response_list, elem):

        ''' this function sends all the messages in 
            response_list to a specifiec connection
            by using select until the connection is
            writable.
        '''

        if not response_list: return

        # send every message that is in response list
        # to the provided element

        # create a byte buffer with all messages to be sent
        sendbuff = b''.join(i.send() for i in response_list)

        while True:
            # retry until message is sent
            [_, wx, _] = select.select([], [elem], [])

            if elem in wx:
                elem.sendall(sendbuff)
                break

    def bootstrap(self):

        # try to bind to socket, exit if failure
        try:
            self.server.bind((self.host, self.port))
        except SocketError:
            print('Error binding to {0}:{1}'.format(self.host, self.port))
            self.server.close()
            exit(1)

        # listen to max_connections
        self.server.listen(self.max_connections)

        read_conns = [self.server]
        write_conns = []
        ex_conns = []

        # sleep for a second to ensure other server has been bound
        time.sleep(1)
        self.other.connect((self.host, self.other_port))

        while True:
            
            # poll ready sockets
            [rx, _, _] = select.select(read_conns, write_conns, ex_conns)

            if self.server in rx:

                conn, addr = self.server.accept()
                print('Accepted connection from \
                       {0}'.format(addr))


                # set connection to non-blocking
                conn.setblocking(0)
                self.other_server = conn

                # stop retrying
                break


        # initialize registrar table and item auctioned
        self.registrars = {}
        self.curr_item_id = 1


    def serve(self):

        BUFF_SIZE = 2048
    
        # connect with other server, set variables etc.        
        self.bootstrap()


        # fd list for select system calls
        read_conns = [self.server, self.other_server]
        write_conns = [self.other_server]
        ex_conns = []

        # initialize server loop
        while True:

            self.pending = []
            # wait until someone is ready
            [rx, wx, ex] = select.select(read_conns,
                                         write_conns,
                                         ex_conns)

            # initialize response list 
            # one field for each incoming socket
            response_list = {}
            for elem in rx:

                # input is server => incomming connections
                if elem == self.server:
                    connection, client_address = elem.accept()
                    print(
                        'new connection from {0}'.format(client_address)
                    )
                    # set connection to non-blocking to enable polls
                    connection.setblocking(0)
                    
                    # add incoming connection to read_list
                    read_conns.append(connection)
                    write_conns.append(connection)

                else:                    
                    # TODO: handle:
                    #       1 - message fragmentation
                    #       2 - possible message concatenation
                    # messages are less than 1024 bts long
                    # also unpacking is needed for the bytes
                    data = serial.unpack_msg(elem.recv(BUFF_SIZE))
                    print(self.port, data)
                    # readable sockets always have data
                    if data: 
                        # parse incoming messages, create response list
                        response_list[elem] = self.parse_messages(data, elem)
                    else:
                        print('closing{0}\n'.format(elem))
                        read_conns.remove(elem)
                        write_conns.remove(elem)

            # TODO: INCOMPLETE!!!
            for elem in wx: 
       
                # if connection is in the response_list, send all
                # the messages designated for it
                if elem in response_list:
                    self.handle_responses(response_list[elem], elem)

                # if the connection is not the other server 
                # send all the pending messages as well

            for elem in write_conns:
                if elem != self.other_server:
                    self.handle_responses(self.pending, elem)



        
if __name__ == '__main__':

    # register signal handler for socket closing
    # upon keyboard interrupts (CTRL+C)

    server = Auctioneer()
    server.serve()
