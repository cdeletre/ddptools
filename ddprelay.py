#!/usr/bin/env python3

import argparse                         # for the command line arguments
from ddp.ddpdevice import DDPdevice     # for DDP
import socket                           # UDP
import logging, sys

INDICATOR = '/-\|'                      # spining indicator chars
ERASE_LINE = '\x1b[2K'      # Erase content of a line
CURSOR_UP_ONE = '\x1b[1A'   # Go to upper line

def main():

    logger = logging.getLogger('ddprelay')
    sh = logging.StreamHandler(sys.stderr)
    formatter = logging.Formatter('[%(asctime)s] %(levelname)s [%(filename)s.%(funcName)s:%(lineno)d] %(message)s', datefmt='%a, %d %b %Y %H:%M:%S')
    sh.setFormatter(formatter)
    logger.addHandler(sh)

    parser = argparse.ArgumentParser(
                    prog='ddprelay.py',
                    description='Forward raw frames (eg. ffmpeg rawvideo/UDP) using DDP protocol',
                    epilog='Made with \u2665 in Python')
    
    parser.add_argument('-v','--verbose',action='count',default=0,help='Verbose level (on stderr): WARN,INFO,DEBUG')
    parser.add_argument('-W','--width',type=int,default=16,help='Frame width in pixels')
    parser.add_argument('-H','--height',type=int,default=16,help='Frame height in pixels')
    parser.add_argument('-d','--destination',default=['127.0.0.1'],action='extend',nargs='+',help='IP destination address (default 127.0.0.1). Multiple unicast adresses can be provided.')
    parser.add_argument('-p','--port',type=int,default=4048,help='UDP destination port (default 4048)')
    parser.add_argument('-l','--listen-port',type=int,default=1234,help='UDP listen port (default 1234)')
    parser.add_argument('-r','--repeat',type=int,default=0,help='UDP packet repeat (default none)')
    parser.add_argument('-F','--frames',type=int,default=0,help='Number of frames to forward before exit (infinite by default)')
    parser.add_argument('-s','--show',action='count',default=0,help='Show frames (on stdout)')
    parser.add_argument('-b','--box',action='count',default=0,help='Use boxes instead of dots when showing frames')

    args = parser.parse_args()
    
    if args.verbose == 1:
        logger.setLevel(logging.WARNING)
    elif args.verbose == 2:
        logger.setLevel(logging.INFO)
    elif args.verbose > 2:
        logger.setLevel(logging.DEBUG)

    if(len(args.destination) == 1):
        device = DDPdevice(args.width, args.height, args.destination[0], args.port,logger=logger)
    else:
        device = DDPdevice(args.width, args.height, args.destination[1], args.port,logger=logger)
        for i in range(len(args.destination) - 2):
            device.adddestination(args.destination[i + 2], args.port )


    # Open UDP socket for receiving raw data
    udpserver = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)      # UDP

    ## udpserver.settimeout(None)
    udpserver.bind(('127.0.0.1', args.listen_port))

    # Calculate framesize (in bytes)
    framesize = args.width * args.height * 3

    # Precompute erase frame pattern
    erase_frame  = (CURSOR_UP_ONE + ERASE_LINE) * args.height

    # number of frames to forward
    nframes = args.frames

    # used for spining indicator
    i = 0

    # Forever loop
    while True:

        nframes -= 1   # with loop set to 0 from start it results in infinite loop

        if args.show == 1:
            sys.stdout.write(erase_frame)
            sys.stdout.write(str(device))
            sys.stdout.flush()
        else:
            sys.stdout.write('\rSending frames %s' % INDICATOR[i  % len(INDICATOR)])

        i = (i + 1)

        frame = b''

        # Receive all the udp payload for the current frame
        # UDP is not reliable so it should only works on localhost
        # In the case the video must be received over the network
        # you should move the artnetrelay node so that artnet protocol
        # is used over the network or you may use an ffmpeg chaining
        # like this:
        # ffmpeg -> RTP or MPEGTS over network -> ffmpeg -> UDP raw
        while len(frame) < framesize:
            frame += udpserver.recvfrom(1500)[0]

        if len(frame) != framesize:
            logger.warning('%d bytes received, expecting %d bytes' % (len(frame), framesize))
        
        logger.info('Received frame %d (%d bytes)' % (i, len(frame)))

        device.setrawframe(frame)

        # Stop when the number of frames has been processed 
        # Note: infinite frames will never branch in here (nframes < 0)
        if nframes == 0:
            logger.info('%d frames have been processed, exiting' % args.frames)
            break

if __name__ == '__main__':
    main()