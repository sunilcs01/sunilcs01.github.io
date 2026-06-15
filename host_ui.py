import sys
import os
import socket
import struct
import cv2
import numpy as np
import mss
import pyautogui
import json
import threading
from PyQt5.QtWidgets import QApplication, QMainWindow, QLabel, QVBoxLayout, QWidget, QPushButton, QLineEdit, QHBoxLayout, QFrame, QFileDialog, QMessageBox
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont, QPixmap

def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

pyautogui.FAILSAFE = False

class FileTransferThread(QThread):
    file_received = pyqtSignal(str)
    error_occurred = pyqtSignal(str)

    def __init__(self, is_server=True, target_ip=None, save_dir=None):
        super().__init__()
        self.is_server = is_server
        self.target_ip = target_ip
        self.save_dir = save_dir
        self.running = True
        self.conn = None
        self.server_socket = None

    def run(self):
        try:
            if not os.path.exists(self.save_dir):
                os.makedirs(self.save_dir)

            if self.is_server:
                self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.server_socket.bind(('0.0.0.0', 10001))
                self.server_socket.listen(1)
                self.conn, addr = self.server_socket.accept()
            else:
                self.conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                QThread.msleep(1500)
                self.conn.connect((self.target_ip, 10001))

            while self.running:
                raw_namelen = self._recvall(4)
                if not raw_namelen: break
                name_len = struct.unpack("!L", raw_namelen)[0]

                raw_name = self._recvall(name_len)
                if not raw_name: break
                filename = raw_name.decode('utf-8')

                raw_filesize = self._recvall(8)
                if not raw_filesize: break
                filesize = struct.unpack("!Q", raw_filesize)[0]

                save_path = os.path.join(self.save_dir, filename)
                received_size = 0
                with open(save_path, 'wb') as f:
                    while received_size < filesize:
                        chunk_size = min(4096, filesize - received_size)
                        chunk = self.conn.recv(chunk_size)
                        if not chunk: break
                        f.write(chunk)
                        received_size += len(chunk)
                
                self.file_received.emit(save_path)

        except Exception as e:
            pass
        finally:
            self.stop()

    def _recvall(self, n):
        data = bytearray()
        while len(data) < n:
            packet = self.conn.recv(n - len(data))
            if not packet: return None
            data.extend(packet)
        return bytes(data)

    def send_file_async(self, filepath):
        threading.Thread(target=self._send_file, args=(filepath,), daemon=True).start()

    def _send_file(self, filepath):
        if not self.conn: return
        try:
            filename = os.path.basename(filepath)
            filesize = os.path.getsize(filepath)
            
            encoded_name = filename.encode('utf-8')
            header = struct.pack("!L", len(encoded_name)) + encoded_name + struct.pack("!Q", filesize)
            
            self.conn.sendall(header)
            
            with open(filepath, 'rb') as f:
                while True:
                    chunk = f.read(4096)
                    if not chunk: break
                    self.conn.sendall(chunk)
        except Exception as e:
            self.error_occurred.emit(f"전송 오류: {str(e)}")

    def stop(self):
        self.running = False
        try:
            if self.conn: self.conn.close()
            if self.server_socket: self.server_socket.close()
        except: pass

class InputClientThread(QThread):
    def __init__(self, target_ip):
        super().__init__()
        self.target_ip = target_ip
        self.running = True

    def run(self):
        try:
            self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            QThread.msleep(500)
            self.client_socket.connect((self.target_ip, 9998))
            
            payload_size = struct.calcsize("!L")
            data = b""
            
            while self.running:
                while len(data) < payload_size:
                    packet = self.client_socket.recv(4096)
                    if not packet: break
                    data += packet
                if not data: break
                
                packed_msg_size = data[:payload_size]
                data = data[payload_size:]
                msg_size = struct.unpack("!L", packed_msg_size)[0]
                
                while len(data) < msg_size:
                    packet = self.client_socket.recv(4096)
                    if not packet: break
                    data += packet
                if len(data) < msg_size: break
                
                cmd_data = data[:msg_size]
                data = data[msg_size:]
                
                cmd_dict = json.loads(cmd_data.decode('utf-8'))
                self.execute_command(cmd_dict)
                
        except Exception as e:
            pass
        finally:
            if hasattr(self, 'client_socket'):
                self.client_socket.close()

    def execute_command(self, cmd):
        try:
            w, h = pyautogui.size()
            if cmd["type"] in ["mouse_move", "mouse_down", "mouse_up"]:
                x = int(cmd["x"] * w)
                y = int(cmd["y"] * h)
                btn = cmd.get("btn", "left")
                
                if cmd["type"] == "mouse_move":
                    pyautogui.moveTo(x, y)
                elif cmd["type"] == "mouse_down":
                    pyautogui.mouseDown(x, y, button=btn)
                elif cmd["type"] == "mouse_up":
                    pyautogui.mouseUp(x, y, button=btn)
            elif cmd["type"] == "scroll":
                pyautogui.scroll(cmd["clicks"] * 100)
            elif cmd["type"] == "key_press":
                pyautogui.write(cmd["key"])
        except Exception as e:
            pass

    def stop(self):
        self.running = False
        if hasattr(self, 'client_socket'):
            try: self.client_socket.close()
            except: pass

