import os
import numpy as np
import time

# ポインタの現在位置はimage_resolutionで管理されることに注意
class TouchController:
    def __init__(
        self,
        image_resolution=np.array([960, 540]),
        display_resolution=np.array([300, 300]),
        device="/dev/hidg0",
    ):
        self.coeff = display_resolution / image_resolution

        # HIDにアクセスするファイルディスクリプタの作成
        self.fd = os.open(device, os.O_RDWR)

        # ポインタの位置を初期化
        self.home()

    def move(self, destination, debug_mode=False):
        # 目的位置と現在位置の差分から移動量を計算する
        diff_img_res = destination - self.pointer
        diff_dis_res = (diff_img_res * self.coeff).astype("int64")

        # 移動が完了するまで繰り返しポインタを動かす
        remain = diff_dis_res
        while np.count_nonzero(remain) > 0:
            remain = self.__move(remain)

        # 移動後のポインタ位置を保存する
        self.pointer += diff_img_res

        if debug_mode:
            print("move to: ", end="")
            print(self.pointer)

    # displacement分だけポインタを移動する
    # 戻り値：移動しきれなかった分
    def __move(self, displacement):
        # 移動分が上下限を超える場合はクリップ
        disp_x, disp_y = displacement.clip(-127, 127)
        data = (
            chr(0x00)  # Buton
            + chr(disp_x & 0xFF)  # カーソル 横方向 移動量 (-127~+127)
            + chr(disp_y & 0xFF)  # カーソル 縦方向 移動量 (-127~+127)
            + chr(0x00)
            + chr(0x00)
        )
        os.write(self.fd, data.encode("latin-1"))

        # 移動しきれなかった分を戻り値として返す
        remain = displacement - displacement.clip(-127, 127)
        return remain

    # ポインタの現在位置に関わらず、強制的に原点に移動する
    def home(self, debug_mode=False):
        # x方向に-127, y方向に-127の移動を3回繰り返す
        data = chr(0x00) + chr(0x81) + chr(0x81) + chr(0x00) + chr(0x00)
        os.write(self.fd, data.encode("latin-1"))
        os.write(self.fd, data.encode("latin-1"))
        os.write(self.fd, data.encode("latin-1"))

        # ポインタの現在位置を原点に設定する
        self.pointer = [0, 0]

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
            print("tap at: ", end="")
            print(self.pointer)


#    def __del__(self):
#        self.fd.close()
