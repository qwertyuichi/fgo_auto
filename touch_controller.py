import os
import numpy as np
import time

# ポインタの現在位置はscreen_resolutionで管理されることに注意
# イメージ座標系：左上を原点として、→X, ↓Y
# スクリーン座標系：左下を原点として、↑X, →Y
class TouchController:
    def __init__(
        self,
        image_resolution=np.array([960, 540]),  # イメージ座標系でのXY
        screen_resolution=np.array([750, 1334]),  # スクリーン座標系でのXY
        pointer_resolution=2.11,
        device="/dev/hidg0",
    ):
        self.image_resolution = image_resolution
        self.screen_resolution = screen_resolution
        self.pointer_resoltuion = pointer_resolution

        # HIDにアクセスするファイルディスクリプタの作成
        self.fd = os.open(device, os.O_RDWR)

        # ポインタの位置を初期化
        self.pointer = np.array([0, 0])
        self.home()

    def convert_to_screen_coordinate(self, point_image):
        sh, sw = self.screen_resolution
        iw, ih = self.image_resolution
        ix, iy = point_image
        sx = (ih - iy) / ih * sh
        sy = ix / iw * sw

        point_screen = np.array([sx, sy])

        return point_screen

    def convert_to_image_coordinate(self, point_screen):
        sh, sw = self.screen_resolution
        iw, ih = self.image_resolution
        sx, sy = point_screen

        ix = sy / sw * iw
        iy = (sh - sx) / sh * ih

        point_image = np.array([ix, iy])

        return point_image

    def move(self, destination_image_coordinate, debug_mode=False):
        # ポインタ移動量
        DISP_X = 2
        DISP_Y = 2

        # 目的位置と現在位置の差分からポインタ移動回数の
        destination = self.convert_to_screen_coordinate(destination_image_coordinate)
        distance = destination - self.pointer
        loop_x, loop_y = np.round(distance / self.pointer_resoltuion).astype("int")

        while not (loop_x == 0 and loop_y == 0):
            disp_x = np.sign(loop_x) * DISP_X
            disp_y = np.sign(loop_y) * DISP_Y

            data = (
                chr(0x00)  # Buton
                + chr(disp_x & 0xFF)  # カーソル 横方向 移動量 (-127~+127)
                + chr(disp_y & 0xFF)  # カーソル 縦方向 移動量 (-127~+127)
                + chr(0x00)
                + chr(0x00)
            )
            os.write(self.fd, data.encode("latin-1"))

            loop_x -= np.sign(loop_x)
            loop_y -= np.sign(loop_y)

        self.pointer = destination

        if debug_mode:
            print("move to: ", self.convert_to_image_coordinate(self.pointer))

    # ポインタの現在位置に関わらず、強制的に原点に移動する
    def home(self, debug_mode=False):
        # x方向に-127, y方向に127の移動
        data = chr(0x00) + chr(0x81) + chr(0x7F) + chr(0x00) + chr(0x00)
        os.write(self.fd, data.encode("latin-1"))

        # ポインタの現在位置をホームポジション（右下）に設定する
        h, w = self.screen_resolution
        self.pointer = np.array([0, w])

        if debug_mode:
            print("move to: home")

    def tap(self, debug_mode=False):
        time.sleep(0.1)
        # タップ
        data = chr(0x01) + chr(0x00) + chr(0x00) + chr(0x00) + chr(0x00)
        os.write(self.fd, data.encode("latin-1"))
        # 離す
        data = chr(0x00) + chr(0x00) + chr(0x00) + chr(0x00) + chr(0x00)
        os.write(self.fd, data.encode("latin-1"))
        time.sleep(0.1)
        if debug_mode:
            print("tap at: ", self.pointer)


# TouchControllerクラスのテスト
if __name__ == "__main__":
    # 画面制御のインスタンスを作成
    tc = TouchController()

    # ポインタを初期位置に戻す
    tc.home(debug_mode=True)
    time.sleep(0.5)

    # ポインタをイメージ座標系で3/4の位置に移動する
    pi = np.array([960, 540]) * 3 / 4
    # ps = tc.convert_to_screen_coordinate(pi)
    tc.move(pi, debug_mode=True)
    time.sleep(0.5)

    # ポインタをイメージ座標系で半分の位置に移動する
    pi = np.array([960, 540]) / 2
    # ps = tc.convert_to_screen_coordinate(pi)
    tc.move(pi, debug_mode=True)
    time.sleep(0.5)

    # ポインタをイメージ座標系で1/4の位置に移動する
    pi = np.array([960, 540]) / 4
    # ps = tc.convert_to_screen_coordinate(pi)
    tc.move(pi, debug_mode=True)
    time.sleep(0.5)

    # ポインタをイメージ座標系で最大の位置に移動する
    pi = np.array([960, 540])
    # ps = tc.convert_to_screen_coordinate(pi)
    tc.move(pi, debug_mode=True)
    time.sleep(0.5)

    # ポインタを初期位置に戻す
    tc.home(debug_mode=True)
    time.sleep(0.5)
