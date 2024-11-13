from pbr.version import VersionInfo
import argparse
from urllib.parse import urlparse
import sys
import pyiotown.get
import pyiotown.post
import paho.mqtt.client as mqtt
import ssl
import json
import threading
import aiohttp
import asyncio
import random
import base64
import hashlib
import os
import time
import datetime

MESSAGE_TYPE_SEND = 0
MESSAGE_TYPE_MD5 = 1
MESSAGE_TYPE_FWUPDATE = 2
MESSAGE_TYPE_DELETE = 3
MESSAGE_TYPE_COPY = 4

RESULT_OK = 0
RESULT_ERROR_INVALID_SESSION_ID = 1
RESULT_ERROR_DUPLICATE_MESSAGE = 2
RESULT_ERROR_INVALID_FORMAT = 3
RESULT_ERROR_FAIL = 255

state = {
}

def on_connect(client, userdata, flags, reason_code, properties):
  if reason_code.is_failure:
    print(f"Bad connection (reason: {reason_code.getName()})", file=sys.stderr)
    sys.exit(3)
  else:
    print(f"Connect OK! Subscribe Start")

def percentage(key):
  total_size = os.fstat(state[key]['image'].fileno()).st_size
  current_pos = state[key]['image'].tell()
  return current_pos / total_size * 100

def TAG(key):
  return f"{datetime.datetime.now():%Y-%m-%d %H:%M:%S} {key} {percentage(key):.2f}%"

async def periodic_check_downlink_status(key):
  group, device = key.split(':')
  my_fcnt = state[key]['f_cnt']
  my_seq = state[key]['seq']
  
  while my_fcnt == state[key]['f_cnt'] and my_seq == state[key]['seq']:
    try:
      success, response = await pyiotown.get.async_command(http_url,
                                                           state[key]['token'],
                                                           device,
                                                           group_id=group,
                                                           verify=False)
    except Exception as e:
      print(e)
      continue
    sent = True
    for c in response['command']:
      if c.get('fCnt') == my_fcnt:
        sent = False
        break
    print(f"[{TAG(key)}] downlink status for fCnt '{my_fcnt}', seq '{my_seq}': {response} => {'sent' if sent else 'not sent'}")
    if sent:
      break
    else:
      await asyncio.sleep(1)
      continue

  print(f"[{TAG(key)}] wait for ack...")
    
  while state[key]['f_cnt'] == my_fcnt:
    await asyncio.sleep(0.1)

  if state[key]['f_cnt'] == 'no ack':
    post_command(group, device, state[key]['last_message'])
    print(f"[{TAG(key)}] no ack received - re-send the last message")
  elif state[key]['f_cnt'] == 'ack':
    if state[key]['last_message'][0] == MESSAGE_TYPE_FWUPDATE:
      return # no need to wait for the answer.
    print(f"[{TAG(key)}] ack received - wait for the answer")
  elif state[key] != my_fcnt:
    print(f"[{TAG(key)}] cancel FCnt {my_fcnt}")
    return

  time_start = time.time()
  time_now = time.time()
  while time_now < time_start + 10:
    if state[key]['seq'] == my_seq:
      await asyncio.sleep(0.1)
      time_now = time.time()
    else:
      print(f"[{TAG(key)}] got answer '{my_seq}'")
      return

  print(f"[{TAG(key)}] answer wait timeout - re-send the last message '{state[key]['seq']}'")
  post_command(group, device, state[key]['last_message'])

def on_command_posted(future):
  if future.exception() is None:
    for key in state.keys():
      if state[key]['future'] == future:
        result = future.result()
        print(f"[{TAG(key)}] posting command result:", result)
        state[key]['future'] = None
        message = result[1]
        print(message)
        if result[0] == False or message.get('fCnt') is None:
          print(f"[{TAG(key)}] command API fail, offset:{state[key]['image'].tell()}")
          
          group, device = key.split(':')
          post_command(group, device, state[key]['last_message'])
          return
        
        state[key]['f_cnt'] = message['fCnt']
        asyncio.run_coroutine_threadsafe(periodic_check_downlink_status(key), event_loop)
        return
  else:
    print(f"Future({future}) exception:", future.exception())

def post_command(group, device, message):
  key = f"{group}:{device}"
  state[key]['last_message'] = bytearray(message)
  state[key]['f_cnt'] = None
  future = asyncio.run_coroutine_threadsafe(pyiotown.post.async_command(http_url,
                                                                        state[key]['token'],
                                                                        device,
                                                                        bytes(message),
                                                                        {
                                                                          'f_port': 67,
                                                                          'confirmed': True
                                                                        },
                                                                        group_id=group,
                                                                        verify=False), event_loop)
  state[key]['future'] = future
  future.add_done_callback(on_command_posted)
  return future
  
