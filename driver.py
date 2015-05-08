#!/usr/bin/python

''' Driver component for the auction '''

import xml.etree.ElementTree as ET
import multiprocessing
import sys, time
import auctioneer, bidder, messenger
    
def client_worker(port, username):

    # create a bidder at specified port
    clnt = bidder.Bidder(username = username,
                         server_address = ('localhost', port))

    clnt.run()

    return

def messenger_worker(username, frequency, min_bid, max_bid, offers):

    # create a messenger script to communicate 
    # with its corresponding client
    msgr = messenger.Messenger(username,
                               frequency,
                               min_bid,
                               max_bid,
                               offers)

    msgr.simulate()

    return


def worker(port, other_port, items_file, connections):

    sys.stderr = open('auctlog_' + str(port) + ".err", 'w')
    # create an auctioneer with specified parameters
    server = auctioneer.Auctioneer(port = port,
                                   other_port = other_port,
                                   itemfile = items_file,
                                   max_connections = connections)

    server.serve()

    return




def server_data(conf_file):

    ''' parses an xml file to find server
        attributes, such as ports, max no.
        of clients, item file etc. 
    '''

    # get root of xml file
    root = ET.parse(conf_file).getroot()
    
    # get item file from config
    item_fd = root.find('items').attrib['file']
    
    # get individual server configs
    servers = [(srv.attrib['port'], srv.attrib['clients'])
                for srv in root.iter('server')]

    return (item_fd, servers)

def client_data(conf_file):

    ''' parses an xml file to retrieve parameters
        for the clients, e.g. bidding frequency etc. '''

    root = ET.parse(conf_file).getroot()
    
    client_data = lambda conn, bid, offers: { 
          'port': conn.attrib['server'],
          'freq': int(conn.attrib['freq']),
          'min': int(bid.attrib['min']),
          'max': int(bid.attrib['max']) 
        }

    # get attributes for all clients in the xml file
    clients = [ 
        {
         'username': clnt.attrib['username'],
         'conf': client_data(*clnt.getchildren()),
         'offers': [int(i) for i in \
                    clnt.find('offers').text.strip().split()]
        } 
    for clnt in root.iter('client')]

    return clients

if __name__ == '__main__':

    # retrieve server and client parameters
    itemfile, server_conf = server_data('config.xml')
    clients = client_data('config.xml')

    # get ports and max connections
    ports, conns = zip(*[(int(i[0]), int(i[1])) for i in server_conf])

    # create both auctioneers
    auct1 = multiprocessing.Process(
                target = worker, 
                args = (ports[0], ports[1], itemfile, conns[0])
            )

    
    auct2 = multiprocessing.Process(
                target = worker, 
                args = (ports[1], ports[0], itemfile, conns[1])
            )

    # start serving
    auct1.start()
    auct2.start()

    # wait for auctioneers to start
    print("Starting servers...")
    time.sleep(3)
    

    # TODO: create the client processes and their 
    #       messenger counterparts
    
    for clnt in clients:

        # create all of the bidder clients
        clnt_proc = multiprocessing.Process(
                target = client_worker,
                args = (int(clnt['conf']['port']), clnt['username'],)
        )

        clnt_proc.start()
       
        msgr = multiprocessing.Process(
                target = messenger_worker,
                args = (clnt['username'],
                        clnt['conf']['freq'],
                        clnt['conf']['min'],
                        clnt['conf']['max'],
                        clnt['offers'],)
        )

        msgr.start()

