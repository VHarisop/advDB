#!/usr/bin/python

import sys, socket
from socket import error as SocketError

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

