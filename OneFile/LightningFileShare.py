import socket
import os
import struct
import json
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

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

class NeumorphicButton(tk.Canvas):
    """Custom neumorphic button widget"""

    def __init__(self, parent, text, command, bg_color='#e0e5ec', fg_color='#2c3e50', **kwargs):
        width = kwargs.pop('width', 150)
        height = kwargs.pop('height', 45)
        super().__init__(parent, width=width, height=height, bg=bg_color,
                         highlightthickness=0, **kwargs)

        self.bg_color = bg_color
        self.fg_color = fg_color
        self.command = command
        self.text = text
        self.pressed = False

        self.draw_button()
        self.bind('<Button-1>', self.on_press)
        self.bind('<ButtonRelease-1>', self.on_release)
        self.bind('<Enter>', self.on_hover)
        self.bind('<Leave>', self.on_leave)

    def draw_button(self, pressed=False):
        self.delete('all')
        w, h = self.winfo_reqwidth(), self.winfo_reqheight()

        if pressed:
            # Inset shadow effect
            self.create_rectangle(2, 2, w - 2, h - 2, fill=self.bg_color, outline='')
            self.create_line(5, 5, w - 5, 5, fill='#a3b1c6', width=2)
            self.create_line(5, 5, 5, h - 5, fill='#a3b1c6', width=2)
        else:
            # Elevated shadow effect
            self.create_rectangle(0, 0, w, h, fill=self.bg_color, outline='')
            # Dark shadow (bottom-right)
            self.create_line(w - 1, 8, w - 1, h - 1, fill='#a3b1c6', width=3)
            self.create_line(8, h - 1, w - 1, h - 1, fill='#a3b1c6', width=3)
            # Light shadow (top-left)
            self.create_line(1, h - 8, 1, 1, fill='#ffffff', width=3)
            self.create_line(1, 1, w - 8, 1, fill='#ffffff', width=3)

        # Text
        self.create_text(w // 2, h // 2, text=self.text, font=('Segoe UI', 11, 'bold'),
                         fill=self.fg_color)

    def on_press(self, event):
        self.pressed = True
        self.draw_button(pressed=True)

    def on_release(self, event):
        self.pressed = False
        self.draw_button(pressed=False)
        if self.command:
            self.command()

    def on_hover(self, event):
        self.config(cursor='hand2')

    def on_leave(self, event):
        self.config(cursor='')


class NeumorphicFrame(tk.Canvas):
    """Custom neumorphic frame/container"""

    def __init__(self, parent, bg_color='#e0e5ec', inset=True, **kwargs):
        super().__init__(parent, bg=bg_color, highlightthickness=0, **kwargs)
        self.bg_color = bg_color
        self.inset = inset
        self.bind('<Configure>', self.on_configure)

    def on_configure(self, event):
        self.delete('all')
        w, h = event.width, event.height

        if self.inset:
            # Inset effect for containers
            self.create_rectangle(0, 0, w, h, fill=self.bg_color, outline='')
            # Inner shadow
            self.create_line(3, 3, w - 3, 3, fill='#a3b1c6', width=2)
            self.create_line(3, 3, 3, h - 3, fill='#a3b1c6', width=2)
            self.create_line(w - 3, 3, w - 3, h - 3, fill='#d1d9e6', width=1)
            self.create_line(3, h - 3, w - 3, h - 3, fill='#d1d9e6', width=1)
        else:
            # Raised effect
            self.create_rectangle(0, 0, w, h, fill=self.bg_color, outline='')
            self.create_line(w - 1, 5, w - 1, h - 1, fill='#a3b1c6', width=2)
            self.create_line(5, h - 1, w - 1, h - 1, fill='#a3b1c6', width=2)
            self.create_line(1, h - 5, 1, 1, fill='#ffffff', width=2)
            self.create_line(1, 1, w - 5, 1, fill='#ffffff', width=2)


class NeumorphicProgressBar(tk.Canvas):
    """Custom neumorphic progress bar"""

    def __init__(self, parent, bg_color='#e0e5ec', **kwargs):
        height = kwargs.pop('height', 30)
        super().__init__(parent, height=height, bg=bg_color, highlightthickness=0, **kwargs)
        self.bg_color = bg_color
        self.progress_color = '#4CAF50'
        self.value = 0
        self.bind('<Configure>', self.draw)

    def draw(self, event=None):
        self.delete('all')
        w = self.winfo_width()
        h = self.winfo_height()

        # Background track (inset)
        self.create_rectangle(0, 0, w, h, fill=self.bg_color, outline='')
        self.create_line(2, 2, w - 2, 2, fill='#a3b1c6', width=2)
        self.create_line(2, 2, 2, h - 2, fill='#a3b1c6', width=2)

        # Progress fill
        if self.value > 0:
            progress_width = int((w - 8) * (self.value / 100))
            # Gradient effect
            self.create_rectangle(4, 4, 4 + progress_width, h - 4,
                                  fill=self.progress_color, outline='')
            # Shine effect
            self.create_rectangle(4, 4, 4 + progress_width, h // 2,
                                  fill=self.progress_color, outline='',
                                  stipple='gray25')

    def set_value(self, value):
        self.value = max(0, min(100, value))
        self.draw()


