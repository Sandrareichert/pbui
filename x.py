!wget https://github.com/MrToffel/pyrxbuild/raw/main/pyrx-0.0.4-cp39-cp39m-linux_x86_64.whl
!pip install pyrx-0.0.4-cp39-cp39m-linux_x86_64.whl
#improved version of https://github.com/jtgrassie/monero-powpy

import socket
import binascii
import pyrx
import struct
import json
import sys
import time
from multiprocessing import Process, Queue
import os

#proxy
proxy_host = '87.179.179.150'
proxy_port = 443

tnum = 8
def main():
    proxy_ip = socket.gethostbyname(proxy_host)
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect((proxy_ip, proxy_port))
    
    qs = []
    
    for i in range(tnum):
        q=Queue()
        qs+=[q]
        time.sleep(0.1)
        proc = Process(target=worker, args=(q, s, i, tnum))
        proc.daemon = True
        proc.start()

    login = {
        'method': 'login',
        'params': {
            'rigid': '',
            'agent': 'stratum-miner-py/0.1'
        },
        'id':1
    }
    
    s.sendall(str(json.dumps(login)+'\n').encode('utf-8'))
    print('Logging into proxy: {}:{}'.format(proxy_host, proxy_port))
    time.sleep(1)
    try:
        while 1:
            line = s.makefile().readline()
            r = json.loads(line)
            error = r.get('error')
            result = r.get('result')
            params = r.get('params')
            method = r.get('method')
            if error:
                print('Error: {}'.format(error))
                continue
            if result and result.get('status'):
                print('Status: {}'.format(result.get('status')))
            if result and result.get('job'):
                login_id = result.get('id')
                job = result.get('job')
                job['login_id'] = login_id
                target = job.get('target')
                job_id = job.get('job_id')
                height = job.get('height')
                
                
                print('New job with target: {}, RandomX, height: {}'.format(target, height))
                for i in qs:
                    i.put(job)
                
            elif method and method == 'job' and len(login_id):
                height = params.get('height')
                target = params.get('target')
                
                print('New job with target: {}, RandomX, height: {}'.format(target, height))
                for i in qs:
                    i.put(params)
                
    except KeyboardInterrupt:
        s.close()
        sys.exit(0)


def pack_nonce(blob, nonce):
    b = binascii.unhexlify(blob)
    bin = struct.pack('39B', *bytearray(b[:39]))
    bin += struct.pack('I', nonce)
    bin += struct.pack('{}B'.format(len(b)-43), *bytearray(b[43:]))
    return bin


def worker(q, s, start, step):
    login_id=""
    time.sleep(5)
    hash_count = 0
    started = time.time()
    print(start," online!")
    while 1:
        if(q.empty()==True):
            time.sleep(0.1)
        job = q.get()
        if job.get('login_id'):
            login_id = job.get('login_id')
        blob = job.get('blob')
        target = job.get('target')
        height = job.get('height')
        job_id = job.get('job_id')
        block_major = int(blob[:2], 16)
        cnv = 0
        if block_major >= 7:
            cnv = block_major - 6
        
        seed_hash = binascii.unhexlify(job.get('seed_hash'))
        #print("T"+str(start)+": working on",target, " - ", height)
        target = struct.unpack('I', binascii.unhexlify(target))[0]
        if target >> 32 == 0:
            target = int(0xFFFFFFFFFFFFFFFF / int(0xFFFFFFFF / target))
        nonce = start
        while 1:
            if(not q.empty()):
                break
 
            bin = pack_nonce(blob, nonce)
            hash = pyrx.get_rx_hash(bin, seed_hash, height)
            
            hex_hash = binascii.hexlify(hash).decode()
            hash_count += 1
            
            r64 = struct.unpack('Q', hash[24:])[0]
            if r64 < target:
                elapsed = time.time() - started
                hr = int(hash_count / elapsed)
                print('{}Hashrate this core: {} H/s'.format(os.linesep, hr))
                submit = {
                    'method':'submit',
                    'params': {
                        'id': login_id,
                        'job_id': job_id,
                        'nonce': binascii.hexlify(struct.pack('<I', nonce)).decode(),
                        'result': hex_hash
                    },
                    'id':1
                }
                print("#Thread ",start," - Nonce: ",nonce,' - Submitting hash: {}'.format(hex_hash))
                s.sendall(str(json.dumps(submit)+'\n').encode('utf-8'))
                
                
            nonce += step

if __name__ == '__main__':
    main()
