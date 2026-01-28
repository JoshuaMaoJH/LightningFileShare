import socket
import json
import threading


class DeviceDiscovery:
    BROADCAST_PORT = 9998

    def __init__(self, device_name):
        self.device_name = device_name
        self.devices = {}  # {ip: name}

    def start_broadcast(self):
        """Continuously broadcast own presence"""

        def broadcast():
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

            while True:
                message = json.dumps({'name': self.device_name})
                sock.sendto(message.encode(), ('<broadcast>', self.BROADCAST_PORT))
                threading.Event().wait(3)  # Broadcast every 3 seconds

        thread = threading.Thread(target=broadcast, daemon=True)
        thread.start()

    def listen_for_devices(self, callback):
        """Listen for other devices on the LAN"""

        def listen():
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.bind(('', self.BROADCAST_PORT))

            while True:
                data, addr = sock.recvfrom(1024)
                info = json.loads(data.decode())
                ip = addr[0]
                if ip not in self.devices or self.devices[ip] != info['name']:
                    self.devices[ip] = info['name']
                    if callback:
                        callback(ip, info['name'])

        thread = threading.Thread(target=listen, daemon=True)
        thread.start()