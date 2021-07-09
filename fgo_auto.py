import cv2
import numpy as np
import time
import random
from enum import IntEnum
import itertools
import sys
from datetime import datetime
import serial
import threading

import matplotlib.pyplot as plt

# キャプチャの設定
WINDOW_NAME = "rpiplay"
WINDOW_ID = "0x1e00002"
WINDOW_WIDTH = 2532  # 1920
WINDOW_HEIGHT = 1170  # 1080
IMAGE_WIDTH = 1823  # 960
IMAGE_HEIGHT = 842  # 540

# カードをタップする位置
ARQ_CARD_TAP_POSITION = np.array(
    [[1525, 552], [1211, 552], [911, 552], [615, 552], [310, 552]]
)  # Ars, Quick, Busterカードのタップする位置

NOBLE_PHANTASM_TAP_POSITION = np.array(
    [[1186, 215], [911, 215], [647, 215]]
)  # 宝具カードのタップする位置

SKILL_ICON_TAP_POSITION = np.array(
    [
        [[885, 652], [988, 652], [1094, 652]],
        [[512, 652], [617, 652], [721, 652]],
        [[142, 652], [248, 652], [354, 652]],
    ]
)  # スキルアイコンのタップする位置

SKILL_LETTER_POSITION = [
    [
        {"top_x": 847, "top_y": 677, "bottom_x": 882, "bottom_y": 694},
        {"top_x": 950, "top_y": 677, "bottom_x": 985, "bottom_y": 694},
        {"top_x": 1053, "top_y": 677, "bottom_x": 1088, "bottom_y": 694},
    ],
    [
        {"top_x": 476, "top_y": 677, "bottom_x": 510, "bottom_y": 694},
        {"top_x": 579, "top_y": 677, "bottom_x": 613, "bottom_y": 694},
        {"top_x": 682, "top_y": 677, "bottom_x": 716, "bottom_y": 694},
    ],
    [
        {"top_x": 104, "top_y": 677, "bottom_x": 139, "bottom_y": 694},
        {"top_x": 207, "top_y": 677, "bottom_x": 242, "bottom_y": 694},
        {"top_x": 310, "top_y": 677, "bottom_x": 345, "bottom_y": 694},
    ],
]  # スキルアイコンの"あと"の文字が表示される位置 → この文字が表示されていればスキル使用不可能として判定する

SKILL_ICON_TOP_FRAME = [
    [
        {"top_x": 854, "top_y": 614, "bottom_x": 922, "bottom_y": 616},
        {"top_x": 957, "top_y": 614, "bottom_x": 1025, "bottom_y": 616},
        {"top_x": 1060, "top_y": 614, "bottom_x": 1128, "bottom_y": 616},
    ],
    [
        {"top_x": 482, "top_y": 614, "bottom_x": 551, "bottom_y": 616},
        {"top_x": 585, "top_y": 614, "bottom_x": 654, "bottom_y": 616},
        {"top_x": 688, "top_y": 614, "bottom_x": 757, "bottom_y": 616},
    ],
    [
        {"top_x": 111, "top_y": 614, "bottom_x": 179, "bottom_y": 616},
        {"top_x": 214, "top_y": 614, "bottom_x": 282, "bottom_y": 616},
        {"top_x": 317, "top_y": 614, "bottom_x": 385, "bottom_y": 616},
    ],
]  # スキルアイコン上部の白いライン → このラインが見えていればスキルアイコンが存在していると判定する

# 画面判別処理を中断するまでの回数
MAX_ERROR_COUNT = 5000

# カード種別
class Card(IntEnum):
    UNKNOWN = -1
    ARTS = 0
    QUICK = 1
    BUSTER = 2


