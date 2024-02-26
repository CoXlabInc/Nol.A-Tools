import sys
import serial
import binascii
import argparse
from pbr.version import VersionInfo
import json
import getpass
import base64
import time
import math
import hashlib

def receiveMessage():
    if format != 'bootloader':
        return None
    
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

def sendMessage(data, waitTime):
    if format == 'bootloader':
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
        if len(r) > 0 and r[0] == 0x00:  #ack
            return receiveMessage(ser)
        else:
            print(f"No ack: {r}", file=sys.stderr)
            return None
    elif format == 'json':
        global password
        if len(password) > 0:
            data = f"{password} {data}"
        ser.reset_input_buffer()
        ser.timeout = waitTime
        ser.write(data.encode('ascii'))
        ser.flush()
        while True:
            r = ser.readline()
            if len(r) > 0:
                try:
                    message = json.loads(r)
                    break
                except:
                    continue
            else:
                return None

        result = message.get('result')
        if result == 'OK':
            return message
        elif result == 'not authorized' and len(password) == 0:
            password = getpass.getpass()
            return message
        else:
            return message
    return None
        
def sendGetEui64():
    if format == 'bootloader':
        msg = bytearray(b'\x1c')
        resp = sendMessage(msg, 1)
        if resp is not None and len(resp) == 9 and resp[0] == 0x3A:
            return resp[1:]
        else:
            return None
    elif format == 'json':
        msg = 'get deveui\r\n'
        resp = sendMessage(msg, 1)

        try:
            return bytes.fromhex(resp.get('deveui'))
        except:
            return None
        
def sendMassErase(name=None):
    if format == 'bootloader':
        msg = bytearray(b'\x15')
        resp = sendMessage(msg, 1)
        if resp == b'\x3B\x00':
            return True
        else:
            return False
    elif format == 'json' and name is not None:
        msg = f'delfile fw/{name}\r\n'
        resp = sendMessage(msg, 2)
        if resp is not None and resp.get('command') == msg[:-2] and resp.get('result') == 'OK':
            return True
        else:
            print(f"* resp:{resp}")
            return False
    return False

def sendDataBlock(addr, data, name=None):
    if format == 'bootloader':
        msg = bytearray(b'\x10')
        msg.append((addr >> 0) & 0xFF)
        msg.append((addr >> 8) & 0xFF)
        msg.append((addr >> 16) & 0xFF)
        msg += data
        resp = sendMessage(msg, 1)
        #print(f'sendDataBlock {resp} (size:{4+len(data)})')
        if resp == b'\x3B\x00':
            return True
        else:
            return False
    elif format == 'json':
        if name is None:
            return False
        data_encoded = base64.b64encode(data).decode('ascii')
        msg = f"savefile fw/{name} {addr} {data_encoded}\r\n"
        resp = sendMessage(msg, 5)
        if resp is None:
            print(f"\n  Sending data block failed (no response)", file=sys.stderr)
            return False
        elif resp.get('command') != msg[:-2]:
            print(f"\n  Sending data block failed (data mismatch)", file=sys.stderr)
            return False
        elif resp.get('result') != 'OK':
            raise Exception(f"Sending data block failed ({resp.get('result')})")
        return True
    return False

def sendCRCCheck(addr, length):
    msg = bytearray(b'\x16')
    msg.append((addr >> 0) & 0xFF)
    msg.append((addr >> 8) & 0xFF)
    msg.append((addr >> 16) & 0xFF)
    msg.append((length >> 0) & 0xFF)
    msg.append((length >> 8) & 0xFF)
    msg.append((length >> 16) & 0xFF)
    resp = sendMessage(msg, 10)
    #print(f'sendCRCCheck {resp}')
    if resp is not None and len(resp) == 3 and resp[0] == 0x3A:
        return resp[1] + (resp[2] << 8)
    else:
        return None

def sendMD5Check(name):
    msg = f"md5 fw/{name}\r\n"
    resp = sendMessage(msg, 10)
    if resp is None:
        print("* MD5 no response")
        return None
    elif resp.get('result') != 'OK' or resp.get('command') != msg[:-2]:
        print(f"* MD5 response failed: {resp}")
        return None
    else:
        return resp.get('md5')

def sendReset(eui=None, name=None):
    if format == 'bootloader':
        msg = bytearray(b'\x17')
        if eui is not None:
            msg += eui
        resp = sendMessage(msg, 3)
        #print('sendReset<', ' '.join("%02x" % b for b in resp))
        if resp == b'\x3B\x00':
            return True
        else:
            return False
    elif format == 'json':
        if eui is not None:
            msg = f'set deveui {eui.hex()}\r\n'
            resp = sendMessage(msg, 3)
            if resp is None or resp.get('result') != 'OK':
                print(f"  Setting with the New EUI-64 failed ({resp.get('result')})", file=sys.stderr)
                return False

        if name is None:
            msg = f"reboot\r\n"
        else:
            msg = f"fwupdate {name}\r\n"
        resp = sendMessage(msg, 20)
        if resp is None or resp.get('result') != 'OK':
            print(f"  Invoking reboot failed ({resp.get('result')})", file=sys.stderr)
            return False
        return True
    return False

