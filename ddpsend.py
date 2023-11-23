#!/usr/bin/env python3

import argparse                         # for the command line arguments
from ddp.ddpdevice import DDPdevice     # for DDP
import logging, sys
import time
from datetime import datetime       # get the current time (FPS calculation)


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
                    prog='ddpsend.py',
                    description='Send raw images using DDP protocol',
                    epilog='Made with \u2665 in Python')
    
    parser.add_argument('-v','--verbose',action='count',default=0,help='Verbose level (on stderr)')
    parser.add_argument('-W','--width',type=int,default=16,help='Frame width in pixels')
    parser.add_argument('-H','--height',type=int,default=16,help='Frame height in pixels')
    parser.add_argument('-d','--destination',default=['127.0.0.1'],action='extend',nargs='+',help='IP destination address (default 127.0.0.1). Multiple unicast adresses can be provided.')
    parser.add_argument('-p','--port',type=int,default=4048,help='UDP destination port (default 4048)')
    parser.add_argument('-f','--fps',type=int,default=5,help='Frame Per Second (default 5)')
    parser.add_argument('-r','--repeat',type=int,default=0,help='UDP packet repeat (default none)')
    parser.add_argument('-L','--loop',type=int,default=0,help='Number of loop to play (infinite loop by default)')
    parser.add_argument('-s','--show',action='count',default=0,help='Show frames (on stdout)')
    parser.add_argument('-b','--box',action='count',default=0,help='Use boxes instead of dots when showing frames')
    parser.add_argument('filepath',nargs='+',help='Raw image (rgb24) filepath')

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
    
    # load frames from files
    frames = []

    for filepath in args.filepath:
        with open(filepath,'rb') as file:
            
            # Load file content
            frame = file.read()

            # Append file content to frames table
            frames.append(frame)

    # Precompute erase frame pattern
    erase_frame  = (CURSOR_UP_ONE + ERASE_LINE) * args.height

    # use for spining indicator
    i = 0

    # number of loop of the frame to do
    loop = args.loop

    # Forever loop
    while True:

        loop -= 1   # with loop set to 0 from start it results in infinite loop

        # For each frame loaded in the frames table
        for f,frame in enumerate(frames):
            # Store start time (used for FPS)
            start = datetime.now()

            device.setrawframe(frame)
            logger.info('Processing frame %d' % f)
            if args.show > 0:
                sys.stdout.write(erase_frame)
                sys.stdout.write(str(device))
                sys.stdout.flush()
            else:
                sys.stdout.write('\rSending frames %s' % INDICATOR[i])
                i = (i + 1) % len(INDICATOR)

            # Evaluate the elapsed time since the computing has started
            # for the current frame
            duration = (datetime.now() - start).microseconds/1000000
            logger.info('Processing frame %d took %f second' % (f, duration))

            # Calculate the wait time needed to achieve the requested FPS
            wait = 1/int(args.fps) - duration
            logger.info('Will wait %f second' % wait)

            # If we're not to late we will need to wait
            if wait > 0:
                time.sleep(wait)

        # Stop when the number of loop has been done 
        # Note: infinite loop will never branch in here (loop < 0)
        if loop == 0:
            break

if __name__ == '__main__':
    main()