#!/usr/bin/python

''' Driver component for the auction '''

import xml.etree.ElementTree as ET
import multiprocessing
import sys
import auctioneer

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
    
    client_data = lambda conn, bid: { 
          'port': conn.attrib['server'],
          'freq': conn.attrib['freq'],
          'min': int(bid.attrib['min']),
          'max': int(bid.attrib['max']) 
        }

    # get attributes for all clients in the xml file
    clients = [ 
        {
         'username': clnt.attrib['username'],
         'conf': client_data(*clnt.getchildren())
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

    # TODO: create the client processes and their 
    #       messenger counterparts
