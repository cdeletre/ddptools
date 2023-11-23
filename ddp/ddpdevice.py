from struct import pack, unpack     # Usefull to play with bytes
import socket                       # UDP
import logging, sys
from xterm256.rgbconvert import RGBconvert

class DDPdevice:

    class destination:
        def __init__(self, address, port):
            self.address = address
            self.port = port

        def __str__(self):
            return '%s:%d' % (self.address, self.port)

    PIXEL_BLACK = b'\x00\x00\x00'

    # DDP protocol
    # see http://www.3waylabs.com/ddp/#Protocol%20Operation
    # for details

    # DATATYPE
    DDP_RGBTYPE = 0x01                 # TTT=001 (RGB)
    DDP_PIXEL24 = 0x05                 # SSS=5 (24 bits/pixel)

    DDP_MAX_PIXELS = 480
    DDP_MAX_DATALEN = DDP_MAX_PIXELS * 3    # fits nicely in an ethernet packet

    # DDP HEADER
    # BYTE 0
    DDP_VER1 = 0x40                    # version 1 (01)
    DDP_PUSH = 0x01

    # BYTE 1
    # sequence number (4 bits number, MSB first)

    # BYTE 2 (C R TTT SSS)
    DDP_DATATYPE = ((DDP_RGBTYPE << 3) & 0xff) | DDP_PIXEL24

    # BYTE 3
    DDP_SOURCE = 0x01                  # default output device

    # BYTE 4-7
    # data offset in bytes (32-bit number, MSB first)

    # BYTE 4-7
    # data length in bytes (16-bit number, MSB first)

    # BYTE 10-13
    # timecode (if T flag)

    # BYTE 10+ or 14+
    # start of data

    def __init__(self, width=16, height=16, address='127.0.0.1', port=4048, repeat=0, autosend=True, logger=logging.getLogger('ddpdevice')):
        
        self.height = height
        self.width = width
        self.rawframes = [DDPdevice.blackframe(self.width,self.height)]
        self.rawframeindex = 0
        self.running = False
        self.sequence = 0
        self.autosend = autosend
        self.repeat = repeat
        self.logger = logger
        self.rgbconverter = RGBconvert()
        self.periodic = None

        destination =  DDPdevice.destination(address,port)
        self.destinations =  [destination]
        self.logger.info('Destination %s added' % destination)

        self.udpclient = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        if len(address.split('.')) == 4 and int(address.split('.')[3]) == 255:
            self.logger.info('Multicast option enabled')
            self.udpclient.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)   # Allow multicast
    
    def __str__(self):
        return self.rgbconverter.frame2ascii(self.rawframes[self.rawframeindex], self.width, self.height)

    def blackframe(width=16, height=16):
        return DDPdevice.PIXEL_BLACK * width * height
    
    def adddestination(self, address='127.0.0.1', port=4048):
        destination = DDPdevice.destination(address, port)
        self.destinations.append(destination)
        self.logger.info('Destination %s added' % destination)

    def addrawframe(self, rawframe):
        self.rawframes.append(rawframe)
    
    def setrawframe(self, rawframe, index=0):
        self.rawframes[index] = rawframe
        if self.autosend:
            self.sendframe(index)

    def sendnextframe(self):
        self.sendframe(self.rawframeindex)
        self.rawframeindex = (self.rawframeindex + 1) % len(self.rawframes)

    def sendframe(self, index=0):
        offset = 0
        remaining_bytes = len(self.rawframes[index])

        self.logger.info('Processing frame (%d bytes to send) sequence %d' % (remaining_bytes, self.sequence))

        # While data needs to be sent for the current frame
        while remaining_bytes > 0:
            # Prepare up to 480 RGB values to send 
            rgbvalues = self.rawframes[index][offset: offset + DDPdevice.DDP_MAX_DATALEN]

            # Build the DDP payload
            ddppayload = pack(
                        '!BBBBLH',
                        DDPdevice.DDP_VER1                              # BYTE 0
                        | (
                            DDPdevice.DDP_VER1
                            if (len(rgbvalues) == DDPdevice.DDP_MAX_DATALEN)
                            else DDPdevice.DDP_PUSH
                        ),
                        self.sequence,                                  # BYTE 1
                        DDPdevice.DDP_DATATYPE,                         # BYTE 2
                        DDPdevice.DDP_SOURCE,                           # BYTE 3
                        offset,                                         # BYTE 4-7
                        len(rgbvalues))                                 # BYTE 8-9
            ddppayload += rgbvalues                                     # BYTES 10+
            self.logger.debug(ddppayload)

            for _,destination in enumerate(self.destinations):
                # Send the ddp payload in UDP packet to destination
                self.logger.info('Sending DDP packet (%d bytes) to %s' % (len(ddppayload), destination))
                self.udpclient.sendto(ddppayload,(destination.address,destination.port))

                for repeat in range(self.repeat):
                    # Send the ddp payload in UDP packet to destination (repeat)
                    self.logger.info('Repeat sending DDP packet (%d bytes) to %s' % (len(ddppayload), destination))
                    self.udpclient.sendto(ddppayload,(destination.address,destination.port))

            remaining_bytes -= DDPdevice.DDP_MAX_DATALEN
            offset += DDPdevice.DDP_MAX_DATALEN

        self.sequence = (self.sequence + 1) % 0x10