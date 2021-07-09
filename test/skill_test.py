import cv2
import numpy as np

SKILL_LETTER_POSITION = [
    [
        {"top_x": 27, "top_y": 449, "bottom_x": 53, "bottom_y": 462},
        {"top_x": 93, "top_y": 449, "bottom_x": 119, "bottom_y": 462},
        {"top_x": 159, "top_y": 449, "bottom_x": 185, "bottom_y": 462},
    ],
    [
        {"top_x": 264, "top_y": 449, "bottom_x": 290, "bottom_y": 462},
        {"top_x": 330, "top_y": 449, "bottom_x": 356, "bottom_y": 462},
        {"top_x": 396, "top_y": 449, "bottom_x": 422, "bottom_y": 462},
    ],
    [
        {"top_x": 503, "top_y": 449, "bottom_x": 528, "bottom_y": 462},
        {"top_x": 569, "top_y": 449, "bottom_x": 594, "bottom_y": 462},
        {"top_x": 635, "top_y": 449, "bottom_x": 660, "bottom_y": 462},
    ],
]  # スキルアイコンの"あと"の文字が表示される位置 → この文字が表示されていればスキル使用不可能として判定する


SKILL_ICON_TOP_FRAME = [
    [
        {"top_x": 34, "top_y": 409, "bottom_x": 77, "bottom_y": 412},
        {"top_x": 100, "top_y": 409, "bottom_x": 143, "bottom_y": 412},
        {"top_x": 166, "top_y": 409, "bottom_x": 209, "bottom_y": 412},
    ],
    [
        {"top_x": 272, "top_y": 409, "bottom_x": 315, "bottom_y": 412},
        {"top_x": 338, "top_y": 409, "bottom_x": 381, "bottom_y": 412},
        {"top_x": 404, "top_y": 409, "bottom_x": 447, "bottom_y": 412},
    ],
    [
        {"top_x": 510, "top_y": 409, "bottom_x": 553, "bottom_y": 412},
        {"top_x": 575, "top_y": 409, "bottom_x": 619, "bottom_y": 412},
        {"top_x": 642, "top_y": 409, "bottom_x": 685, "bottom_y": 412},
    ],
]  # スキルアイコン上部の白いライン → このラインが見えていればスキルアイコンが存在していると判定する

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


# 画像の読み込み
image_color = cv2.imread("./test/skill_sample_4.png")

# しきい値指定によるフィルタリング
# image_gray = cv2.cvtColor(image_color, cv2.COLOR_BGR2GRAY)
# _, image_binary = cv2.threshold(image_gray, 100, 255, cv2.THRESH_BINARY)


def check_skill_icon_existence(image_color, roi=None, debug_mode=False):
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


for i in range(3):
    for j in range(3):
        check_skill_icon_existence(image_color, SKILL_ICON_TOP_FRAME[i][j])
"""
for i in range(3):
    for j in range(3):
        pos = get_template_image_position(
            image_color, "あと", SKILL_LETTER_POSITION[i][j], False
        )
        if pos is None:
            # "あと"の文字が見つからなければ、スキル使用可能
            print(True)
        else:
            print(False)
"""

