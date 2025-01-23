import asyncio
from os import system
import sys
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
import websockets
import logging
import colorlog
import struct
import time
import json
import argparse
import threading
import uvicorn
from fastapi.middleware.cors import CORSMiddleware

height = 600
width = 1000
board = {}
origins = []

class WebSocketServer:


    def __init__(self, host="localhost", port=2380,time_limit=30000):
        self.host = host
        self.port = port
        self.ping_time = 0
        self.ping_check = {}

        self.msg_data = {}
        self.total_size = {}
        self.msg_data[0] = []
        self.total_size[0] = 0

        self.token_used_time = {}
        self.time_limit = time_limit

        self.client_count = 1
        self.connected_clients = set()
        pass
    

    async def append_data(self,id, data):
        logging.debug("Append data, id: %d, len(data): %d", id, len(data))
        self.msg_data[id].append(data)
        self.total_size[id] += len(data)

    def get_merage_data(self,id):
        logging.debug("Get merage data, id: %d, len(chunks): %d", id, self.total_size[id])
        result = bytearray(self.total_size[id])
        i = 0
        for chunk in self.msg_data[id]:
            result[i:i + len(chunk)] = chunk
            i += len(chunk)
        self.total_size[id] = 0
        self.msg_data[id].clear()
        return result
    
    async def broadcast(self):
        while True:
            if self.total_size[0] > 0 and len(self.connected_clients) > 0:
                logging.debug("Send data to all clients,len(chunks): %d", len(self.msg_data[0]))
                for websocket in self.connected_clients:
                    try:
                        await websocket.send(self.get_merage_data(0))
                    except websockets.exceptions.ConnectionClosedError:
                        # 如果连接已关闭，从集合中移除该客户端
                        self.connected_clients.remove(websocket)
            await asyncio.sleep(0.2)

    async def ping(self):
        while True:
            if len(self.connected_clients) > 0:
                logging.debug("Send ping to all clients")
                for websocket in self.connected_clients:
                    self.ping_check[websocket] = 0
                asyncio.create_task(self.append_data(0,bytearray([0xfc])))
                self.ping_time = time.time()
            await asyncio.sleep(10)
    
    async def check_ping(self):
        while True:
            if len(self.connected_clients) > 0 and time.time() - self.ping_time > 3:
                for websocket in self.connected_clients:
                    if self.ping_check[websocket] == 0:
                        logging.warning("WebSocket %s ping timeout, close it", websocket)
                        await websocket.send("1001 Ping timeout".encode())
                        await websocket.close()
            await asyncio.sleep(2)
            
    
    def uint_to_bytes(self,uint,bytes):
        uint = int(uint)
        array = bytearray(bytes)

        for i in range(bytes):
            array[i] = uint & (0xff)
            uint >>= 8
        return array

    async def handle_connection(self, websocket):
        logging.info("One client connected, path: %s", websocket)
        self.connected_clients.add(websocket)
        client_id = self.client_count
        self.client_count += 1
        self.msg_data[client_id] = []
        self.total_size[client_id] = 0
        self.ping_check[websocket] = 1
        asyncio.create_task(self.send_data(websocket, client_id))

        async for message in websocket:
            logging.debug(f"Received message: {message}")
            ls = 0
            while ls < len(message):
                type = struct.unpack_from('B', message, ls)[0]
                ls += 1
                if type == 0xfe:
                    if ls+18 > len(message):
                        logging.warning("Invalid command received, ignore it")
                        await websocket.send("1002 Protocol violation: unknown packet type".encode())
                        await websocket.close()
                        self.connected_clients.remove(websocket)
                        break
                    x = (message[ls+1] << 8) | message[ls]
                    y = (message[ls+3] << 8) | message[ls+2]
                    r = message[ls+4]
                    g = message[ls+5]
                    b = message[ls+6]

                    uid = (message[ls+9] << 16) | (message[ls+8] << 8) | message[ls+7]

                    token_start = ls+10
                    token = ''.join(f'{byte:02x}' for byte in message[token_start:-4])

                    # 解析 id
                    id = (message[ls+29] <<24) | (message[ls+28] << 16) | (message[ls+27] << 8) | message[ls+26]
                    
                    ls += 30
                    
                    logging.debug(f"Received draw command: x={x}, y={y}, r={r}, g={g}, b={b}, uid={uid}, token={token}, id={id}")

                    if token in self.token_used_time:
                        if (time.time() - self.token_used_time[token]) < self.time_limit:
                            logging.warning(f"Token {token} has been used too long, reject the command")
                            sendBuf = bytearray([
                                0xff,
                                *self.uint_to_bytes(id,4),
                                0xee
                            ])
                            asyncio.create_task(self.append_data(client_id,sendBuf))
                            continue
                        else:
                            logging.info(f"Paint ({r}, {g}, {b}) at ({x}, {y})")
                            board[(y,x)] = (r,g,b)
                            sendBuf = bytearray([
                                0xfa,
                                *self.uint_to_bytes(x,2),
                                *self.uint_to_bytes(y,2),
                                r,g,b
                            ])
                            asyncio.create_task(self.append_data(0,sendBuf))
                            sendBuf = bytearray([
                                0xff,
                                *self.uint_to_bytes(id,4),
                                0xef
                            ])
                            asyncio.create_task(self.append_data(client_id,sendBuf))
                            self.token_used_time[token] = time.time()
                    else:
                        logging.info(f"Paint ({r}, {g}, {b}) at ({x}, {y})")
                        board[(y,x)] = (r,g,b)
                        sendBuf = bytearray([
                            0xfa,
                            *self.uint_to_bytes(x,2),
                            *self.uint_to_bytes(y,2),
                            r,g,b
                        ])
                        asyncio.create_task(self.append_data(0,sendBuf))
                        sendBuf = bytearray([
                                0xff,
                                *self.uint_to_bytes(id,4),
                                0xef
                            ])
                        asyncio.create_task(self.append_data(client_id,sendBuf))
                        self.token_used_time[token] = time.time()
                elif type == 0xfb:
                    self.ping_check[websocket] = 1


    async def send_data(self,websocket,id):
        logging.info("Start sending data to id %d", id)
        while True:
            # 检查是否有包需要发送，以及 WebSocket 连接是否已打开
            if self.total_size[id] > 0:
                logging.debug("Start sending data %d,len(chunks): %d",id, len(self.msg_data[id]))
                try:
                    await websocket.send(self.get_merage_data(id))
                except websockets.exceptions.ConnectionClosedError:
                    logging.warning("WebSocket connection closed, stop sending data")
                    await websocket.close()
                    self.connected_clients.remove(websocket)
                    break
                except Exception as e:
                    logging.error("Error occurred when sending data: %s", e)
            await asyncio.sleep(0.2)


    async def start(self):
        logging.info("Time limit: %d", self.time_limit)
        logging.info("Start WebSocket server at %s:%d", self.host, self.port)
        logging.info("WebSocket url: ws://%s:%d", self.host, self.port)

        asyncio.create_task(self.broadcast())
        asyncio.create_task(self.ping())
        asyncio.create_task(self.check_ping())
        
        async with websockets.serve(self.handle_connection, self.host, self.port):
            await asyncio.Future()


