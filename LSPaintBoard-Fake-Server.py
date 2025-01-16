import asyncio
import websockets
import logging
import colorlog
import struct
import time
import json
import argparse

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
                    x = struct.unpack_from('<H', message, ls)[0]
                    y = struct.unpack_from('<H', message, ls+2)[0]
                    r = struct.unpack_from('B', message, ls+4)[0]
                    g = struct.unpack_from('B', message, ls+5)[0]
                    b = struct.unpack_from('B', message, ls+6)[0]
                    uid0 = struct.unpack_from('B', message, ls+7)[0]
                    uid1 = struct.unpack_from('B', message, ls+8)[0]
                    uid2 = struct.unpack_from('B', message, ls+9)[0]
                    uid = (uid0 << 16) | (uid1 << 8) | uid2
                    high, low = struct.unpack_from('<QQ', message,ls+10)
                    token = (high << 64) | low
                    id = struct.unpack_from('<I', message, ls+18)[0]
                    ls += 26
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


    async def send_data(self,websocket,id):
        logging.info("Start sending data to id %d", id)
        while True:
            # 检查是否有包需要发送，以及 WebSocket 连接是否已打开
            if self.total_size[id] > 0:
                logging.debug("Start sending data,len(chunks): %d", len(self.msg_data[id]))
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
        logging.info("Start WebSocket server at %s:%d", self.host, self.port)

        asyncio.create_task(self.broadcast())
        
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

def read_config():
    global time_limit
    global port
    global host
    try:
        with open("config.json", "r") as f:
            config = json.load(f)
            time_limit = config["time_limit"]
            port = config["port"]
            host = config["host"]
        logging.info("Read config: time_limit=%d, port=%d, host=%s", time_limit, port, host)
    except Exception as e:
        logging.error("Error occurred when reading config: %s", e)

def parse_args():
    global time_limit
    global port
    global host

    parser = argparse.ArgumentParser(description="LSPaintBoard-Fake-Server")

    parser.add_argument('--time_limit', type=int, default=30000, help='Token time limit in milliseconds')
    parser.add_argument('--port', type=int, default=2380, help='Server port')
    parser.add_argument('--host', type=str, default="localhost", help='Server host')

    args = parser.parse_args()
    
    if args.time_limit is not None:
        time_limit = args.time_limit
    if args.port is not None:
        port = args.port
    if args.host is not None:
        host = args.host
    
    with open("config.json", "w") as f:
            json.dump({"time_limit": time_limit, "port": port, "host": host}, f)

if __name__ == "__main__":
    logging = get_logger(logging.INFO)

    parse_args()
    read_config()

    server = WebSocketServer(port=port, host=host, time_limit=time_limit)
    asyncio.run(server.start())