"""
# スキルアイコンの最上段のライン
# → このラインが明るければスキル使用可能、暗ければスキル使用不可能として判定する
SKILL_ICON_TOP_LINE = [
    [
        {"top_x": 34, "top_y": 413, "bottom_x": 77, "bottom_y": 414},
        {"top_x": 100, "top_y": 413, "bottom_x": 143, "bottom_y": 414},
        {"top_x": 166, "top_y": 413, "bottom_x": 209, "bottom_y": 414},
    ],
    [
        {"top_x": 272, "top_y": 413, "bottom_x": 315, "bottom_y": 414},
        {"top_x": 338, "top_y": 413, "bottom_x": 381, "bottom_y": 414},
        {"top_x": 404, "top_y": 413, "bottom_x": 447, "bottom_y": 414},
    ],
    [
        {"top_x": 510, "top_y": 413, "bottom_x": 553, "bottom_y": 414},
        {"top_x": 575, "top_y": 413, "bottom_x": 619, "bottom_y": 414},
        {"top_x": 642, "top_y": 413, "bottom_x": 685, "bottom_y": 414},
    ],
]


# スキルアイコンの位置
SKILL_ICON__POSITION = [
    [
        {"top_x": 34, "top_y": 413, "bottom_x": 77, "bottom_y": 456},
        {"top_x": 100, "top_y": 413, "bottom_x": 143, "bottom_y": 456},
        {"top_x": 166, "top_y": 413, "bottom_x": 209, "bottom_y": 456},
    ],
    [
        {"top_x": 272, "top_y": 413, "bottom_x": 315, "bottom_y": 456},
        {"top_x": 338, "top_y": 413, "bottom_x": 381, "bottom_y": 456},
        {"top_x": 404, "top_y": 413, "bottom_x": 447, "bottom_y": 456},
    ],
    [
        {"top_x": 510, "top_y": 413, "bottom_x": 553, "bottom_y": 456},
        {"top_x": 575, "top_y": 413, "bottom_x": 619, "bottom_y": 456},
        {"top_x": 642, "top_y": 413, "bottom_x": 685, "bottom_y": 456},
    ],
]

# スキルアイコンに表示される数値の位置
SKILL_NUMBER_POSITION = [
    [
        {"top_x": 69, "top_y": 443, "bottom_x": 80, "bottom_y": 460},
        {"top_x": 135, "top_y": 443, "bottom_x": 146, "bottom_y": 460},
        {"top_x": 201, "top_y": 443, "bottom_x": 212, "bottom_y": 460},
    ],
    [
        {"top_x": 307, "top_y": 443, "bottom_x": 318, "bottom_y": 460},
        {"top_x": 373, "top_y": 443, "bottom_x": 384, "bottom_y": 460},
        {"top_x": 439, "top_y": 443, "bottom_x": 450, "bottom_y": 460},
    ],
    [
        {"top_x": 545, "top_y": 443, "bottom_x": 556, "bottom_y": 460},
        {"top_x": 610, "top_y": 443, "bottom_x": 622, "bottom_y": 460},
        {"top_x": 677, "top_y": 443, "bottom_x": 688, "bottom_y": 460},
    ],
]
"""

"""
# 画像の読み込み
image_color_1 = cv2.imread("./skill_sample_1.png")
image_color_2 = cv2.imread("./skill_sample_2.png")

# キャプチャ画像のグレースケール化
image_gray_1 = cv2.cvtColor(image_color_1, cv2.COLOR_BGR2GRAY)
image_gray_2 = cv2.cvtColor(image_color_2, cv2.COLOR_BGR2GRAY)

for pos_array in SKILL_ICON_POSITION:
    for roi in pos_array:
        print(roi)


        # ROIの設定
        icon_1 = image_gray_1[
            # roi["top_y"] : roi["bottom_y"], roi["top_x"] : roi["bottom_x"]
            roi["top_y"] : roi["top_y"],
            roi["top_x"] : roi["bottom_x"],
        ]
        icon_2 = image_gray_2[
            # roi["top_y"] : roi["bottom_y"], roi["top_x"] : roi["bottom_x"]
            roi["top_y"] : roi["top_y"],
            roi["top_x"] : roi["bottom_x"],
        ]

        # 輝度の平均値
        print("輝度平均値（スキル使用前）：", np.mean(icon_1))
        print("輝度平均値（スキル使用後）：", np.mean(icon_2))

        # cv2.imshow("icon_1", icon_1)
        # cv2.imshow("icon_2", icon_2)
        # cv2.waitKey(100000)
"""

"""
def get_skill_availability(image_color, roi=None, debug_mode=False):
    THRESHOLD = 200  # 平均輝度の閾値; 平均輝度がこの閾値以上であれば、スキルが使用可能であるとみなす

    # キャプチャ画像のグレースケール化
    image_gray = cv2.cvtColor(image_color, cv2.COLOR_BGR2GRAY)

    # ROIの設定
    if roi is not None:
        image_gray = image_gray[
            roi["top_y"] : roi["bottom_y"], roi["top_x"] : roi["bottom_x"]
        ]

        mean_brightness = np.mean(image_gray)
        if mean_brightness > THRESHOLD:
            return True
        else:
            return False


image_color = cv2.imread("./skill_sample_3.png")
for pos_array in SKILL_ICON_TOP_LINE:
    for roi in pos_array:
        print(roi)
        print(get_skill_availability(image_color, roi))
"""