# 画面種別
class Phase(IntEnum):
    OTHER = -1  # その他（判別不能の場合）
    SUPPORTER_SELECT = 0  # サポート選択画面
    SKILL_SELECT = 1  # スキル選択画面
    CARD_SELECT = 2  # カード選択画面
    RESULT = 3  # リザルト画面
    END_PROCESS = 4  # 連続出撃の選択画面
    USE_APPLE = 5  # 連続出撃の選択画面


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
        time.sleep(0.1)


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
                # w = 100
                # self.image_color = image_original[:, w : 2532 - w]
                # キャプチャした画像をリサイズして更新
                self.image_color = cv2.resize(
                    image_original, (IMAGE_WIDTH, IMAGE_HEIGHT)
                )
                # self.image_color = cv2.resize(
                #    self.image_color, (IMAGE_WIDTH, IMAGE_HEIGHT)
                # )

                # キャプチャした画像を表示
                cv2.imshow("fgo_auto", self.image_color)
                cv2.waitKey(1)

    def get_image(self):
        return self.image_color


##### NPゲージ量の取得 #####
# 戻り値
#   NPゲージ量を表す配列(ndarray)
def get_np_gauge(image_color, debug_mode=False):
    NP_POSITION = [
        {"top_x": 988, "top_y": 769, "bottom_x": 1144, "bottom_y": 775},
        {"top_x": 617, "top_y": 769, "bottom_x": 773, "bottom_y": 775},
        {"top_x": 246, "top_y": 769, "bottom_x": 402, "bottom_y": 775},
    ]  # NPゲージの座標
    NP_BRIGHTNESS_THRESHOLD = 6  # 明度の閾値; 閾値以上のpixelはNPゲージのバーが伸びている
    np_gauge = np.array([0, 0, 0])

    if debug_mode:
        fig = plt.figure()

    # キャプチャ画像のグレースケール化
    image_gray = cv2.cvtColor(image_color, cv2.COLOR_BGR2GRAY)

    # NPゲージ量を求める
    for i in range(3):
        img_np = image_gray[
            NP_POSITION[i]["top_y"] : NP_POSITION[i]["bottom_y"],
            NP_POSITION[i]["top_x"] : NP_POSITION[i]["bottom_x"],
        ]

        # 明度の平均値を求める
        lightness = np.mean(img_np, axis=0)

        # ゲージの画像幅が158pixelなので、閾値を下回ったindex値を元にNPゲージ量を算出する
        gauge_length = NP_POSITION[i]["bottom_x"] - NP_POSITION[i]["top_x"]
        for j in range(10, len(lightness)):  # 端部は暗くなるので、開始点近傍は無視
            # print(lightness[j])
            if lightness[j] <= NP_BRIGHTNESS_THRESHOLD:
                f_np_max = False
                np_gauge[i] = int(100 * j / 158)
                break
            elif j == len(lightness) - 1 and lightness[j] > NP_BRIGHTNESS_THRESHOLD:
                # 最後まで閾値以下にならなければNPゲージ量MAX
                np_gauge[i] = 100

        if debug_mode:
            # 　NPゲージ部を抜き出した画像を保存
            cv2.imwrite("./debug/np_gauge_" + str(i + 1) + ".png", img_np)

            # 明度の平均値をプロット
            plt.plot(lightness, label="NP gauge " + str(i + 1))
            plt.legend(
                bbox_to_anchor=(1, 1), loc="upper right", borderaxespad=0, fontsize=18
            )

    if debug_mode:
        fig.savefig("./debug/np_gauge_lightness.png")
        print(np_gauge)

    return np_gauge


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


