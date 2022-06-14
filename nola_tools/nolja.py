import sys
import time
import serial
import binascii

def receiveMessage(ser):
    garbage = bytearray(b'')
    while True:
        r = ser.read(1)
        if len(r) == 0:
            print(f"No start delimeter: {garbage}", file=sys.stderr)
            return None
        elif r[0] == 0x80: # start message delimeter
            break
        garbage.append(r[0])
            

    r = ser.read(2)
    if len(r) != 2:
        if ser.in_waiting > 0:
            r += ser.read(ser.in_waiting)
        print(f"Invalid length field: {r}", file=sys.stderr)
        return None

    length = (r[0] << 0) + (r[1] << 8)
    message = ser.read(length)
    if len(message) != length:
        if ser.in_waiting > 0:
            r += ser.read(ser.in_waiting)
        print(f"Invalid length: {length} byte expected, but {len(message)} byte received. [{r}]", file=sys.stderr)
        return None

    r = ser.read(2)
    if len(r) != 2:
        if ser.in_waiting > 0:
            r += ser.read(ser.in_waiting)
        print(f"No CRC: {r}", file=sys.stderr)
        return None

    crc_received = r[0] + (r[1] << 8)
    crc_calculated = binascii.crc_hqx(message, 0xffff)

    if crc_calculated != crc_received:
        print(f"CRC error: 0x{crc_calculated:x} expected but 0x{crc_received}", file=sys.stderr)
        return None
    else:
        return message

def sendMessage(ser, data, waitTime):
    msg = bytearray(b'\x80')
    msg.append((len(data) >> 0) & 0xFF)
    msg.append((len(data) >> 8) & 0xFF)
    msg += data
    crc = binascii.crc_hqx(data, 0xffff)
    msg.append((crc >> 0) & 0xFF)
    msg.append((crc >> 8) & 0xFF)
    ser.reset_input_buffer()
    ser.timeout = waitTime
    ser.write(msg)
    ser.flush()
    r = ser.read(1)
    if r[0] == 0x00:  #ack
        return receiveMessage(ser)
    else:
        print(f"No ack: {r}", file=sys.stderr)
        return None

def sendMassErase(ser):
   msg = bytearray(b'\x15')
   resp = sendMessage(ser, msg, 1)
   if resp == b'\x3B\x00':
       print("Mass erase done")
       return True
   else:
       return False

def sendDataBlock(ser, addr, data):
    msg = bytearray(b'\x10')
    msg.append((addr >> 0) & 0xFF)
    msg.append((addr >> 8) & 0xFF)
    msg.append((addr >> 16) & 0xFF)
    msg += data
    resp = sendMessage(ser, msg, 1)
    #print(f'sendDataBlock {resp} (size:{4+len(data)})')
    if resp == b'\x3B\x00':
        return True
    else:
        return False

def sendCRCCheck(ser, addr, length):
    msg = bytearray(b'\x16')
    msg.append((addr >> 0) & 0xFF)
    msg.append((addr >> 8) & 0xFF)
    msg.append((addr >> 16) & 0xFF)
    msg.append((length >> 0) & 0xFF)
    msg.append((length >> 8) & 0xFF)
    msg.append((length >> 16) & 0xFF)
    resp = sendMessage(ser, msg, 10)
    #print(f'sendCRCCheck {resp}')
    if resp is not None and len(resp) == 3 and resp[0] == 0x3A:
        return resp[1] + (resp[2] << 8)
    else:
        return None

def sendReset(ser):
    msg = bytearray(b'\x17')
    resp = sendMessage(ser, msg, 3)
    #print('sendReset<', ' '.join("%02x" % b for b in resp))
    if resp == b'\x3B\x00':
        return True
    else:
        return False

def printUsage():
    print('* Usage: %s {serial port} {binary file}' % sys.argv[0])

def main():
    print('Nol.ja flasher version 0.6 for Nol.A supported boards.')

    if len(sys.argv) != 3:
        printUsage()
        return 3

    try:
        ser = serial.Serial(port=sys.argv[1],
                            baudrate=115200,
                            parity=serial.PARITY_NONE,
                            stopbits=serial.STOPBITS_ONE,
                            bytesize=serial.EIGHTBITS,
                            timeout=2)
    except serial.SerialException:
        print('* Cannot open port.', file=sys.stderr)
        printUsage()
        return 1

    try:
        f = open(sys.argv[2], 'rb')
        image = f.read()
        f.close()
    except IOError:
        print('* Cannot open file.', file=sys.stderr)
        printUsage()
        return 2

    print('Erasing...')
    if sendMassErase(ser) == False:
        print("* Mass erase failed", file=sys.stderr)
        return 3

    addr = 0
    printed = 0

    while True:
        block = image[addr : min(addr+256, len(image))]

        if sendDataBlock(ser, addr, block) == False:
            print('* Communication Error', file=sys.stderr)
            return 4

        addr += len(block)

        while printed > 0:
            print(' ', end='')
            printed -= 1
            print(end='\r')

        p = 'Flashing: %.2f %% (%u / %u)' % (addr * 100. / len(image), addr, len(image))
        printed = len(p)
        print(p, end='\r', flush=True)

        if addr >= len(image):
            break

    print('\nFlashing done')

    devCrc = sendCRCCheck(ser, 0, len(image))
    myCrc = binascii.crc_hqx(image, 0xFFFF)

    if myCrc != devCrc:
        print('Integrity check failed.', file=sys.stderr)
        print('CRC:0x%04x expected, but 0x%04x' % (myCrc, devCrc), file=sys.stderr)
        return 5

    print('Integrity check passed.')

    if sendReset(ser) == True:
        ser.close()
        return 0
    else:
        print('Reset error', file=sys.stderr)
        ser.close()
        return 6
