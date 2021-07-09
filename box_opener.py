import cv2
import numpy as np
import time
import itertools
import serial
import threading
import sys

# キャプチャの設定
WINDOW_NAME = "rpiplay"
WINDOW_ID = "0x1e00001"
WINDOW_WIDTH = 1920
WINDOW_HEIGHT = 1080
IMAGE_WIDTH = 960
IMAGE_HEIGHT = 540

# 画面判別処理を中断するまでの回数
MAX_ERROR_COUNT = 500


class TouchController:
    def __init__(self):
        self.ser = serial.Serial("/dev/ttyUSB0", 115200, timeout=None)

    def __del__(self):
        self.ser.close()

    def send_message(self, message):
        self.ser.write(bytes(message, "UTF-8"))
        time.sleep(0.2)

    def home(self):
        self.send_message("HOME\n")

    def tap(self):
        self.send_message("TAP\n")

    def move(self, destination_image_coordinate):
        x, y = destination_image_coordinate
        message = "MOVE," + str(x) + "," + str(y) + "\n"
        self.send_message(message)


class ScreenCapture(threading.Thread):
    def __init__(self):
        super(ScreenCapture, self).__init__()

        # キャプチャの初期設定
        self.video_source = cv2.VideoCapture(
            # f"ximagesrc xname={WINDOW_NAME} ! videoconvert ! videoscale ! video/x-raw,width={WINDOW_WIDTH},height={WINDOW_HEIGHT} ! appsink"
            f"ximagesrc xid={WINDOW_ID} ! videoconvert ! videoscale ! video/x-raw,width={WINDOW_WIDTH},height={WINDOW_HEIGHT} ! appsink"
        )

    def stop(self):
        self.stop = True

    def run(self):
        self.stop = False

        while not self.stop:
            ret, image_original = self.video_source.read()

            if ret:
                # キャプチャした画像をリサイズして更新
                self.image_color = cv2.resize(
                    image_original, (IMAGE_WIDTH, IMAGE_HEIGHT)
                )
                # キャプチャした画像を表示
                cv2.imshow("fgo_auto", self.image_color)
                cv2.waitKey(1)

    def get_image(self):
        return self.image_color


##### 任意画像の位置の認識 #####
def get_template_image_position(image_color, image_name, roi=None, debug_mode=False):
    THRESHOLD = 0.80  # 一致度の閾値; 一致度の最大値がこの閾値以上であれば、テンプレートと一致したとみなす
    TEMPLATE_IMAGE_PATH = "./pict/" + image_name + ".png"

    # キャプチャ画像のグレースケール化
    image_gray = cv2.cvtColor(image_color, cv2.COLOR_BGR2GRAY)

    # ROIの設定
    if roi is not None:
        image_gray = image_gray[
            roi["top_y"] : roi["bottom_y"], roi["top_x"] : roi["bottom_x"]
        ]

    # テンプレートの画像をグレースケールで読み込む
    template = cv2.imread(TEMPLATE_IMAGE_PATH, 0)

    # テンプレートマッチング処理
    result = cv2.matchTemplate(image_gray, template, cv2.TM_CCOEFF_NORMED)

    # 一致度の最大値と位置を取得
    _, max_val, _, max_loc = cv2.minMaxLoc(result)
    top_x, top_y = max_loc
    if roi is not None:
        top_x += roi["top_x"]
        top_y += roi["top_y"]
    width, height = template.shape[::-1]

    if debug_mode:
        result = image_color.copy()
        # 検出領域を四角で囲む
        cv2.rectangle(
            result, (top_x, top_y), (top_x + width, top_y + height), (255, 0, 0), 2
        )

        # 結果を出力
        cv2.imwrite("./debug/" + image_name + ".jpg", result)
        print(
            "image_name:",
            image_name,
            "    max_val:",
            max_val,
            "    max_loc:",
            (top_x, top_y),
        )

    # 一致度が閾値以上：一致するエリアの中心座標を返す
    # 一致度が閾値以下：Noneを返す
    if max_val > THRESHOLD:
        # タップの位置を求める
        tap_position = np.array([top_x + int(width / 2), top_y + int(height / 2)])
        return tap_position
    else:
        return None


if __name__ == "__main__":
    # 画面制御のインスタンスを作成
    tc = TouchController()

    # 画面キャプチャのインスタンスを生成
    sc = ScreenCapture()
    sc.start()
    time.sleep(1)

    # ポインタを初期位置に戻す
    tc.home()

    try:
        error_counter = 0
        while True:
            # ポインタを初期位置に戻す
            tc.home()

            # 画像をキャプチャ
            image_color = sc.get_image()

            # 次のアクションを決める
            tap_position = get_template_image_position(image_color, "open_box")
            if tap_position is not None:
                tc.move(tap_position)
                for i in range(5):
                    tc.tap()
                    time.sleep(0.1)
                print("回転します")
            else:
                tap_position = get_template_image_position(image_color, "リセット")
                if tap_position is not None:
                    tc.move(tap_position)
                    tc.tap()
                    time.sleep(2)
                    print("箱をリセットします")

                    image_color = sc.get_image()
                    tap_position = get_template_image_position(image_color, "実行する")
                    print(tap_position)
                    tc.move(tap_position)
                    tc.tap()
                    image_color = sc.get_image()
                    time.sleep(2)

                    image_color = sc.get_image()
                    tap_position = get_template_image_position(image_color, "閉じる")
                    tc.move(tap_position)
                    tc.tap()
                    print("箱をリセットしました")
                else:
                    error_counter += 1

            # 画面判別処理を繰り返してもフェーズが判別不明の場合
            if error_counter >= MAX_ERROR_COUNT:
                print("エラー：現在のフェーズが判別できませんでした")
                while True:
                    print("中断します(rで再開, eで終了): ", end="")
                    s = input()
                    if s == "r":
                        error_counter = 0
                        break
                    elif s == "e":
                        sys.exit()
                        break
            time.sleep(0.2)

    except KeyboardInterrupt:
        print("プログラムを終了します")
        sys.exit()
