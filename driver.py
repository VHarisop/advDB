#!/usr/bin/python

''' Driver component for the auction '''

import xml.etree.ElementTree as ET
import multiprocessing
import auctioneer

def worker(port, other_port, items_file, connections):
    
    # create an auctioneer with specified parameters
    server = auctioneer.Auctioneer(port = port,
                                   other_port = other_port,
                                   itemfile = items_file,
                                   max_connections = connections)

    server.serve()

    return

def server_data(conf_file):

    ''' parses an xml file to find server
        attributes, such as ports, number
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

if __name__ == '__main__':

    itemfile, server_conf = server_data('config.xml')

    # get ports and max connections
    ports = [int(i[0]) for i in server_conf]
    conns = [int(i[1]) for i in server_conf]

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
