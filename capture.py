import cv2

# キャプチャの設定
WINDOW_NAME = "rpiplay"
WINDOW_ID = "0x2a00002"
WINDOW_WIDTH = 1728#2532
WINDOW_HEIGHT = 798#1170
IMAGE_WIDTH = 1823  # 960
IMAGE_HEIGHT = 842  # 540


if __name__ == "__main__":

    # キャプチャの初期設定
    video_source = cv2.VideoCapture(
        # f"ximagesrc xname={WINDOW_NAME} ! videoconvert ! videoscale ! video/x-raw,width={WINDOW_WIDTH},height={WINDOW_HEIGHT} ! appsink"
        f"ximagesrc xid={WINDOW_ID} ! videoconvert ! videoscale ! video/x-raw,width={WINDOW_WIDTH},height={WINDOW_HEIGHT} ! appsink"
    )

    # while cv2.waitKey(1) != 27:
    # 画像を所定のサイズでキャプチャ
    ret, image = video_source.read()

    if ret:
        image = cv2.resize(image, (IMAGE_WIDTH, IMAGE_HEIGHT))

        # 画像の大きさを取得
        """
        height, width, channels = image.shape[:3]
        print("width: " + str(width))
        print("height: " + str(height))
        """

        # キャプチャした画像を表示
        # cv2.imshow("fgo_auto", image)
        cv2.imwrite("./debug/capture.png", image)
        cv2.waitKey(1)
    else:
        print("キャプチャできませんでした")