##### BRAVE CHAINができる組を取得する #####
def get_brave_chain_combination(image_color, debug_mode=False):
    THRESHOLD = 0.9  # 一致度の閾値; 一致度の最大値がこの閾値以上であれば、比較対象の画像と一致しているとみなす
    CHARACTOR_POSITION = [
        {"top_x": 802, "top_y": 300, "bottom_x": 933, "bottom_y": 380},
        {"top_x": 607, "top_y": 300, "bottom_x": 738, "bottom_y": 380},
        {"top_x": 414, "top_y": 300, "bottom_x": 545, "bottom_y": 380},
        {"top_x": 224, "top_y": 300, "bottom_x": 355, "bottom_y": 380},
        {"top_x": 33, "top_y": 300, "bottom_x": 164, "bottom_y": 380},
    ]  # 各カードの認識範囲

    # キャプチャ画像のグレースケール化
    image_gray = cv2.cvtColor(image_color, cv2.COLOR_BGR2GRAY)

    # キャラクタの画像を切り抜いてリスト化
    img_chara_list = []
    for i in range(5):
        img_chara_list.append(
            image_gray[
                CHARACTOR_POSITION[i]["top_y"] : CHARACTOR_POSITION[i]["bottom_y"],
                CHARACTOR_POSITION[i]["top_x"] : CHARACTOR_POSITION[i]["bottom_x"],
            ]
        )

    # カード3枚を比較する組み合わせパターンを作成する
    index_list = (0, 1, 2, 3, 4)
    combination_list = list(itertools.combinations(index_list, 3))

    # 各組み合わせパターンごとに類似度を計算
    chain_combination = None
    for combination in combination_list:
        similarity_score = np.array([])
        for c in list(itertools.combinations(combination, 2)):
            # テンプレートマッチングのターゲットとテンプレートを作成
            img_target = img_chara_list[c[0]]
            temp_w, temp_h = img_chara_list[c[1]].shape[::-1]
            img_template = img_chara_list[c[1]][
                int(temp_h * 0.2) : int(temp_h * 0.8),
                int(temp_w * 0.2) : int(temp_w * 0.8),
            ]

            # テンプレートマッチング処理
            ret = cv2.matchTemplate(img_target, img_template, cv2.TM_CCOEFF_NORMED)
            _, max_coeff, _, _ = cv2.minMaxLoc(ret)

            # 相関係数の最大値を類似度のスコアとして記録
            similarity_score = np.append(similarity_score, max_coeff)

        # 類似度のスコアがすべて閾値より高い組み合わせがあればBRAVE CHAINできる組として記録する
        if np.all([similarity_score > THRESHOLD]):
            chain_combination = combination

            # デバッグモードでなければBRAVE CHAINできる組を見つけた段階で処理を打ち切る
            if not debug_mode:
                break

        if debug_mode:
            # 計算結果の表示
            print(combination, similarity_score, np.all([similarity_score > THRESHOLD]))

            # 比較に使用した画像を保存
            for i in range(5):
                cv2.imwrite(
                    "./debug/img_chara_list[" + str(i) + "].png", img_chara_list[i]
                )

    return chain_combination


##### カード種別を取得する ####
def get_card_type(image_color, debug_mode=False):
    THRESHOLD = 0.80  # 一致度の閾値; 一致度の最大値がこの閾値以上であれば、テンプレートと一致しているとみなす
    ARTS_IMAGE_PATH = "./pict/arts.png"
    QUICK_IMAGE_PATH = "./pict/quick.png"
    BUSTER_IMAGE_PATH = "./pict/buster.png"
    CARD_POSITION = [
        {"top_x": 1420, "top_y": 450, "bottom_x": 1600, "bottom_y": 700},
        {"top_x": 1120, "top_y": 450, "bottom_x": 1300, "bottom_y": 700},
        {"top_x": 820, "top_y": 450, "bottom_x": 1000, "bottom_y": 700},
        {"top_x": 520, "top_y": 450, "bottom_x": 700, "bottom_y": 700},
        {"top_x": 220, "top_y": 450, "bottom_x": 400, "bottom_y": 700},
    ]  # 各カードの認識範囲
    card_type = np.full(5, Card.UNKNOWN)

    # テンプレートの読み込み
    template = np.array(
        [
            cv2.imread(ARTS_IMAGE_PATH, 0),
            cv2.imread(QUICK_IMAGE_PATH, 0),
            cv2.imread(BUSTER_IMAGE_PATH, 0),
        ]
    )

    # キャプチャ画像のグレースケール化
    image_gray = cv2.cvtColor(image_color, cv2.COLOR_BGR2GRAY)

    for i in range(5):
        img_card = image_gray[
            CARD_POSITION[i]["top_y"] : CARD_POSITION[i]["bottom_y"],
            CARD_POSITION[i]["top_x"] : CARD_POSITION[i]["bottom_x"],
        ]

        # テンプレートマッチング処理
        card_dict = {"arts": 0, "quick": 1, "buster": 2}
        for card_index in range(3):
            result = cv2.matchTemplate(
                img_card, template[card_index], cv2.TM_CCOEFF_NORMED
            )
            _, max_coeff, _, _ = cv2.minMaxLoc(result)
            if max_coeff > THRESHOLD:
                card_type[i] = card_index
                break

    if debug_mode:
        print(card_type)
        print(
            "?:",
            np.count_nonzero(card_type == Card.UNKNOWN),
            ", A:",
            np.count_nonzero(card_type == Card.ARTS),
            ", Q:",
            np.count_nonzero(card_type == Card.QUICK),
            ", B:",
            np.count_nonzero(card_type == Card.BUSTER),
        )
    return card_type


