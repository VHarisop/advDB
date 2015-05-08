#!/usr/bin/python

import sys, socket, select
from socket import error as SocketError
from serializer import unpack_status

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

