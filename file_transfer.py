import socket
import os
import struct
import json
from pathlib import Path


class FileTransfer:
    BUFFER_SIZE = 4096
    PORT = 9999

    def send_file(self, filepath, target_ip, progress_callback=None):
        """Send file"""
        client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client.connect((target_ip, self.PORT))

        # Send file metadata
        filesize = os.path.getsize(filepath)
        filename = os.path.basename(filepath)
        metadata = json.dumps({
            'filename': filename,
            'filesize': filesize
        }).encode('utf-8')

        # First send metadata length (4 bytes), then send metadata
        client.send(struct.pack('!I', len(metadata)))
        client.send(metadata)

        # Send file content (binary)
        sent = 0
        with open(filepath, 'rb') as f:
            while True:
                data = f.read(self.BUFFER_SIZE)
                if not data:
                    break
                client.sendall(data)  # Use sendall to ensure complete transmission
                sent += len(data)
                if progress_callback:
                    progress_callback(sent, filesize)

        client.close()

    def receive_file(self, save_dir, progress_callback=None):
        """Receive file"""
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)  # Allow port reuse
        server.bind(('0.0.0.0', self.PORT))
        server.listen(1)

        conn, addr = server.accept()
        print(f"Connection from: {addr}")

        try:
            # First receive metadata length (4 bytes)
            metadata_size_data = self._recv_exact(conn, 4)
            metadata_size = struct.unpack('!I', metadata_size_data)[0]

            # Receive metadata
            metadata = self._recv_exact(conn, metadata_size).decode('utf-8')
            info = json.loads(metadata)
            filename = info['filename']
            filesize = info['filesize']

            print(f"Receiving file: {filename}, Size: {filesize} bytes")

            # Receive file content
            filepath = os.path.join(save_dir, filename)
            received = 0
            with open(filepath, 'wb') as f:
                while received < filesize:
                    remaining = filesize - received
                    chunk_size = min(self.BUFFER_SIZE, remaining)
                    data = conn.recv(chunk_size)
                    if not data:
                        raise ConnectionError("Connection interrupted")
                    f.write(data)
                    received += len(data)
                    if progress_callback:
                        progress_callback(received, filesize)

            print(f"File saved to: {filepath}")
            return filepath
        finally:
            conn.close()
            server.close()

    def _recv_exact(self, conn, size):
        """Receive exact number of bytes"""
        data = b''
        while len(data) < size:
            chunk = conn.recv(size - len(data))
            if not chunk:
                raise ConnectionError("Connection unexpectedly closed")
            data += chunk
        return data