##### ARTS, QUICK, BUSTER CHAINができる組を取得する #####
# 戻り値
#   チェイン種別
#   チェイン成立の組を表す配列(ndarray)
# 備考
#   チェイン種別はカード種別と同一番号（番号はCardクラスを参照）
def get_aqb_chain_combination(card_type, debug_mode=False):
    # 判別不可能なカードが3枚以上ある場合はCHAIN不可としてNoneを返す
    if np.count_nonzero(card_type == Card.UNKNOWN) >= 3:
        return (None, None)

    # ARTS, QUICK, BUSTERのいずれかが3枚以上あれば、種別とその組を返す
    # chain_combination = np.array([])
    for chain_type in range(3):
        if np.count_nonzero(card_type == chain_type) >= 3:
            result = (chain_type, np.where(card_type == chain_type)[0])
            if debug_mode:
                print(result)
            return result

    # CHAIN不可ならNoneを返す
    return (None, None)


# カード選択画面での行動を決める
def select_card(np_gauge, card_type):
    # カード選択画面であることが確定したら下記の優先順で戦略を取る
    # 1. 宝具使用
    # 2. Arts, Quick, Busterチェイン使用
    # 3. Braveチェイン使用
    # 4. ランダム選択

    ### 1. 宝具を使用可否を検証 ###
    # NPゲージが100%以上のものがあれば宝具を使用する
    noble_phantasm_list = np.where(np_gauge >= 100)[0]
    if len(noble_phantasm_list) > 0:
        ### 1. 宝具使用 ###
        print("        宝具を使用します")
        # 宝具カードを選択する
        time.sleep(1)  # 宝具カードが選択可能になるまでのウェイト
        for i in noble_phantasm_list:
            print("            宝具カード" + str(i) + "を選択")
            tc.move(NOBLE_PHANTASM_TAP_POSITION[i])
            tc.tap()

        """
        # 残りはランダムに通常カードを選択する
        if len(noble_phantasm_list) < 3:
            normal_card_list = random.sample(
                list(range(5)), 3 - len(noble_phantasm_list)
            )
            for i in normal_card_list:
                print("            通常カード" + str(i) + "を選択")
                tc.move(ARQ_CARD_TAP_POSITION[i])
                tc.tap()
        """
        # 通常カードは全部タップする（宝具封印対策）
        for i in range(5):
            print("            通常カード" + str(i) + "を選択")
            tc.move(ARQ_CARD_TAP_POSITION[i])
            tc.tap()
    else:
        ### 2. Arts, Quick, Busterチェイン使用を検討 ###
        chain_type, combination = get_aqb_chain_combination(card_type)
        if chain_type is not None:
            ### 2. Arts, Quick, Busterチェイン使用 ###
            chain_name = {0: "Arts", 1: "Quick", 2: "Buster"}
            print("        " + chain_name[chain_type] + "チェインを使用します")
            for i in combination:
                print("            通常カード" + str(i) + "を選択")
                tc.move(ARQ_CARD_TAP_POSITION[i])
                tc.tap()
        else:
            ### 3. Braveチェイン使用を検討 ###
            combination = get_brave_chain_combination(image_color)
            if combination is not None:
                ### 3. Braveチェイン使用 ###
                print("        Braveチェインを使用します")
                for i in combination:
                    print("            通常カード" + str(i) + "を選択")
                    tc.move(ARQ_CARD_TAP_POSITION[i])
                    tc.tap()
            else:
                ### 4. ランダム選択 ###
                print("        通常カードをランダム選択します")
                normal_card_list = random.sample(list(range(5)), 3)
                for i in sorted(normal_card_list):
                    print("            通常カード" + str(i) + "を選択")
                    tc.move(ARQ_CARD_TAP_POSITION[i])
                    tc.tap()


