import sys
import serial
import binascii
import argparse
from pbr.version import VersionInfo

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

def sendGetEui64(ser):
    msg = bytearray(b'\x1c')
    resp = sendMessage(ser, msg, 1)
    if resp is not None and len(resp) == 9 and resp[0] == 0x3A:
        return resp[1:]
    else:
        return None
    
def sendMassErase(ser):
    msg = bytearray(b'\x15')
    resp = sendMessage(ser, msg, 1)
    if resp == b'\x3B\x00':
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

def sendReset(ser, eui=None):
    msg = bytearray(b'\x17')
    if eui is not None:
        msg += eui
    resp = sendMessage(ser, msg, 3)
    #print('sendReset<', ' '.join("%02x" % b for b in resp))
    if resp == b'\x3B\x00':
        return True
    else:
        return False

def main():
    parser = argparse.ArgumentParser(description=f"Nol.ja flasher for boards supported by Nol.A version {VersionInfo('nola_tools').release_string()}")
    parser.add_argument('serial', nargs='?', help='A serial port connected with the board to be flashed (e.g., /dev/ttyUSB0, COM3, ...)')
    parser.add_argument('--flash', type=argparse.FileType('rb'), nargs=1, help='A binary file to flash (e.g., output.bin, ./build/test.bin, C:\Temp\hello.bin)', metavar='bin file')
    parser.add_argument('--eui', nargs=1, help='Set the new EUI-64. The EUI-64 must be a 64-bit hexadecimal string. (e.g., 0011223344556677)', metavar='EUI-64')
    args = parser.parse_args()

    if args.serial == None:
        print('* A serial port must be specified.', file=sys.stderr)
        parser.print_help()
        return 1
    
    if args.eui is not None:
        new_eui = bytearray.fromhex(args.eui[0])
        if len(new_eui) != 8:
            print('* Invalid EUI-64.', file=sys.stderr)
            return 1
    else:
        new_eui = None    

    try:
        ser = serial.Serial(port=args.serial,
                            baudrate=115200,
                            parity=serial.PARITY_NONE,
                            stopbits=serial.STOPBITS_ONE,
                            bytesize=serial.EIGHTBITS,
                            timeout=2)
    except serial.SerialException as e:
        print(f'* Cannot open port: {e}', file=sys.stderr)
        parser.print_help()
        return 1

    eui = sendGetEui64(ser)
    if eui == None:
        print("* Getting EUI-64 failed", file=sys.stderr)
        return 2
    
    print(f"* EUI-64: {eui[0]:02X}-{eui[1]:02X}-{eui[2]:02X}-{eui[3]:02X}-{eui[4]:02X}-{eui[5]:02X}-{eui[6]:02X}-{eui[7]:02X}")

    if args.flash != None:
        image = args.flash[0].read()

        print('* Mass erasing...')
        if sendMassErase(ser) == False:
            print(" Mass erase failed", file=sys.stderr)
            return 3
        print("  Mass erase done")

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

            p = '* Flashing: %.2f %% (%u / %u)' % (addr * 100. / len(image), addr, len(image))
            printed = len(p)
            print(p, end='\r', flush=True)

            if addr >= len(image):
                break

        print('\n  Flashing done')

        devCrc = sendCRCCheck(ser, 0, len(image))
        myCrc = binascii.crc_hqx(image, 0xFFFF)

        if myCrc != devCrc:
            print('* Integrity check failed.', file=sys.stderr)
            print('  CRC:0x%04x expected, but 0x%04x' % (myCrc, devCrc), file=sys.stderr)
            return 5

        print('* Integrity check passed.')

    if args.flash != None or new_eui is not None:
        if new_eui == None:
            print('* Resetting...')
            result = sendReset(ser)
        else:
            print(f'* Resetting with new EUI-64 {new_eui[0]:02X}-{new_eui[1]:02X}-{new_eui[2]:02X}-{new_eui[3]:02X}-{new_eui[4]:02X}-{new_eui[5]:02X}-{new_eui[6]:02X}-{new_eui[7]:02X} ...')
            result = sendReset(ser, new_eui)

        if result == True:
            print('  Reset done')
        else:
            print('  Reset error', file=sys.stderr)
            return 6
            
    ser.close()
    return 0


if __name__ == "__main__":
    main()

