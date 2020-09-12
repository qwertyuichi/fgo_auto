import cv2
import numpy as np
import time
import random
from enum import IntEnum
import itertools
import sys
from datetime import datetime
import serial


# キャプチャの設定
WINDOW_NAME = "rpiplay"
IMAGE_WIDTH = 960
IMAGE_HEIGHT = 540

# カードをタップする位置
ARQ_CARD_TAP_POSITION = np.array(
    [[875, 380], [680, 380], [485, 380], [290, 380], [95, 380]]
)  # Ars, Quick, Busterカードのタップする位置

NOBLE_PHANTASM_TAP_POSITION = np.array(
    [[653, 155], [483, 155], [313, 155]]
)  # 宝具カードのタップする位置

# 画面判別処理を中断するまでの回数
MAX_ERROR_COUNT = 500

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


class TouchController:
    def __init__(self):
        self.ser = serial.Serial("/dev/ttyUSB0", 115200, timeout=None)

    def __del__(self):
        self.ser.close()

    def send_message(self, message):
        self.ser.write(bytes(message, "UTF-8"))

    def home(self):
        self.send_message("HOME\n")

    def tap(self):
        self.send_message("TAP\n")

    def move(self, destination_image_coordinate):
        x, y = destination_image_coordinate
        message = "MOVE," + str(x) + "," + str(y) + "\n"
        self.send_message(message)