# スキルアイコンが存在するかを判定する
def check_skill_icon_existence(image_color, roi=None):
    THRESHOLD = 200  # 平均輝度の閾値; 平均輝度がこの閾値以上であれば、スキルアイコンが存在しているとみなす

    # キャプチャ画像のグレースケール化
    image_gray = cv2.cvtColor(image_color, cv2.COLOR_BGR2GRAY)

    # ROIの設定
    if roi is not None:
        image_gray = image_gray[
            roi["top_y"] : roi["bottom_y"], roi["top_x"] : roi["bottom_x"]
        ]

        mean_brightness = np.max(np.mean(image_gray, axis=1))
        if mean_brightness > THRESHOLD:
            return True
        else:
            return False
    else:
        return False


# 利用可能なスキルを見つけて発動する
def use_available_skills(image_color, debug_mode=False):
    for i in range(3):
        for j in range(3):
            pos = get_template_image_position(
                image_color, "あと", SKILL_LETTER_POSITION[i][j], debug_mode
            )
            if pos is None:

                skill_icon_existence = check_skill_icon_existence(
                    image_color, SKILL_ICON_TOP_FRAME[i][j]
                )

                # スキルアイコンの存在が確認できた上、"あと"の文字が見つからなければ、スキル使用可能
                if skill_icon_existence:
                    print("サーヴァント", i + 1, "の第", j + 1, "スキルを使用します")
                    # cv2.imwrite("./debug/capture.png", image_color)
                    tc.move(SKILL_ICON_TAP_POSITION[i][j])
                    tc.tap()
                    # time.sleep(0.2)
                    tc.move(np.array([920, 500]))  # 真ん中のサーヴァントを選択
                    tc.tap()
                    # time.sleep(0.2)
                    tc.move(np.array([550, 500]))  # 2人しかいないとき→左側のサーヴァントを選択
                    tc.tap()
                    # time.sleep(0.2)
                    tc.move(np.array([1280, 500]))  # 2人しかいないとき→右側のサーヴァントを選択
                    tc.tap()
                    tc.home()
                    time.sleep(2)

                    return False
                else:
                    print("サーヴァント", i + 1, "の第", j + 1, "スキルのアイコンが見つかりません")

    # これ以上使えるスキルはない判定
    return True


def get_game_phase(image_color, debug_mode=False):
    # 現在のフェーズがわからなければ、下記の優先順位で確認する
    # 1. カード選択画面
    # 2. スキル選択画面
    # 3. リザルト画面
    # 4. 連続出撃確認画面
    # 5. サポート選択画面

    phase = Phase.OTHER

    # 1. カード選択画面か否か
    card_type = get_card_type(image_color)
    if np.count_nonzero(card_type == Card.UNKNOWN) <= 2:
        # 判別不能カードが2枚以下であればカードが識別できたものとする
        phase = Phase.CARD_SELECT
        print("    カード選択画面に移行します")

    else:
        # 2. スキル選択画面か否か
        # roi = {"top_x": 789, "top_y": 391, "bottom_x": 909, "bottom_y": 439}
        # position = get_template_image_position(image_color, "attack", roi)
        position = get_template_image_position(image_color, "attack")
        if position is not None:
            phase = Phase.SKILL_SELECT
            print("    スキル選択画面に移行します")
        else:
            # 3. リザルト画面か否か
            # roi = {"top_x": 0, "top_y": 0, "bottom_x": 960, "bottom_y": 270}
            # position = get_template_image_position(image_color, "result", roi)
            position = get_template_image_position(image_color, "result")
            if position is not None:
                phase = Phase.RESULT
                print("    リザルト画面に移行します")
            else:
                # 4. 連続出撃確認画面か否か
                # roi = {"top_x": 562, "top_y": 392, "bottom_x": 700, "bottom_y": 452}
                # position = get_template_image_position(image_color, "連続出撃", roi)
                position = get_template_image_position(image_color, "連続出撃")
                if position is not None:
                    phase = Phase.END_PROCESS
                    print("    連続出撃選択画面に移行します")
                else:
                    # 5. サポート選択画面か否か
                    # roi = {"top_x": 696, "top_y": 0, "bottom_x": 960, "bottom_y": 55}
                    # position = get_template_image_position(image_color, "サポート選択", roi)
                    position = get_template_image_position(image_color, "サポート選択")
                    if position is not None:
                        phase = Phase.SUPPORTER_SELECT
                        print("    サポート選択画面に移行します")
                    else:
                        # 5. 黄金の果実を使用する場面か
                        golden_apple_position = get_template_image_position(
                            image_color, "golden_apple"
                        )
                        silver_apple_position = get_template_image_position(
                            image_color, "silver_apple"
                        )
                        if (
                            golden_apple_position is not None
                            or silver_apple_position is not None
                        ):
                            phase = Phase.USE_APPLE
                            print("    黄金の果実を使用します")
                        else:
                            # いずれでもない場合
                            phase = Phase.OTHER

    return phase


