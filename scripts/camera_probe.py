import os
import time
from pathlib import Path
import cv2

CAMERA_IP = os.getenv("CAMERA_IP", "192.168.8.253")
CAMERA_USER = os.getenv("CAMERA_USER", "admin")
CAMERA_PASSWORD = os.getenv("CAMERA_PASSWORD")

if not CAMERA_PASSWORD:
    raise SystemExit("请先设置环境变量 CAMERA_PASSWORD")

# 摄像头RTSP地址列表
urls = [
    f"rtsp://{CAMERA_USER}:{CAMERA_PASSWORD}@{CAMERA_IP}:10554/tcp/av0_0",
    f"rtsp://{CAMERA_USER}:{CAMERA_PASSWORD}@{CAMERA_IP}:10554/tcp/av0_1",
    f"rtsp://{CAMERA_USER}:{CAMERA_PASSWORD}@{CAMERA_IP}:10554/udp/av0_0",
    f"rtsp://{CAMERA_USER}:{CAMERA_PASSWORD}@{CAMERA_IP}:10554/udp/av0_1",
    f"rtsp://{CAMERA_USER}:{CAMERA_PASSWORD}@{CAMERA_IP}:554/tcp/av0_0",
    f"rtsp://{CAMERA_USER}:{CAMERA_PASSWORD}@{CAMERA_IP}:554/tcp/av0_1",
]

out_dir = Path("tmp_camera_probe")
out_dir.mkdir(exist_ok=True)

# 设置FFMPEG参数
os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp|stimeout;5000000|max_delay;500000"

# 循环测试每个地址
for index, url in enumerate(urls, start=1):
    print(f"\n[{index}] testing {url.replace(CAMERA_PASSWORD, '***')}")

    cap = cv2.VideoCapture(url, cv2.CAP_FFMPEG)
    if not cap.isOpened():
        print("打开失败")
        continue

    start = time.time()
    success = False

    while time.time() - start < 10:
        ok, frame = cap.read()
        if ok and frame is not None:
            height, width = frame.shape[:2]
            output = out_dir / f"camera_probe_{index}_{width}x{height}.jpg"
            cv2.imwrite(str(output), frame)
            print(f"成功：已保存 {output}")
            cap.release()
            raise SystemExit(0)

    # 10秒没读到画面
    cap.release()
    print("已打开但未获取到画面")

raise SystemExit("没有抓到画面，请检查 App 里是否开启 RTSP/ONVIF/局域网协议")