def get_logger(level=logging.INFO):
    # 创建logger对象
    logger = logging.getLogger()
    logging.basicConfig(level=logging.DEBUG,
                        format='%(asctime)s - %(levelname)s: %(message)s')
    logger.setLevel(level)
    # 创建控制台日志处理器
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    # 定义颜色输出格式
    color_formatter = colorlog.ColoredFormatter(
        '[%(asctime)s] [%(log_color)s%(levelname)s%(reset)s] %(message)s',
        log_colors={
            'DEBUG': 'cyan',
            'INFO': 'green',
            'WARNING': 'yellow',
            'ERROR': 'red',
            'CRITICAL': 'red,bg_white',
        }
    )
    # 将颜色输出格式添加到控制台日志处理器
    console_handler.setFormatter(color_formatter)
    # 移除默认的handler
    for handler in logger.handlers:
        logger.removeHandler(handler)
    # 将控制台日志处理器添加到logger对象
    logger.addHandler(console_handler)
    return logger

time_limit = 30000
port = 2380
host = "localhost"
apihost = "localhost"
apiport = 2381

def read_config():
    global time_limit
    global port
    global host
    global apihost
    global apiport
    global origins
    try:
        with open("config.json", "r") as f:
            config = json.load(f)

            # server
            time_limit = config["server"]["time_limit"]
            port = config["server"]["port"]
            host = config["server"]["host"]

            # api

            apihost = config["api"]["host"]
            apiport = config["api"]["port"]
            origins = config["api"]["origins"]
        logging.info("Read config: time_limit=%d, port=%d, host=%s", time_limit, port, host)
    except Exception as e:
        logging.error("Error occurred when reading config: %s", e)

