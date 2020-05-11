import time
import RPi.GPIO as GPIO
import cv2
from datetime import datetime

# キャプチャする解像度
IMAGE_WIDTH = 960  # 1920X1080の半分
IMAGE_HEIGHT = 540

# キャプチャボード(B102)をリセットする
def init_capture():
    # GPIOの初期設定
    GPIO.setmode(GPIO.BCM)  # GPIOへアクセスする番号をBCMの番号で指定することを宣言します。
    GPIO.setup(17, GPIO.OUT, initial=GPIO.HIGH)  # リセットピン
    GPIO.setup(27, GPIO.IN)  # HDMI接続確認用ピン

    # HDMIケーブルが接続されているかの確認
    if GPIO.input(27) == GPIO.HIGH:
        # B102のハードウェアリセット
        GPIO.output(17, GPIO.LOW)
        time.sleep(0.1)
        GPIO.output(17, GPIO.HIGH)
        print("B102をリセットしました")
    else:
        print("ERROR:HDMIケーブルが接続されていません")
        GPIO.cleanup()
        exit()

    GPIO.cleanup()


# B102からの入力映像を任意のタイミングでキャプチャする
def capture_camera():
    # カメラをキャプチャする
    cap = cv2.VideoCapture(0)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 960)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 540)

    # retは画像を取得成功フラグ
    ret, frame = cap.read()

    if ret:
        date = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = "./" + date + ".png"
        print("保存しました：" + path)
        cv2.imwrite(path, frame)  # ファイル保存

        time.sleep(1)


# 初期化処理
init_capture()

# カメラをキャプチャする
capture_camera()