def request_md5_request(group, device):
  key = f"{group}:{device}"
  request = bytes([MESSAGE_TYPE_MD5, state[key]['seq'], state[key]['session']])
  future = post_command(group, device, request)
  print(f"[{TAG(key)}] Try to request MD5 (future:{future})")
  
def request_send_data(group, device, size=50):
  key = f"{group}:{device}"
  request = bytearray([MESSAGE_TYPE_SEND, state[key]['seq'], state[key]['session']])
  offset = state[key]['image'].tell()
  request += offset.to_bytes(3, byteorder='little', signed=False)
  data = state[key]['image'].read(size)

  if len(data) > 0:
    request += data
    future = post_command(group, device, request)
    print(f"[{TAG(key)}] Try to send {size} bytes from offset {offset} (future:{future})")
  else:
    print(f"[{TAG(key)}] EOF")
    request_md5_request(group, device)

def request_firmware_update(group, device):
  key = f"{group}:{device}"
  request = bytes([MESSAGE_TYPE_FWUPDATE, state[key]['seq'], state[key]['session']])
  state[key]['last_message'] = bytearray(request)
  future = post_command(group, device, request)
  print(f"[{TAG(key)}] Try to request firmware update (future:{future})")

def request_delete_data(group, device):
  key = f"{group}:{device}"
  request = bytes([MESSAGE_TYPE_DELETE, state[key]['seq'], state[key]['session']])
  state[key]['last_message'] = bytearray(request)
  future = post_command(group, device, request)
  print(f"[{TAG(key)}] Try to request delete (future:{future})")

def on_message(client, userdata, message):
  try:
    m = json.loads(message.payload.decode('utf-8'))
  except Exception as e:
    print(e, file=sys.stderr)
    return

  topic_blocks = message.topic.split('/')
  
  group_id = topic_blocks[2]
  device = topic_blocks[4]
  key = f"{group_id}:{device}"
  if state.get(key) is None:
    return

  message_type = topic_blocks[5]

  # print(message.topic, m)
  if message_type == 'boot':
    print(message.topic, m)
  elif message_type == 'ack':
    # print(message.topic, m)
    if state[key]['f_cnt'] == m['fCnt']:
      state[key]['f_cnt'] = None
      if m['errorMsg'] == '':
        state[key]['f_cnt'] = 'ack'
        if state[key]['last_message'][0] == MESSAGE_TYPE_FWUPDATE:
          print(f"[{TAG(key)}] Firmware update request is sent. Check the device.")
          sys.exit(0)
      else:
        if m['errorMsg'] == 'Oversized Payload':
          dec_size = 1
          state[key]['chunk_size'] -= dec_size
          print(f"[{TAG(key)}] Over sized payload -> Decreased chunk_size to {state[key]['chunk_size']}")
          if state[key]['chunk_size'] <= 0:
            sys.exit(5)

          state[key]['image'].seek(-dec_size, os.SEEK_CUR)
          state[key]['seq'] = (state[key]['seq'] + 1) & 0xFF
          message_with_new_seq = bytearray(state[key]['last_message'])
          message_with_new_seq[1] = state[key]['seq']
          post_command(group_id, device, message_with_new_seq[:-dec_size])
        elif m['errorMsg'] == 'No ACK':
          state[key]['f_cnt'] = 'no ack'
        else:
          print(f"[{TAG(key)}] unhandled error: {m['errorMsg']}")
          sys.exit(6)
  elif message_type == 'data':
    if m.get('data') is not None and m['data'].get('fPort') == 67:
      # print(message.topic, m)
      try:
        raw = base64.b64decode(m['data']['raw'])
      except Exception as e:
        print(e)
        print(f"Invalid or no raw data:\n\t{m}\n\t{m['data'].get('raw')}")
        return

      print(f"[{TAG(key)}] Answer {raw.hex()}")
      if len(raw) < 4:
        return
      answer_type = raw[0]
      answer_seq = raw[1]
      answer_session = raw[2]
      answer_result = raw[3]

      if answer_seq != state[key]['seq']:
        print(f"[{TAG(key)}] not my seq (expected {state[key]['seq']} but {answer_seq})")
        return

      state[key]['seq'] = (state[key]['seq'] + 1) & 0xFF

      if answer_type == MESSAGE_TYPE_SEND:
        if answer_result in [ RESULT_OK, RESULT_ERROR_DUPLICATE_MESSAGE ]:
          total_size = os.fstat(state[key]['image'].fileno()).st_size
          current_pos = state[key]['image'].tell()
          print(f"[{TAG(key)}] send data success. ({current_pos}/{total_size})")
          request_send_data(group_id, device, state[key]['chunk_size'])
        else:
          print(f"[{TAG(key)}] send data fail returned: {answer_result}, offset:{state[key]['image'].tell()}")
          message_with_new_seq = bytearray(state[key]['last_message'])
          message_with_new_seq[1] = state[key]['seq']
          post_command(group_id, device, message_with_new_seq)

      elif answer_type == MESSAGE_TYPE_DELETE:
        if answer_result == RESULT_OK:
          request_send_data(group_id, device, state[key]['chunk_size'])
        else:
          print(f"[{TAG(key)}] delete fail returned: {answer_result}, offset:{state[key]['image'].tell()}")
          sys.exit(2)

      elif answer_type == MESSAGE_TYPE_MD5:
        if answer_result == RESULT_OK:
          if len(raw) != 20:
            print(f"[{TAG(key)}] MD5 response must be 20 byte but {len(raw)}")
          else:
            md5_response = raw[4:]

            state[key]['image'].seek(0)
            md5 = hashlib.md5()
            for chunk in iter(lambda: state[key]['image'].read(2048), b''):
              md5.update(chunk)
            md5_expected = md5.digest()
            if md5_response == md5_expected:
              print(f"[{TAG(key)}] MD5 matched: {md5_expected.hex()}")
              request_firmware_update(group_id, device)
            else:
              print(f"[{TAG(key)}] MD5 {md5_expected.hex()} expected but {md5_response.hex()}")
        else:
          print(f"[{TAG(key)}] MD5 fail returned: {answer_result}")
      elif answer_type == MESSAGE_TYPE_FWUPDATE:
        print(f"[{TAG(key)}] firmware update response: {answer_result}")
        state[key]['seq'] = -1
        sys.exit(0)

