
import socket, select, sys, signal, time
import random
from socket import error as SocketError

# imports from own code
import serializer as serial
import messages, errors

# timeout and alarm constants
L = 5
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

def item_new(about, price):

    ''' helper function for handy item representation '''

    return {
        'about': about,
        'price': price,
        'holder': None,
        'interested': [],
        'timeouts': 0
    }

class Server_Base(object):

    ''' Base class for the Auctioneer class '''

    def sigalrm_handler(self, signum, frame):

        ''' handle L second timeouts for possible price reductions
            and item discards 
        '''
        global L

        log("{0} seconds passed, update timeout - {1}".format(L, self.port))

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

            if not self.items:

                # notify my auctioneers to finish auction
                # reset alarms, do not renew
                self.pending.append(messages.CompleteMsg())
                signal.alarm(0)

            else:
                signal.alarm(L)
            
            return

        if curr_item['interested'] == []:
            # no price has been offered, nobody interested

            # discard item, inform debug log
            del self.items[self.curr_item_id]
            log('Deleted item {0}'.format(self.curr_item_id)) 
            
            # send a StopBidMsg to the other server
            # to notify about the discarding
            self.sync(messages.StopBidMsg(item_id=self.curr_item_id,
                                          winner=curr_item['holder'])
            )

            # also notify my clients
            self.pending.append(messages.StopBidMsg(
                                    item_id=self.curr_item_id,
                                    winner=curr_item['holder']))

            # if no items remain, do not renew alarm
            # and inform my clients about completion of auction
            if not self.items:
                signal.alarm(0)
                self.pending.append(messages.CompleteMsg())
                return

            # item_id is updated (linear assignment of ids)
            self.curr_item_id = min(self.items)

            # notify my clients for bidding on new item
            self.pending.append(self.start_msg())
            self.interest_phase = True

        else:
            
            # update timeouts
            self.items[self.curr_item_id]['timeouts'] += 1
            self.interest_phase = False

            # >= 1 offers, price must be lowered or item awarded

            # nobody has initially bid on the item - reduce price!
            if curr_item['holder'] == None and curr_item['timeouts'] > 1:
                self.items[self.curr_item_id]['price'] *= 0.9
 
                # send this message to inform every client
                self.pending.append(messages.SyncPriceMsg(
                                        item_id=self.curr_item_id,
                                        username=curr_item['holder'],
                                        price=(curr_item['price'] * 0.9)))          

            if curr_item['timeouts'] > M:        

                try:
                    del self.items[self.curr_item_id]
                    log('Deleted item {0}'.format(curr_item))
                    
                    self.pending.append(messages.StopBidMsg(
                                        item_id = self.curr_item_id,
                                        winner = curr_item['holder']))

                except KeyError:

                    log('Item with id %d already deleted' % self.curr_item_id)
                
                try:

                    if self.items:

                        # update item counter
                        self.curr_item_id = min(self.items)

                        # send a start bid message for the next item
                        self.pending.append(self.start_msg())
                        self.interest_phase = True

                except KeyError:
                    log('No item found with id {0}'.format(
                                        self.curr_item_id))
                


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
                       other_port = 50005,  
                       itemfile="items.txt"):

        # register signal handlers 
        signal.signal(signal.SIGALRM, self.sigalrm_handler)
        signal.signal(signal.SIGINT, self.sigint_handler)

        # initialize connection-related data
        (self.host, self.port)  = (host, port)
        self.max_connections    = max_connections
        self.other_port         = other_port

        # sample items. Initial price is always 0, to be initiated by bidder.
        self.items = {
            1: item_new('Small hat from middle ages', 0),
            2: item_new('Pirate Sword', 0),
            3: item_new('Cupboard from victorian age', 0),
            4: item_new('A flyer from 1880s Chicago', 0)
        }

        self.interest_phase = False
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

    def start_msg(self):

        ''' Creates a StartBidMsg based on the auction's current state '''

        return messages.StartBidMsg(
                    item_id = self.curr_item_id,
                    price = self.items[self.curr_item_id]['price'],
                    description = self.items[self.curr_item_id]['about'])

        
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
        # log('Sent: {0}'.format(msg))

    
    def parse_messages(self, data, connection):

        global L 
        # response: list of messages clear for delivery
        response = []

        # use the '|' delimiter to split buffer 
        # into separate messages. Remove trailing emptiness
        msg_list = [serial.decode_msg(i) for i in data.strip('|').split('|')]

        # message log
        # log('{0}: {1}'.format(self.port, msg_list))

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
                self.registrar_table[msg_dec['username']] = connection

                response.append(messages.AckConnectMsg())

                # if no items left, auction is complete 
                if not self.items: 
                    response.append(messages.CompleteMsg())
                    return response

            # NOTE: Case 2 -> BID

            if msg_dec['header'] == 'bid':

                # extract bid info
                item_id     = msg_dec['item_id']
                offer       = msg_dec['price']
                username    = msg_dec['username']

                if item_id in self.items:

                    if self.interest_phase:

                        # we are still in the interest phase
                        # and client should wait for next phase
                        response.append(messages.ErrorMsg(
                                username=username,
                                error=errors.interest_phase))

                        continue

                    if offer > self.items[item_id]['price']:

                        # FIXME: new high bid msg should always 
                        #        come after a successful response
                        #        from a SyncPriceMsg

                        # update price and holder fields
                        self.items[item_id]['price'] = offer
                        self.items[item_id]['holder'] = username

                        # reset timeouts!
                        self.items[item_id]['timeouts'] = 0
                        log('Reset timeout')

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

                    # update timeouts
                    self.items[item_id]['timeouts'] = 0

                    # add to pending messages to inform clients
                    self.pending.append(messages.NewHighBidMsg(
                                        item_id = item_id,
                                        price = price,
                                        bidder = username)
                    )
                    
                    # debug log
                    log('New holder: {0}'.format(self.items[item_id]['holder']))

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
                
                
                if msg_dec['item_id'] in self.items:
                    
                    # only add if message is not already there
                    # from sigalrm trigger
                    self.pending.append(stopmsg)

                    # if in my items, I must delete it
                    # as the other guy got triggered by alarm
                    try:
                        del self.items[msg_dec['item_id']]
                        log('Deleted item %d' % msg_dec['item_id'])
                    except KeyError:
                        pass

                    if self.items:  
                        # if nonempty, update item counter
                        try:
                            self.curr_item_id = min(self.items)
                            self.pending.append(self.start_msg())
                            self.interest_phase = True
                        except KeyError:
                            pass

                if not self.items:
                    # inform my clients that auction is finished
                    self.pending.append(messages.CompleteMsg())

            # NOTE: Case 5 -> INTERESTED
                
            if msg_dec['header'] == 'i_am_interested':

                if self.items[self.curr_item_id]['timeouts'] == 0:

                    # add user to interested people
                    self.items[self.curr_item_id]['interested'].append(
                                        msg_dec['username'])

                    log('User %s is interested for item %d' % 
                                (msg_dec['username'], self.curr_item_id))

                    # sync with other server
                    self.sync(messages.SyncInterestMsg(
                                    username=msg_dec['username']))

                    # respond to bidder with acknowledgement message
                    response.append(messages.AckInterestMsg())



            # NOTE: Case 6 -> STARTAUCTION

            if msg_dec['header'] == 'start_auction':

                # start the alarm sequence here
                self.auctioning = True
                signal.alarm(L)

            if msg_dec['header'] == 'sync_interest':

                # update interest info for item
                self.items[self.curr_item_id]['interested'].append(
                            msg_dec['username'])
    
            if msg_dec['header'] == 'quit':

                # retrieve disconnected client's identity
                # and remove from registrar table

                if msg_dec['username'] in self.registrar_table:
                    del self.registrar_table[msg_dec['username']]
                    log('Removed user %s' % msg_dec['username'])

                # NOTE: connections that close abruptly
                #       do not send this message. They are handled
                #       in the serve() loop instead.
                #       No need to remove from select.select's lists,
                #       as it is handled there too.
        
        # return list of messages for response
        return response


