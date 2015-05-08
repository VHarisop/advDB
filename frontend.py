#!/usr/bin/python2
# -*- coding: utf-8 -*-

import curses, sys
from curses.textpad import Textbox, rectangle
from curses import wrapper

def frontend(stdscr):
    
    ''' An echoing client - to be modified for 
        communication with the bidder backend '''

    # create screen, add window
    stdscr.addstr(0, 0, "Enter Command: ")
    outwin = curses.newwin(1, 30, 6,1)

    # create 2 box areas
    rectangle(stdscr, 1, 0, 1+1+1, 1+30+1)
    rectangle(stdscr, 5, 0, 5+1+1, 1+30+1)

    # catch user input
    box = Textbox(outwin)

    # enable hardware rendering + scrolling
    outwin.idlok(1)
    outwin.scrollok(True)

    # previous message length - useful for deletion!
    prev_message_len = 0

    while True:

        # redraw stuff if necessary
        stdscr.refresh()

        # Let the user edit until Ctrl-G is struck.
        box.edit()

        # Get resulting contents
        message = box.gather()
    
        # scroll down the box
        outwin.scroll(1)
        outwin.move(0, 0)

        # delete stuff in output box
        for i in range(prev_message_len):
            stdscr.addch(2, 1 + i, ' ')
        stdscr.addstr(2, 1, message, 28)
        prev_message_len = len(message)


if __name__ == '__main__':
    wrapper(frontend)
