from flask import Flask, render_template, Response
import cv2  # OpenCV untuk menangani video
import numpy as np 
import HandTrackingModule as htm # Modul untuk deteksi tangan
import math 
import autopy # Untuk kontrol mouse
import pyautogui # Untuk kontrol mouse dan keyboard
import time
from ctypes import cast, POINTER  
from comtypes import CLSCTX_ALL 
from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume

app = Flask(__name__)

# Inisialisasi kamera
wCam, hCam = 640, 480
cap = cv2.VideoCapture(0)
cap.set(3, wCam)
cap.set(4, hCam)

# Inisialisasi detektor tangan
detector = htm.HandDetector(maxHands=1, detectionCon=0.85, trackCon=0.8)

# Inisialisasi kontrol volume
devices = AudioUtilities.GetSpeakers()
interface = devices.Activate(
    IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
volume = cast(interface, POINTER(IAudioEndpointVolume))
volRange = volume.GetVolumeRange()

# Rentang volume
minVol = -63
maxVol = volRange[1]
hmin = 50
hmax = 200
color = (0, 215, 255)
tipIds = [4, 8, 12, 16, 20]
mode = ''
active = 0
pTime = 0

# Disable pyautogui failsafe to prevent accidental mouse movement
pyautogui.FAILSAFE = False

# Fungsi untuk menampilkan teks pada gambar
def putText(img, mode, loc=(250, 450), color=(0, 255, 255)):
    cv2.putText(img, str(mode), loc, cv2.FONT_HERSHEY_COMPLEX_SMALL,
                3, color, 3)

# Fungsi untuk menghasilkan frame video
def gen_frames():
    global mode, active, pTime
    while True:
        try:
            success, img = cap.read()
            if not success:
                print("❌ Gagal membaca frame dari kamera.")
                break
            img = detector.findHands(img)
            lmList = detector.findPosition(img, draw=False)
            fingers = []

            if len(lmList) != 0:
                # Thumb
                if lmList[tipIds[0]][1] > lmList[tipIds[0] - 1][1]:
                    fingers.append(1)
                else:
                    fingers.append(0)

                for id in range(1, 5):
                    if lmList[tipIds[id]][2] < lmList[tipIds[id] - 2][2]:
                        fingers.append(1)
                    else:
                        fingers.append(0)

                # Mode switching
                if fingers == [0, 0, 0, 0, 0] and active == 0:
                    mode = 'None'
                elif (fingers == [0, 1, 0, 0, 0] or fingers == [0, 1, 1, 0, 0]) and active == 0:
                    mode = 'Scroll'
                    active = 1
                elif fingers == [1, 1, 0, 0, 0] and active == 0:
                    mode = 'Volume'
                    active = 1
                elif fingers == [1, 1, 1, 1, 1] and active == 0:
                    mode = 'Cursor'
                    active = 1

            # SCROLL MODE
            if mode == 'Scroll':
                putText(img, mode)
                if fingers == [0, 1, 0, 0, 0]:
                    putText(img, 'Up', loc=(20, 440), color=(0, 255, 0))
                    pyautogui.scroll(300)
                elif fingers == [0, 1, 1, 0, 0]:
                    putText(img, 'Down', loc=(20, 470), color=(0, 0, 255))
                    pyautogui.scroll(-300)
                elif fingers == [0, 0, 0, 0, 0]:
                    active = 0
                    mode = 'None'

            # VOLUME MODE
            elif mode == 'Volume':
                putText(img, mode)
                if fingers and fingers[-1] == 1:
                    active = 0
                    mode = 'None'
                elif len(lmList) >= 9:
                    x1, y1 = lmList[4][1], lmList[4][2]
                    x2, y2 = lmList[8][1], lmList[8][2]
                    cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
                    length = math.hypot(x2 - x1, y2 - y1)

                    vol = np.interp(length, [hmin, hmax], [minVol, maxVol])
                    volBar = np.interp(vol, [minVol, maxVol], [400, 150])
                    volPer = np.interp(vol, [minVol, maxVol], [0, 100])
                    volume.SetMasterVolumeLevel(vol, None)

                    cv2.rectangle(img, (30, 150), (55, 400), (209, 206, 0), 3)
                    cv2.rectangle(img, (30, int(volBar)), (55, 400), (215, 255, 127), cv2.FILLED)
                    cv2.putText(img, f'{int(volPer)}%', (25, 430), cv2.FONT_HERSHEY_COMPLEX, 0.9, (209, 206, 0), 3)

            # CURSOR MODE
            elif mode == 'Cursor':
                putText(img, mode)
                if fingers[1:] == [0, 0, 0, 0]:
                    active = 0
                    mode = 'None'
                elif len(lmList) >= 9:
                    x1, y1 = lmList[8][1], lmList[8][2]
                    w, h = autopy.screen.size()
                    X = int(np.interp(x1, [110, 620], [0, w - 1]))
                    Y = int(np.interp(y1, [20, 350], [0, h - 1]))
                    autopy.mouse.move(X, Y)
                    if fingers[0] == 0:
                        pyautogui.click()

            # FPS Monitoring
            cTime = time.time()
            fps = 1 / ((cTime + 0.01) - pTime)
            pTime = cTime
            cv2.putText(img, f'FPS:{int(fps)}', (480, 50), cv2.FONT_ITALIC, 1, (255, 0, 0), 2)

            # Encode & yield frame
            ret, buffer = cv2.imencode('.jpg', img)
            frame = buffer.tobytes()
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

            time.sleep(0.03)  # biar tidak ngefreeze browser/kamera
        except Exception as e:
            print(f"⚠️ Error dalam gen_frames(): {e}")
            break

# Flask app setup
@app.route('/')
def index():
    return render_template('index.html')

# Route untuk video streaming
@app.route('/video')
def video():
    return Response(gen_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')


if __name__ == '__main__':
    app.run(debug=True)