def main():
    parser = argparse.ArgumentParser(description=f"Nol.ja flasher for boards supported by Nol.A version {VersionInfo('nola_tools').release_string()}")
    parser.add_argument('serial', nargs='?', help='A serial port connected with the board to be flashed (e.g., /dev/ttyUSB0, COM3, ...)')
    parser.add_argument('--flash', type=argparse.FileType('rb'), nargs=1, help='A binary file to flash (e.g., output.bin, ./build/test.bin, C:\Temp\hello.bin)', metavar='file')
    parser.add_argument('--region', nargs=1, help='A region name where the file is flashed on (e.g., main, bootloader, model, ...)', metavar='region')
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

    global ser
    
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

    global format
    global password
    format = 'bootloader'
    password = ''

    eui = sendGetEui64()
    if eui == None:
        format = 'json'
        prev_password = password
        eui = sendGetEui64()
        if eui == None:
            if prev_password != password:
                eui = sendGetEui64() # try again with password
                if eui == None:
                    print("* Getting EUI-64 failed", file=sys.stderr)
                    return 2
            else:
                print("* Getting EUI-64 failed", file=sys.stderr)
                return 2
        else:
            print("* 'JSON' format detected")
    
    print(f"* EUI-64: {eui[0]:02X}-{eui[1]:02X}-{eui[2]:02X}-{eui[3]:02X}-{eui[4]:02X}-{eui[5]:02X}-{eui[6]:02X}-{eui[7]:02X}")

    if args.flash != None:
        image = args.flash[0].read()

        if format == 'bootloader':
            blocksize = 256
            print('* Mass erasing...')
            if sendMassErase() == False:
                print(" Mass erase failed", file=sys.stderr)
                return 3
            print("  Mass erase done")
        elif format == 'json':
            blocksize = 150
            num_fail = 0
            num_continuous_success = 0
            
            if args.region is not None:
                name = args.region[0]
            else:
                print(f"* The region name must be specified by using the '--region' option for the target.")
                return 1

            if sendMassErase(name) == False:
                print(" Delete existing file failed", file=sys.stderr)
                return 3

            md5 = hashlib.md5()

        addr = 0
        printed = 0

        time_start = time.time()

        while addr < len(image):
            block = image[addr : min(addr+blocksize, len(image))]

            try:
                time_now = time.time()
                p = f'\r* Flashing: {addr * 100. / len(image):.2f} %% ({addr} / {len(image)}, {addr / (time_now - time_start):.02f} bps, block size: {blocksize}, thr:{int(math.pow(2, num_fail))}, #s:{num_continuous_success})'
                printed = len(p) - 1
                print(p, end='', flush=True)
            except:
                printed = 0

            if sendDataBlock(addr, block, name) == False:
                if format == 'json':
                    num_fail += 1
                    num_continuous_success = 0
                    if blocksize > 10:
                        blocksize -= 1
                    continue
                else:
                    print('* Communication Error', file=sys.stderr)
                    return 4
            else:
                if format == 'json':
                    md5.update(block)
                    num_continuous_success += 1
                    if math.pow(2, num_fail) < num_continuous_success:
                        blocksize += 1

            addr += len(block)

            print(end='\r')
            while printed > 0:
                print(' ', end='')
                printed -= 1

        print(f'\n  Flashing done ({time_now - time_start} seconds)')

        if format == 'bootloader':
            devCrc = sendCRCCheck(0, len(image))
            myCrc = binascii.crc_hqx(image, 0xFFFF)

            if myCrc != devCrc:
                print('* Integrity check failed.', file=sys.stderr)
                print('  CRC:0x%04x expected, but 0x%04x' % (myCrc, devCrc), file=sys.stderr)
                return 5

            print('* Integrity check passed.')
        elif format == 'json':
            devMD5 = sendMD5Check(name)
            myMD5 = md5.hexdigest()
            if devMD5 != myMD5:
                print('* Integrity check failed.', file=sys.stderr)
                print(f'  MD5:{myMD5} expected, but {devMD5}')
                return 5

            print('* Integrity check passed.')

    if args.flash != None or new_eui is not None:
        if new_eui == None:
            print('* Resetting...')
        else:
            print(f'* Resetting with new EUI-64 {new_eui[0]:02X}-{new_eui[1]:02X}-{new_eui[2]:02X}-{new_eui[3]:02X}-{new_eui[4]:02X}-{new_eui[5]:02X}-{new_eui[6]:02X}-{new_eui[7]:02X} ...')

        if sendReset(new_eui, name):
            print('  Reset done')
        else:
            print('  Reset error', file=sys.stderr)
            return 6
            
    ser.close()
    return 0


if __name__ == "__main__":
    main()