def parse_args():
    if len(sys.argv) < 2:
        return
    global time_limit
    global port
    global host
    global apihost
    global apiport

    parser = argparse.ArgumentParser(description="LSPaintBoard-Fake-Server")

    parser.add_argument('--time_limit', type=int, default=30000, help='Token time limit in milliseconds')
    parser.add_argument('--port', type=int, default=2380, help='Server port')
    parser.add_argument('--host', type=str, default="localhost", help='Server host')
    parser.add_argument('--apihost', type=str, default="localhost", help='API host')
    parser.add_argument('--apiport', type=int, default=2381, help='API port')

    args = parser.parse_args()
    
    if args.time_limit is not None:
        time_limit = args.time_limit
    if args.port is not None:
        port = args.port
    if args.host is not None:
        host = args.host
    if args.apihost is not None:
        apihost = args.apihost
    if args.apiport is not None:
        apiport = args.apiport

    with open("config.json", "w") as f:
        config = {
            "server":{
                "time_limit": time_limit,
                "port": port,
                "host": host,
            },
            "api":{
                "host": apihost,
                "port": apiport
            }
        }
        json.dump(config, f)
        logging.info("Write config: time_limit=%d, port=%d, host=%s", time_limit, port, host)
    
class BoardApi():
    def __init__(self,host = "localhost", port = 2380,origins = []):
        self.host = host
        self.port = port
        self.app = FastAPI()
        self.origins = origins
    
    def start(self):
        logging.info("Start API server at %s:%d", self.host, self.port)
        logging.info("With allowed IP address:")
        logging.info("------------")
        for origin in self.origins:
            logging.info(origin)
        logging.info("------------")
        logging.info("API url: http://%s:%d/getboard", self.host, self.port)

        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=self.origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

        @self.app.get('/getboard')
        def get_board():
            global board
            global height
            global width

            byteArray = bytearray(height * width * 3)
    
            for y in range(0,height):
                for x in range(0,width):
                    r, g, b = board.get((y,x), (0,0,0))
                    byteArray[y * width * 3 + x * 3] = r
                    byteArray[y * width * 3 + x * 3 + 1] = g
                    byteArray[y * width * 3 + x * 3 + 2] = b

            byteArray = bytes(byteArray)
            
            return StreamingResponse(content=iter([byteArray]), media_type="application/octet-stream")
        
        threading.Thread(target=self.run_uvicorn, daemon=True).start()

    def run_uvicorn(self):
        uvicorn.run(self.app, host=self.host, port=self.port)

        

if __name__ == "__main__":
    logging = get_logger(logging.INFO)
    
    read_config()
    parse_args()

    for y in range(0,height):
        for x in range(0,width):
            board[(y,x)] = (255,255,255)

    boardapi = BoardApi(apihost, apiport,origins)
    boardapi.start()

    server = WebSocketServer(port=port, host=host, time_limit=time_limit)
    asyncio.run(server.start())