class ClientThread(QThread):
    connected = pyqtSignal()
    error_occurred = pyqtSignal(str)

    def __init__(self, target_ip):
        super().__init__()
        self.target_ip = target_ip
        self.running = True

    def run(self):
        try:
            self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.client_socket.connect((self.target_ip, 9999))
            self.connected.emit()
            
            with mss.mss() as sct:
                monitor = sct.monitors[0]
                while self.running:
                    sct_img = sct.grab(monitor)
                    img = np.array(sct_img)
                    
                    h, w = img.shape[:2]
                    scale = 1280.0 / w
                    new_w, new_h = 1280, int(h * scale)
                    img = cv2.resize(img, (new_w, new_h))
                    
                    img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
                    
                    result, frame = cv2.imencode('.jpg', img, [int(cv2.IMWRITE_JPEG_QUALITY), 65])
                    data = frame.tobytes()
                    
                    msg_size = struct.pack("!L", len(data))
                    self.client_socket.sendall(msg_size + data)
                    
                    QThread.msleep(30)
                    
        except Exception as e:
            self.error_occurred.emit(str(e))
        finally:
            if hasattr(self, 'client_socket'):
                self.client_socket.close()

    def stop(self):
        self.running = False

class HostWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("sunilcs 원격제어용 (고객)")
        self.setFixedSize(450, 650)
        self.setStyleSheet("""
            QMainWindow { background-color: #050505; }
            QWidget { background-color: transparent; }
        """)
        
        self.init_ui()

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        outer_layout = QVBoxLayout()
        outer_layout.setContentsMargins(20, 20, 20, 20)
        central_widget.setLayout(outer_layout)
        
        neon_frame = QFrame()
        neon_frame.setObjectName("NeonFrame")
        neon_frame.setStyleSheet("""
            #NeonFrame {
                background-color: #111111;
                border: 3px solid #00FFFF;
                border-radius: 20px;
            }
        """)
        outer_layout.addWidget(neon_frame)
        
        layout = QVBoxLayout()
        layout.setAlignment(Qt.AlignCenter)
        neon_frame.setLayout(layout)

        logo_label = QLabel()
        pixmap = QPixmap(resource_path("logo.png"))
        if not pixmap.isNull():
            logo_label.setPixmap(pixmap.scaledToWidth(250, Qt.SmoothTransformation))
        logo_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(logo_label)
        
        layout.addSpacing(30)

        title_label = QLabel("원격 지원 접속")
        title_label.setFont(QFont("Arial", 10, QFont.Bold))
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setStyleSheet("color: #FFFFFF; border: none;")
        layout.addWidget(title_label)
        
        layout.addSpacing(50)

        desc_label = QLabel("상담원이 알려주신 10자리 번호를 입력하세요.")
        desc_label.setFont(QFont("Arial", 10))
        desc_label.setAlignment(Qt.AlignCenter)
        desc_label.setStyleSheet("color: #BBBBBB; border: none;")
        layout.addWidget(desc_label)

        layout.addSpacing(30)

        input_layout = QHBoxLayout()
        self.id_input = QLineEdit()
        self.id_input.setPlaceholderText("예: 323-223-5522")
        self.id_input.setFont(QFont("Arial", 10))
        self.id_input.setAlignment(Qt.AlignCenter)
        self.id_input.setFixedHeight(70)
        self.id_input.setStyleSheet("""
            QLineEdit {
                color: #FFFF00;
                background-color: #222222;
                border: 2px solid #444444;
                border-radius: 10px;
                padding: 10px;
            }
            QLineEdit:focus {
                border: 2px solid #00FFFF;
            }
        """)
        
        input_layout.addWidget(self.id_input)
        layout.addLayout(input_layout)

        layout.addSpacing(50)

        self.send_file_btn = QPushButton("사장님께 파일 보내기")
        self.send_file_btn.setFont(QFont("Arial", 10, QFont.Bold))
        self.send_file_btn.setFixedHeight(50)
        self.send_file_btn.setStyleSheet("""
            QPushButton {
                background-color: #00A300; 
                color: white; 
                border-radius: 10px;
                border: none;
            }
            QPushButton:hover {
                background-color: #007800;
            }
            QPushButton:disabled {
                background-color: #333333;
                color: #777777;
            }
        """)
        self.send_file_btn.setEnabled(False)
        self.send_file_btn.clicked.connect(self.on_send_file_clicked)
        
        layout.addWidget(self.send_file_btn)
        layout.addSpacing(20)

        btn_layout = QHBoxLayout()
        
        self.connect_btn = QPushButton("연결하기")
        self.connect_btn.setFont(QFont("Arial", 10, QFont.Bold))
        self.connect_btn.setFixedHeight(60)
        self.connect_btn.setStyleSheet("""
            QPushButton {
                background-color: #0078D7; 
                color: white; 
                border-radius: 10px;
                border: none;
            }
            QPushButton:hover {
                background-color: #005A9E;
            }
            QPushButton:disabled {
                background-color: #333333;
                color: #777777;
            }
        """)
        self.connect_btn.clicked.connect(self.on_connect_clicked)
        
        self.disconnect_btn = QPushButton("연결 끊기")
        self.disconnect_btn.setFont(QFont("Arial", 10, QFont.Bold))
        self.disconnect_btn.setFixedHeight(60)
        self.disconnect_btn.setStyleSheet("""
            QPushButton {
                background-color: #D70000; 
                color: white; 
                border-radius: 10px;
                border: none;
            }
            QPushButton:hover {
                background-color: #A30000;
            }
            QPushButton:disabled {
                background-color: #333333;
                color: #777777;
            }
        """)
        self.disconnect_btn.setEnabled(False)
        self.disconnect_btn.clicked.connect(self.on_disconnect_clicked)

        btn_layout.addWidget(self.connect_btn)
        btn_layout.addWidget(self.disconnect_btn)
        layout.addLayout(btn_layout)

        layout.addSpacing(40)

        self.status_label = QLabel("대기 중...")
        self.status_label.setFont(QFont("Arial", 10))
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet("color: #777777; border: none;")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

    def on_connect_clicked(self):
        input_id = self.id_input.text().replace("-", "").replace(" ", "")
        
        if len(input_id) != 10 or not input_id.isdigit():
            self.status_label.setText("올바른 10자리 숫자를 입력해주세요.")
            self.status_label.setStyleSheet("color: #FF3333; border: none;")
            return
            
        try:
            ip_int = int(input_id)
            packed_ip = struct.pack("!L", ip_int)
            target_ip = socket.inet_ntoa(packed_ip)
        except Exception as e:
            self.status_label.setText("잘못된 접속 번호입니다.")
            self.status_label.setStyleSheet("color: #FF3333; border: none;")
            return

        self.status_label.setText(f"사장님 PC({target_ip})로 접속 중...")
        self.status_label.setStyleSheet("color: #00FFFF; border: none;")
        self.connect_btn.setEnabled(False)
        self.disconnect_btn.setEnabled(True)
        self.id_input.setEnabled(False)
        
        desktop_path = os.path.join(os.path.expanduser('~'), 'Desktop')
        self.file_thread = FileTransferThread(is_server=False, target_ip=target_ip, save_dir=desktop_path)
        self.file_thread.file_received.connect(self.on_file_received)
        self.file_thread.start()
        
        self.input_thread = InputClientThread(target_ip)
        self.input_thread.start()
        
        self.client_thread = ClientThread(target_ip)
        self.client_thread.connected.connect(self.on_client_connected)
        self.client_thread.error_occurred.connect(self.on_client_error)
        self.client_thread.start()

    def on_send_file_clicked(self):
        if not hasattr(self, 'file_thread') or not self.file_thread.running: return
        filepath, _ = QFileDialog.getOpenFileName(self, "사장님께 보낼 파일 선택", "", "All Files (*)")
        if filepath:
            self.file_thread.send_file_async(filepath)
            QMessageBox.information(self, "전송 시작", "파일 전송을 시작했습니다. 사장님 PC에 저장됩니다.")

    def on_file_received(self, filepath):
        QMessageBox.information(self, "파일 수신 완료", f"사장님으로부터 파일이 도착했습니다!\n바탕화면에 자동 저장되었습니다.\n\n저장 위치: {filepath}")

    def on_client_connected(self):
        self.status_label.setText("사장님이 원격 제어 중입니다...")
        self.send_file_btn.setEnabled(True)

    def on_client_error(self, err):
        if hasattr(self, 'client_thread'):
            self.client_thread.stop()
            self.client_thread.wait()
            
        self.connect_btn.setEnabled(True)
        self.disconnect_btn.setEnabled(False)
        self.send_file_btn.setEnabled(False)
        self.id_input.setEnabled(True)
        
        if "10054" in err or "10053" in err:
            self.status_label.setText("사장님이 원격 제어를 종료하셨습니다.")
            self.status_label.setStyleSheet("color: #777777; border: none;")
        else:
            self.status_label.setText(f"연결 실패: 방화벽이나 포트를 확인하세요. ({err})")
            self.status_label.setStyleSheet("color: #FF3333; border: none;")

    def on_disconnect_clicked(self):
        try:
            if hasattr(self, 'file_thread'):
                self.file_thread.stop()
                self.file_thread.wait()
            if hasattr(self, 'input_thread'):
                self.input_thread.stop()
                self.input_thread.wait()
            if hasattr(self, 'client_thread'):
                self.client_thread.stop()
                self.client_thread.wait()
        except: pass
            
        self.status_label.setText("연결이 종료되었습니다.")
        self.status_label.setStyleSheet("color: #777777; border: none;")
        self.connect_btn.setEnabled(True)
        self.disconnect_btn.setEnabled(False)
        self.send_file_btn.setEnabled(False)
        self.id_input.setEnabled(True)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = HostWindow()
    window.show()
    sys.exit(app.exec_())
