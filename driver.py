#!/usr/bin/python

''' Driver component for the auction '''

import xml.etree.ElementTree as ET

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

   

    