##### NPゲージ量の取得 #####
# 戻り値
#   NPゲージ量を表す配列(ndarray)
def get_np_gauge(image_color, debug_mode=False):
    NP_POSITION = [
        {"top_x": 598, "top_y": 508, "bottom_x": 698, "bottom_y": 510},
        {"top_x": 359, "top_y": 508, "bottom_x": 459, "bottom_y": 510},
        {"top_x": 121, "top_y": 508, "bottom_x": 221, "bottom_y": 510},
    ]  # NPゲージの座標
    THRESHOLD = 20  # 明度の閾値; 閾値以上のpixelはNPゲージのバーが伸びている
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

        # ゲージの画像幅が100pixelなので、閾値を下回ったindex値をそのままNPゲージ量とする
        for j in range(10, len(lightness)):  # 端部は暗くなるので、開始点近傍は無視
            # print(lightness[j])
            if lightness[j] <= THRESHOLD:
                f_np_max = False
                np_gauge[i] = j
                break
            elif j == len(lightness) - 1 and lightness[j] > THRESHOLD:
                # 最後まで閾値以下にならなければNPゲージ量MAX
                np_gauge[i] = 100

        if debug_mode:
            # 　NPゲージ部を抜き出した画像を保存
            cv2.imwrite("/debug/np_gauge_" + str(i + 1) + ".png", img_np)

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
    THRESHOLD = 0.90  # 一致度の閾値; 一致度の最大値がこの閾値以上であれば、テンプレートと一致しているとみなす
    ARTS_IMAGE_PATH = "./pict/arts.png"
    QUICK_IMAGE_PATH = "./pict/quick.png"
    BUSTER_IMAGE_PATH = "./pict/buster.png"
    CARD_POSITION = [
        {"top_x": 802, "top_y": 380, "bottom_x": 933, "bottom_y": 465},
        {"top_x": 607, "top_y": 380, "bottom_x": 738, "bottom_y": 465},
        {"top_x": 414, "top_y": 380, "bottom_x": 545, "bottom_y": 465},
        {"top_x": 224, "top_y": 380, "bottom_x": 355, "bottom_y": 465},
        {"top_x": 33, "top_y": 380, "bottom_x": 165, "bottom_y": 465},
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

    ### 1. 宝具を使用を検討 ###
    # NPゲージが100%以上のものがあれば宝具を使用する
    noble_phantasm_list = np.where(np_gauge >= 100)[0]
    if len(noble_phantasm_list) > 0:
        ### 1. 宝具使用 ###
        print("        宝具を使用します")
        # 宝具カードを選択する
        for i in noble_phantasm_list:
            print("            宝具カード" + str(i) + "を選択")
            tc.move(NOBLE_PHANTASM_TAP_POSITION[i])
            tc.tap()

        # 残りはランダムに通常カードを選択する
        if len(noble_phantasm_list) < 3:
            normal_card_list = random.sample(
                list(range(5)), 3 - len(noble_phantasm_list)
            )
            for i in normal_card_list:
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
        roi = {"top_x": 789, "top_y": 391, "bottom_x": 909, "bottom_y": 439}
        position = get_template_image_position(image_color, "attack", roi)
        if position is not None:
            phase = Phase.SKILL_SELECT
            print("    スキル選択画面に移行します")
        else:
            # 3. リザルト画面か否か
            roi = {"top_x": 0, "top_y": 0, "bottom_x": 960, "bottom_y": 270}
            position = get_template_image_position(image_color, "result", roi)
            if position is not None:
                phase = Phase.RESULT
                print("    リザルト画面に移行します")
            else:
                # 4. 連続出撃確認画面か否か
                roi = {"top_x": 562, "top_y": 392, "bottom_x": 700, "bottom_y": 452}
                position = get_template_image_position(image_color, "連続出撃", roi)
                if position is not None:
                    phase = Phase.END_PROCESS
                    print("    連続出撃選択画面に移行します")
                else:
                    # 5. サポート選択画面か否か
                    roi = {"top_x": 696, "top_y": 0, "bottom_x": 960, "bottom_y": 55}
                    position = get_template_image_position(image_color, "サポート選択", roi)
                    if position is not None:
                        phase = Phase.SUPPORTER_SELECT
                        print("    サポート選択画面に移行します")
                    else:
                        # いずれでもない場合
                        phase = Phase.OTHER

    return phase


# フェーズによって行動を決める
def select_action(phase, error_counter):
    if phase == Phase.SUPPORTER_SELECT:  # サポート選択画面の場合
        tap_position = get_template_image_position(image_color, "サポート選択")
        if tap_position is not None:
            # サポートの一番上のキャラクタを選択する
            tap_position = np.array([100, 200])
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
        tap_position = get_template_image_position(image_color, "attack")
        if tap_position is not None:
            # Attackボタンを選択する
            tc.move(tap_position)
            tc.tap()
            print("        Attackボタンを選択しました")

            # 次のフェーズをセット
            print("    カード選択画面へ移行します")
            phase = Phase.CARD_SELECT
            error_counter = 0
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
            print("        NPゲージ量を取得しました：", np.sort(np_gauge)[::-1])
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
            # "次へ"ボタンが現れる座標を3回タップする
            tap_position = np.array([850, 510])
            tc.move(tap_position)
            for i in range(5):
                tc.tap()
                time.sleep(2)

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
            time.sleep(3)
            print("        連続出撃ボタンを選択しました")

            # 次のフェーズをセット
            time.sleep(5)
            print("    サポート選択画面へ移行します")
            phase = Phase.SUPPORTER_SELECT
            error_counter = 0
        else:
            print("        連続出撃ボタンを認識できませんでした")
            phase = Phase.OTHER
    elif phase == Phase.OTHER:
        # フェーズが判別不明になったら画面判別処理へ移行する
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

    # キャプチャの初期設定
    video_source = cv2.VideoCapture(
        f"ximagesrc xname={WINDOW_NAME} ! videoconvert ! appsink"
    )

    # クエストのフェーズを初期化
    phase = Phase.OTHER
    try:
        error_counter = 0
        while cv2.waitKey(1) != 27:
            # ポインタを初期位置に戻す
            tc.home()

            # 画像をキャプチャ
            ret, image_original = video_source.read()

            if ret:
                # 画像をリサイズ
                image_color = cv2.resize(image_original, (IMAGE_WIDTH, IMAGE_HEIGHT))

                # キャプチャした画像を表示
                cv2.imshow("fgo_auto", image_color)

                # 次のアクションを決める
                phase, error_counter = select_action(phase, error_counter)

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
                        GPIO.cleanup()
                        sys.exit()
                        break

            time.sleep(1)

    except KeyboardInterrupt:
        print("プログラムを終了します")
        sys.exit()