def main():
  parser = argparse.ArgumentParser(description=f"Nalja Firmware Update Over The Air (FUOTA) tool for devices in IOTOWN {VersionInfo('nola_tools').release_string()}")
  parser.add_argument('iotown', help='An IOTOWN MQTT URL to connect (e.g., mqtts://{username}:{token}@town.coxlab.kr)')
  parser.add_argument('group', help='A group ID you belong to')
  parser.add_argument('device', help='A device ID to update its firmware')
  parser.add_argument('image', type=argparse.FileType('rb'), nargs=1, help='A image file to flash (e.g., output.bin, ./build/test.bin, C:\Temp\hello.bin)', metavar='file')
  parser.add_argument('--region', help='A device-specific region name where the file is flashed on (e.g., main, bootloader, model, 0, 1, 2, ...)', metavar='region')
  parser.add_argument('--chunksize', help='The initial chunk size')
  parser.add_argument('--offset', help='The offset of the image. If it is set, the FUOTA will begin transmitting the image with the offset without initial remove.')
  args = parser.parse_args()
  
  url_parsed = urlparse(args.iotown)

  token = url_parsed.password
  if token is None:
    print("No token found in the URL", file=sys.stderr)
    return 1

  device = args.device
  username = url_parsed.username

  iotown_netloc = url_parsed.hostname

  client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
  client.on_connect = on_connect
  client.on_message = on_message

  client.username_pw_set(username, token)
  client.tls_set(cert_reqs=ssl.CERT_NONE)
  client.tls_insecure_set(True)
  client.connect(url_parsed.hostname, 8883 if url_parsed.port is None else url_parsed.port)

  global http_url
  http_url = url_parsed._replace(scheme='https', netloc=iotown_netloc).geturl()
  success, result = pyiotown.get.node(http_url, token, device, group_id=args.group, verify=False)

  if not success:
    print(f"Getting information of the device '{device}' failed: {result}", file=sys.stderr)
    return 1

  client.subscribe([(f"iotown/rx/{args.group}/device/{device}/ack", 2),
                    (f"iotown/rx/{args.group}/device/{device}/boot", 2),
                    (f"iotown/rx/{args.group}/device/{device}/data", 2)])

  global event_loop
  event_loop = asyncio.new_event_loop()

  seq = random.randrange(0, 256)

  key = f"{args.group}:{device}"
  state[key] = {
    'token': token,
    'seq': seq,
    'session': 0 if args.region is None else int(args.region),
    'image': args.image[0],
    'f_cnt': None,
    'chunk_size': 240 if args.chunksize is None else int(args.chunksize),
    'last_message': None
  }

  offset = 0
  try:
    offset = int(args.offset)
  except:
    pass

  if offset == 0:
    request_delete_data(args.group, device)
  else:
    state[key]['image'].seek(offset)
    request_send_data(args.group, device, state[key]['chunk_size'])
    
  def event_loop_thread(client):
    event_loop.run_forever()
  threading.Thread(target=event_loop_thread, args=[client], daemon=True).start()
  
  client.loop_forever()

if __name__ == "__main__":
  main()