class FileShareGUI:
    def __init__(self):
        self.window = tk.Tk()
        self.window.title("Lightning File Share")
        self.window.geometry("650x550")

        # Neumorphic color scheme
        self.bg_color = '#e0e5ec'
        self.text_color = '#2c3e50'
        self.accent_color = '#4CAF50'

        self.window.config(bg=self.bg_color)

        self.transfer = FileTransfer()
        hostname = socket.gethostname()
        self.discovery = DeviceDiscovery(hostname)

        self.setup_ui()
        self.start_services()

    def setup_ui(self):
        # Main container with padding
        main_container = tk.Frame(self.window, bg=self.bg_color)
        main_container.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        # Title
        title_label = tk.Label(main_container, text="⚡ Lightning File Share",
                               font=('Segoe UI', 20, 'bold'),
                               bg=self.bg_color, fg=self.text_color)
        title_label.pack(pady=(0, 20))

        # Device list section
        device_label = tk.Label(main_container, text="Available Devices",
                                font=('Segoe UI', 12, 'bold'),
                                bg=self.bg_color, fg=self.text_color)
        device_label.pack(anchor='w', pady=(0, 10))

        # Neumorphic frame for device list
        self.device_frame = NeumorphicFrame(main_container, bg_color=self.bg_color,
                                            inset=True, width=600, height=200)
        self.device_frame.pack(fill=tk.BOTH, pady=(0, 20))
        self.device_frame.pack_propagate(False)

        # Listbox with custom styling
        listbox_container = tk.Frame(self.device_frame, bg=self.bg_color)
        listbox_container.place(relx=0.5, rely=0.5, anchor='center',
                                relwidth=0.95, relheight=0.9)

        self.device_listbox = tk.Listbox(listbox_container,
                                         font=('Segoe UI', 10),
                                         bg='#e0e5ec',
                                         fg=self.text_color,
                                         selectbackground='#4CAF50',
                                         selectforeground='white',
                                         relief=tk.FLAT,
                                         borderwidth=0,
                                         highlightthickness=0)
        self.device_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scrollbar = tk.Scrollbar(listbox_container)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.device_listbox.config(yscrollcommand=scrollbar.set)
        scrollbar.config(command=self.device_listbox.yview)

        # Button area
        btn_container = tk.Frame(main_container, bg=self.bg_color)
        btn_container.pack(pady=20)

        self.send_btn = NeumorphicButton(btn_container, text="📤 Send File",
                                         command=self.send_file,
                                         bg_color=self.bg_color,
                                         fg_color=self.accent_color,
                                         width=180, height=50)
        self.send_btn.pack(side=tk.LEFT, padx=10)

        self.receive_btn = NeumorphicButton(btn_container, text="📥 Receive File",
                                            command=self.receive_file,
                                            bg_color=self.bg_color,
                                            fg_color='#2196F3',
                                            width=180, height=50)
        self.receive_btn.pack(side=tk.LEFT, padx=10)

        # Progress section
        progress_label = tk.Label(main_container, text="Transfer Progress",
                                  font=('Segoe UI', 11, 'bold'),
                                  bg=self.bg_color, fg=self.text_color)
        progress_label.pack(anchor='w', pady=(10, 5))

        self.progress = NeumorphicProgressBar(main_container, bg_color=self.bg_color)
        self.progress.pack(fill=tk.X, pady=(0, 15))

        # Status label with neumorphic container
        status_container = NeumorphicFrame(main_container, bg_color=self.bg_color,
                                           inset=False, height=50)
        status_container.pack(fill=tk.X)
        status_container.pack_propagate(False)

        self.status_label = tk.Label(status_container, text="✓ Ready",
                                     font=('Segoe UI', 11),
                                     bg=self.bg_color, fg=self.accent_color)
        self.status_label.place(relx=0.5, rely=0.5, anchor='center')

    def start_services(self):
        """Start background services"""
        self.discovery.start_broadcast()
        self.discovery.listen_for_devices(self.on_device_found)

    def on_device_found(self, ip, name):
        """Callback when a new device is discovered"""
        self.device_listbox.insert(tk.END, f"{name} ({ip})")

    def send_file(self):
        selection = self.device_listbox.curselection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a target device first!")
            return

        filepath = filedialog.askopenfilename()
        if not filepath:
            return

        # Extract IP address
        device_info = self.device_listbox.get(selection[0])
        target_ip = device_info.split('(')[1].rstrip(')')

        def progress_update(sent, total):
            percent = (sent / total) * 100
            self.progress.set_value(percent)
            self.status_label.config(text=f"📤 Sending... {percent:.1f}%",
                                     fg='#2196F3')
            self.window.update_idletasks()

        def send_thread():
            try:
                self.transfer.send_file(filepath, target_ip, progress_update)
                self.status_label.config(text="✓ Send complete!", fg=self.accent_color)
                self.progress.set_value(0)
            except Exception as e:
                messagebox.showerror("Error", f"Send failed: {str(e)}")
                self.status_label.config(text="✗ Send failed", fg='#f44336')
                self.progress.set_value(0)

        threading.Thread(target=send_thread, daemon=True).start()

    def receive_file(self):
        save_dir = filedialog.askdirectory()
        if not save_dir:
            return

        def progress_update(received, total):
            percent = (received / total) * 100
            self.progress.set_value(percent)
            self.status_label.config(text=f"📥 Receiving... {percent:.1f}%",
                                     fg='#2196F3')
            self.window.update_idletasks()

        def receive_thread():
            try:
                self.status_label.config(text="⏳ Waiting for file...", fg='#FF9800')
                filepath = self.transfer.receive_file(save_dir, progress_update)
                messagebox.showinfo("Success", f"File saved to:\n{filepath}")
                self.status_label.config(text="✓ Receive complete!", fg=self.accent_color)
                self.progress.set_value(0)
            except Exception as e:
                messagebox.showerror("Error", f"Receive failed: {str(e)}")
                self.status_label.config(text="✗ Receive failed", fg='#f44336')
                self.progress.set_value(0)

        threading.Thread(target=receive_thread, daemon=True).start()

    def run(self):
        self.window.mainloop()


if __name__ == "__main__":
    app = FileShareGUI()
    app.run()