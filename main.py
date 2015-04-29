#!/usr/bin/python

import multiprocessing
import auctioneer

def worker(port, other_port):
    server = auctioneer.Auctioneer(port = port, other_port = other_port)
    server.serve()

    return

if __name__ == '__main__':

    # create the 2 auction servers
    p1 = multiprocessing.Process(target = worker, args=(50000, 50005,))
    p2 = multiprocessing.Process(target = worker, args=(50005, 50000,))

    # start serving
    p1.start()
    p2.start()
