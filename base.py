
import socket, select, sys, signal, time
import random
from socket import error as SocketError

# imports from own code
import serializer as serial
import messages, errors

# timeout and alarm constants
L = 2
M = 2

# set to True if a RuntimeError was raised
dirty_log = False

# use log() to write logging
# messages to standard error
def log(string_arg): 
    try:

        sys.stderr.write(string_arg + '\n')

    except RuntimeError: # reentrant call?
        
        # should not attempt to write again
        dirty_log = True

def max_bid(message_list):

    ''' returns max priced bit out of 
        a list of bid-type messages
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

class Server_Base(object):

    ''' Base class for the Auctioneer class '''

    def sigalrm_handler(self, signum, frame):

        ''' handle L second timeouts for possible price reductions
            and item discards 
        '''
        global L

        log("{0} seconds passed, update timeout".format(L))

        # TODO: rest of handler!
        #       - handle bids
        #       - discard items

        # get item that is currently processed
        # server.current_item is just an id that 
        # points to server.items dict

        # retrieve item if it exists
        try:
            curr_item = self.items[self.curr_item_id]
        except KeyError:
            signal.alarm(L)
            return

        if curr_item['price'] == 0:
            # no price has been offered, nobody interested

            # discard item, inform debug log
            del self.items[self.curr_item_id]
            log('Deleted item {0}'.format(self.curr_item_id)) 
            
            # send a StopBidMsg to the other server
            # to notify about the discarding
            self.sync(messages.StopBidMsg(item_id=self.curr_item_id,
                                          winner=curr_item['holder'])
            )


            
            # item_id is updated (linear assignment of ids)
            self.curr_item_id += 1

        else:
            # >= 1 offers, price must be lowered or item awarded
            if curr_item['timeouts'] > M:        
                try:
                    del self.items[self.curr_item_id]
                    log('Deleted item {0}'.format(curr_item))
                    
                    # TODO: send this message to all the clients
                    self.pending.append(messages.StopBidMsg(
                                        item_id = self.curr_item_id,
                                        winner = curr_item['holder'])
                    )
                except KeyError:
                    log('No item found with id {0}'.format(
                                        self.curr_item_id)
                    )
                
                # send a StopBidMsg to the other server
                self.sync(messages.StopBidMsg(item_id=self.curr_item_id,
                                              winner=curr_item['holder'])
                )

                
                
                # update current item id
                self.curr_item_id += 1

            else:
                # lower price by 10% and update timeout info
                curr_item['price'] *= 0.9 
                curr_item['timeouts'] += 1

        # renew alarm
        signal.alarm(L)
        
    def sigint_handler(self, signum, frame):

        ''' handles abrupt shutdowns from 
            keyboard interrupt events
        '''

        # disable alarms to prevent reentrant calls
        signal.alarm(0)

        log('Closing socket...')

        self.server.close()
        sys.exit(1)


    def __init__(self, host='localhost', 
                       port=50000, 
                       max_connections=27,
                       other_port = 50005):

        # register signal handlers 
        signal.signal(signal.SIGALRM, self.sigalrm_handler)
        signal.signal(signal.SIGINT, self.sigint_handler)

        # initialize connection-related data
        (self.host, self.port)  = (host, port)
        self.max_connections    = max_connections
        self.other_port         = other_port

        # internal state of Lamport Clock
        self.timer              = 0

        # sample items. Initial price is always 0, to be initiated by bidder.
        self.items = {
            1: item_new('Small hat from middle ages', 0),
            2: item_new('Pirate Sword', 0),
            3: item_new('Cupboard from victorian age', 0)
        }

        self.item_ticker = max(self.items.keys())
        # current_item_id is the item that bids 
        # are currently placed on (denoted by id)
        self.curr_item_id = None

        # table of registrars. Each recognized connection is put on this table.
        self.registrar_table = {}

        # list of pending messages
        self.pending = []

        # try initializing the socket
        try:
            self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        except SocketError:
            print('Error initalizing socket')
            exit(1)

        # try initializing other socket
        try:
            self.other = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        except SocketError:
            print('Error initializing gossip socket')
            exit(1)

    def update_price(self, item_id, new_price, holder):

        ''' utility function to update a price based on a 
            received SyncPriceMsg
        '''

        # if new bid was higher indeed, update price
        if self.items[item_id]['price'] < new_price:
            self.items[item_id]['price'] = new_price
            self.items[item_id]['holder'] = holder
            signal.alarm(L)
                                           
    def close(self):
        self.server.close()
        self.other.close()

        
    def sync(self, msg):

        ''' generic function to prioritize and send
            a message to the other server
        '''

        repeat_flag = True
        wr_list = [self.other]

        while repeat_flag:

            [_, wx, _] = select.select([], wr_list, [])

            for elem in wx:
                # if other server is ready, send message 
                # and set repeat flag as false
                if elem == self.other:
                    elem.sendall(msg.send())
                    repeat_flag = False
        
        # debug log
        log('Sent: {0}'.format(msg))

    
    def parse_messages(self, data, connection):

        global L 
        # response: list of messages clear for delivery
        response = []

        # use the '|' delimiter to split buffer 
        # into separate messages. Remove trailing emptiness
        msg_list = [serial.decode_msg(i) for i in data.strip('|').split('|')]

        log('{0}: {1}'.format(self.port, msg_list))

        # advance buffer!
        data = data[sum(len(i) + 1 for i in msg_list):] 

        for msg_dec in msg_list:

            # NOTE: Case 1 -> CONNECT

            if msg_dec['header'] == 'connect':
                # if username already present, we must reject.
                if msg_dec['username'] in self.registrar_table:

                    # response is a rejection message
                    response = messages.ErrorMsg(
                                            username=msg_dec['username'],
                                            error=errors.reject_register)
                    
                    # no other responses should be made
                    return [response]

                # otherwise, register normally
                self.registrar_table[msg_dec['username']] = (
                            connection, 
                            msg_dec['uid']
                )

                response.append(messages.AckConnectMsg())
                response.append(messages.ItemsMsg(items=self.items, 
                                                  current=self.curr_item_id))

            # NOTE: Case 2 -> BID

            if msg_dec['header'] == 'bid':

                # extract bid info
                item_id     = msg_dec['item_id']
                offer       = msg_dec['price']
                username    = msg_dec['username']


                if item_id in self.items:

                    if offer > self.items[item_id]['price']:

                        # FIXME: new high bid msg should always 
                        #        come after a successful response
                        #        from a SyncPriceMsg

                        # update price and holder fields
                        self.items[item_id]['price'] = offer
                        self.items[item_id]['holder'] = username

                        # debug log
                        log('New holder: {0}'.format(username))

                        # renew timeout value
                        signal.alarm(L)

                        # sync with other server on priority
                        self.sync(messages.SyncPriceMsg(
                                        item_id = item_id,
                                        username = username,
                                        price = offer)
                        )
                    
                        # create new high bid response for clients
                        self.pending.append(messages.NewHighBidMsg(
                                        item_id = item_id,
                                        bidder = msg_dec['username'],
                                        price = offer)
                        )

                else:
                    # invalid item id for bid message
                    response.append(messages.ErrorMsg(
                                    item_id = item_id,
                                    username = msg_dec['username'],
                                    error = errors.invalid_item_id)
                    )

            # NOTE: Case 3 -> SYNCPRICE

            if msg_dec['header'] == 'sync_price':

                # get info
                price    = msg_dec['price']
                item_id  = msg_dec['item_id']
                username = msg_dec['username']

                # update info if necessary
                if self.items[item_id]['price'] < price:

                    # update item info
                    self.items[item_id]['price'] = price
                    self.items[item_id]['holder'] = username

                    # add to pending messages to inform clients
                    self.pending.append(messages.NewHighBidMsg(
                                        item_id = item_id,
                                        price = price,
                                        bidder = username)
                    )
                    
                    # debug log
                    log('Holder: {0}'.format(self.items[item_id]['holder']))

                    # renew timeout for item
                    signal.alarm(L)

                # other server sent a false message
                # we need to sync again!
                else:                    
                    # send syncprice to other server
                    self.sync(messages.SyncPriceMsg(
                                        item_id = item_id,
                                        price = price,
                                        username = username)
                    )

            # NOTE: Case 4 -> STOPBID

            if msg_dec['header'] == 'stop_bid':

                # add a stop bid message to pending messages
                # in order to be delivered to all my clients
                stopmsg = messages.StopBidMsg(
                                    item_id = msg_dec['item_id'],
                                    winner = msg_dec['winner']
                )

                # only add if message is not already there
                # from sigalrm trigger
                self.pending.append(stopmsg)
                
                if msg_dec['item_id'] in self.items:
                    # if in my items, I must delete it
                    # as the other guy got triggered by alarm
                    del self.items[msg_dec['item_id']]
                    log('Deleted item %d' % msg_dec['item_id'])

            # TODO: handle bid status
            # TODO: handle each message accordingly
        
        # return list of messages for response
        return response


