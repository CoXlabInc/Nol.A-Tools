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

def on_command_posted(future):
  if future.exception() is None:
    for key in state.keys():
      if state[key]['future'] == future:
        result = future.result()
        print(f"[{key}] posting command result:", result)
        state[key]['future'] = None
        message = json.loads(result[1])
        if result[0] == False or message.get('fCnt') is None:
          print(f"[{key}] command API fail, offset:{state[key]['image'].tell()}")
          sys.exit(4)
        state[key]['f_cnt'] = message['fCnt']
        return
  else:
    print(f"Future({future}) exception:", future.exception())

def request_md5_request(group, device):
  key = f"{group}:{device}"
  request = bytearray([MESSAGE_TYPE_MD5, state[key]['seq'], state[key]['session']])
  future = asyncio.run_coroutine_threadsafe(pyiotown.post.async_command(http_url,
                                                                        state[key]['token'],
                                                                        device,
                                                                        bytes(request),
                                                                        {
                                                                          'f_port': 67,
                                                                          'confirmed': True
                                                                        },
                                                                        verify=False), event_loop)
  state[key]['future'] = future
  future.add_done_callback(on_command_posted)
  print(f"[{key}] Try to request MD5 (future:{future})")
  
def request_send_data(group, device, size=50):
  key = f"{group}:{device}"
  request = bytearray([MESSAGE_TYPE_SEND, state[key]['seq'], state[key]['session']])
  offset = state[key]['image'].tell()
  request += offset.to_bytes(3, byteorder='little', signed=False)
  data = state[key]['image'].read(size)

  if len(data) > 0:
    request += data
    state[key]['last_send_size'] = size

    future = asyncio.run_coroutine_threadsafe(pyiotown.post.async_command(http_url,
                                                                          state[key]['token'],
                                                                          device,
                                                                          bytes(request),
                                                                          {
                                                                            'f_port': 67,
                                                                            'confirmed': True
                                                                          },
                                                                          verify=False), event_loop)
    state[key]['future'] = future
    future.add_done_callback(on_command_posted)
    print(f"[{key}] Try to send {state[key]['last_send_size']} bytes from offset {offset} (future:{future})")
  else:
    print(f"[{key}] EOF")
    state[key]['last_send_data'] = 0
    request_md5_request(group, device)

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
  if message_type == 'ack':
    if state[key]['f_cnt'] == m['fCnt']:
      if m['errorMsg'] != '':
        print(f"[{key}] Error on LoRa: {m['errorMsg']}")
        if state[key].get('last_send_size') is not None:
          state[key]['image'].seek(-state[key]['last_send_size'], os.SEEK_CUR)
        offset = state[key]['image'].tell()
        if m['errorMsg'] == 'Oversized Payload':
          state[key]['chunk_size'] -= 10
          print(f"Decreased chunk_size to {state[key]['chunk_size']}")
          if state[key]['chunk_size'] <= 0:
            sys.exit(5)
            
          request_send_data(group_id, device, state[key]['chunk_size'])
        elif m['errorMsg'] == 'No ACK':
          request_send_data(group_id, device, state[key]['chunk_size'])
        else:
          print(f"[{key}] unhandled error")
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

      print(f"[{key}] Answer {raw.hex()}")
      if len(raw) < 4:
        return
      answer_type = raw[0]
      answer_seq = raw[1]
      answer_session = raw[2]
      answer_result = raw[3]

      if answer_seq != state[key]['seq']:
        print(f"not my seq (expected {state[key]['seq']} but {answer_seq})")
        return

      state[key]['seq'] = (state[key]['seq'] + 1) & 0xFF

      if answer_type == MESSAGE_TYPE_SEND:
        if answer_result in [ RESULT_OK, RESULT_ERROR_DUPLICATE_MESSAGE ]:
          total_size = os.fstat(state[key]['image'].fileno()).st_size
          current_pos = state[key]['image'].tell()
          print(f"[{key}] send data success. {current_pos}/{total_size}={current_pos / total_size * 100:.2f}%")
        else:
          print(f"[{key}] send data fail returned: {answer_result}, offset:{state[key]['image'].tell()}")
          if state[key].get('last_send_size') is not None:
            state[key]['image'].seek(-state[key]['last_send_size'], os.SEEK_CUR)
        request_send_data(group_id, device, state[key]['chunk_size'])
      elif answer_type == MESSAGE_TYPE_DELETE:
        if answer_result == RESULT_OK:
          request_send_data(group_id, device, 300)
        else:
          print(f"[{key}] delete fail returned: {answer_result}, offset:{state[key]['image'].tell()}")
          sys.exit(2)
      elif answer_type == MESSAGE_TYPE_MD5:
        if answer_result == RESULT_OK:
          if len(raw) != 20:
            print(f"[{key}] MD5 response must be 20 byte but {len(raw)}")
          else:
            md5_response = raw[4:]
            print(f"[{key}] MD5 response {md5_response.hex()}")

            state[key]['image'].seek(0)
            md5 = hashlib.md5()
            for chunk in iter(lambda: state[key]['image'].read(2048), b''):
              # update the hash object
              md5.update(chunk)
            md5_expected = md5.hexdigest()
            print(f"[{key}] MD5 expected: {md5_expected}")
        else:
          print(f"[{key}] MD5 fail returned: {answer_result}")
        
def main():
  parser = argparse.ArgumentParser(description=f"Nalja Firmware Update Over The Air (FUOTA) tool for devices in IOTOWN {VersionInfo('nola_tools').release_string()}")
  parser.add_argument('iotown', help='An IOTOWN MQTT URL to connect (e.g., mqtts://{username}:{token}@town.coxlab.kr)')
  parser.add_argument('group', help='A group ID you belong to')
  parser.add_argument('device', help='A device ID to update its firmware')
  parser.add_argument('image', type=argparse.FileType('rb'), nargs=1, help='A image file to flash (e.g., output.bin, ./build/test.bin, C:\Temp\hello.bin)', metavar='file')
  parser.add_argument('--region', help='A device-specific region name where the file is flashed on (e.g., main, bootloader, model, 0, 1, 2, ...)', metavar='region')
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
  try:
    result = pyiotown.get.node(http_url, token, device, verify=False)
  except:
    print(f"Getting information of the device '{device}' failed", file=sys.stderr)
    return 1

  client.subscribe([(f"iotown/rx/{args.group}/device/{device}/ack", 2),
                    (f"iotown/rx/{args.group}/device/{device}/data", 2)])

  def message_loop(client):
    client.loop_forever()
  message_thread = threading.Thread(target=message_loop, args=[client])
  message_thread.start()

  global event_loop
  event_loop = asyncio.new_event_loop()

  seq = random.randrange(0, 256)

  key = f"{args.group}:{device}"
  state[key] = {
    'token': token,
    'seq': seq,
    'session': 0 if args.region is None else int(args.region),
    'image': args.image[0],
    'f_cnt': -1,
    'chunk_size': 200
  }
  
  command = bytes([ MESSAGE_TYPE_DELETE, seq, 0x00 ])
  lorawan_param = {
    'f_port': 67,
    'confirmed': True
  }

  future = asyncio.run_coroutine_threadsafe(pyiotown.post.async_command(http_url,
                                                                        token,
                                                                        device,
                                                                        command,
                                                                        lorawan_param,
                                                                        verify=False), event_loop)
  state[key]['future'] = future
  print(f"[{key}] Initiating by requesting delete session '{state[key]['session']}' ({future})")

  future.add_done_callback(on_command_posted)
  event_loop.run_forever()
  
if __name__ == "__main__":
  main()