# フェーズによって行動を決める
def select_action(phase, error_counter, image_color):
    if phase == Phase.SUPPORTER_SELECT:  # サポート選択画面の場合
        tap_position = get_template_image_position(image_color, "サポート選択")
        if tap_position is not None:
            # サポートの一番上のキャラクタを選択する
            tap_position = np.array([326, 326])
            tc.move(tap_position)
            tc.tap()
            print("        サポートを選択しました")

            # 次のフェーズをセット
            time.sleep(10)
            print("    スキル選択画面へ移行します")
            phase = Phase.SKILL_SELECT
            error_counter = 0
        else:
            print("       サポート選択を認識できませんでした")
            phase = Phase.OTHER
    elif phase == Phase.SKILL_SELECT:  # スキル選択画面の場合

        # "Attack"ボタンがあればスキル選択画面として判定する
        tap_position = get_template_image_position(image_color, "attack")
        if tap_position is not None:
            # 利用可能なスキルがあれば全て使用する
            no_skill_available = use_available_skills(image_color, debug_mode=False)
            # no_skill_available = True

            # 使えるスキルがなければAttackボタンを選択する
            if no_skill_available:

                tc.move(tap_position)
                tc.tap()
                tc.home()
                print("        Attackボタンを選択しました")

                # 次のフェーズをセット
                print("    カード選択画面へ移行します")
                phase = Phase.CARD_SELECT
                error_counter = 0
                time.sleep(0.5)
        else:
            print("        Attackボタンを認識できませんでした")
            phase = Phase.OTHER

            date = datetime.now().strftime("%Y%m%d_%H%M%S")
            path = "./debug/" + date + ".png"
            print("保存しました：" + path)
            cv2.imwrite(path, image_color)  # ファイル保存

    elif phase == Phase.CARD_SELECT:  # カード選択画面の場合
        card_type = get_card_type(image_color)
        if np.count_nonzero(card_type == Card.UNKNOWN) <= 2:
            # NPゲージ量を取得する
            np_gauge = get_np_gauge(image_color)
            # print("        NPゲージ量を取得しました：", np.sort(np_gauge)[::-1])
            print("        NPゲージ量を取得しました：", np_gauge[::-1])
            # 下記の優先順で戦略を取る
            # 1. 宝具使用
            # 2. Arts, Quick, Busterチェイン使用
            # 3. Braveチェイン使用
            # 4. ランダム選択
            select_card(np_gauge, card_type)

            # 次のフェーズをセット
            # リザルト画面かスキル選択画面かわからないので画面判別処理へ入る
            phase = Phase.OTHER
            error_counter = 0
        else:
            print("        カードを認識できませんでした")
            phase = Phase.OTHER
    elif phase == Phase.RESULT:
        tap_position = get_template_image_position(image_color, "result")
        if tap_position is not None:
            # "次へ"ボタンが現れる座標を5回タップする
            tap_position = np.array([1452, 748])
            tc.move(tap_position)
            for i in range(5):
                tc.tap()
                time.sleep(1)

            # 次のフェーズをセット
            phase = Phase.END_PROCESS
            error_counter = 0
        else:
            print("        リザルト画面を認識できませんでした")
            phase = Phase.OTHER
    elif phase == Phase.END_PROCESS:
        tap_position = get_template_image_position(image_color, "連続出撃")
        if tap_position is not None:
            # 連続出撃ボタンを選択する
            tc.move(tap_position)
            tc.tap()
            time.sleep(1)
            print("        連続出撃ボタンを選択しました")

            # 次のフェーズをセット
            # 黄金の果実を選択するか、サポート選択画面へ移行するかがわからないので、OTHERをセット
            phase = Phase.OTHER
            error_counter = 0
        else:
            print("        連続出撃ボタンを認識できませんでした")
            phase = Phase.OTHER

    elif phase == Phase.USE_APPLE:
        # 果実の選択画面であることを確認する
        golden_apple_position = get_template_image_position(image_color, "golden_apple")
        silver_apple_position = get_template_image_position(image_color, "silver_apple")

        if golden_apple_position is not None or silver_apple_position is not None:
            # (760,400)をタップする
            tap_position = np.array([1346, 615])
            tc.move(tap_position)
            tc.tap()

            # 画面を更新する
            image_color = sc.get_image()

            # 黄金の果実/白銀の果実/赤銅の果実を使用する
            golden_apple_position = get_template_image_position(
                image_color, "golden_apple"
            )
            silver_apple_position = get_template_image_position(
                image_color, "silver_apple"
            )
            # bronze_apple_position = get_template_image_position(
            #    image_color, "bronze_apple"
            # )

            if golden_apple_position is not None:
                # 黄金の果実を選択する
                tc.move(golden_apple_position)
                tc.tap()
                time.sleep(0.1)
            if silver_apple_position is not None:
                # 白銀の果実を選択する
                tc.move(silver_apple_position)
                tc.tap()
                time.sleep(0.1)
            # if bronze_apple_position is not None:
            #    # 赤銅の果実を選択する
            #    tc.move(bronze_apple_position)
            #    tc.tap()
            #    time.sleep(0.1)

            # "決定"ボタンが現れる座標をタップする
            tap_position = np.array([1146, 660])
            tc.move(tap_position)
            tc.tap()
            print("        APを回復しました")

            # 次のフェーズをセット
            time.sleep(4)
            print("    サポート選択画面へ移行します")
            phase = Phase.SUPPORTER_SELECT
            error_counter = 0
        else:
            tap_position = None
            phase = Phase.OTHER
    elif phase == Phase.OTHER:
        # 何かウィンドウが開いていてスタックしている？
        # → 閉じるボタンを探してタップする
        tap_position = get_template_image_position(image_color, "close")
        if tap_position is not None:
            tc.move(tap_position)
            tc.tap()
        else:
            # フェーズが判別不明になった
            # → 画面判別処理へ移行する
            if error_counter == 0:
                print("画面判別処理中... ( 1 /", MAX_ERROR_COUNT, ")")
            else:
                print(
                    "\033[1A\033[2K\033[G画面判別処理中... (",
                    error_counter + 1,
                    "/",
                    MAX_ERROR_COUNT,
                    ")",
                )

            phase = get_game_phase(image_color, True)
            error_counter += 1

    return phase, error_counter


if __name__ == "__main__":
    # 画面制御のインスタンスを作成
    tc = TouchController()

    # 画面キャプチャのインスタンスを生成
    sc = ScreenCapture()
    sc.start()
    time.sleep(1)

    # クエストのフェーズを初期化
    phase = Phase.OTHER
    try:
        error_counter = 0
        # while cv2.waitKey(1) != 27:
        while True:
            # ポインタを初期位置に戻す
            tc.home()

            # 画像をキャプチャ
            image_color = sc.get_image()
            # cv2.imwrite("./debug/capture.png", image_color)

            # 次のアクションを決める
            phase, error_counter = select_action(phase, error_counter, image_color)

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
