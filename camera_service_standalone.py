"""
独立的摄像头服务 - 解决OpenCV在异步环境中的问题
运行在独立进程中，通过HTTP提供快照
"""
import cv2
import time
from fastapi import FastAPI, Response
from fastapi.responses import StreamingResponse
import uvicorn
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Camera Service")

# 全局摄像头对象
camera = None
camera_index = 0
last_frame = None
last_frame_time = 0
frame_cache_ttl = 0.1  # 100ms缓存

def init_camera():
    """初始化摄像头"""
    global camera
    if camera is not None:
        return True
    
    try:
        camera = cv2.VideoCapture(camera_index, cv2.CAP_DSHOW)
        if camera.isOpened():
            # 设置摄像头参数
            camera.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            camera.set(cv2.CAP_PROP_FPS, 30)
            logger.info(f"✅ Camera {camera_index} initialized successfully")
            return True
        else:
            camera = None
            logger.error(f"❌ Failed to open camera {camera_index}")
            return False
    except Exception as e:
        camera = None
        logger.error(f"❌ Error initializing camera: {e}")
        return False

def get_frame():
    """获取一帧图像"""
    global camera, last_frame, last_frame_time
    
    # 检查缓存
    current_time = time.time()
    if last_frame is not None and (current_time - last_frame_time) < frame_cache_ttl:
        return last_frame
    
    # 初始化摄像头
    if camera is None:
        if not init_camera():
            return None
    
    # 读取帧
    try:
        ret, frame = camera.read()
        if ret and frame is not None:
            # 编码为JPEG
            ret, jpeg = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
            if ret:
                last_frame = jpeg.tobytes()
                last_frame_time = current_time
                return last_frame
        else:
            # 读取失败，重新初始化
            logger.warning("Frame read failed, reinitializing camera...")
            if camera is not None:
                camera.release()
                camera = None
            return None
    except Exception as e:
        logger.error(f"Error reading frame: {e}")
        if camera is not None:
            camera.release()
            camera = None
        return None

@app.get("/")
def root():
    """健康检查"""
    return {
        "status": "running",
        "camera_initialized": camera is not None and camera.isOpened(),
        "camera_index": camera_index
    }

@app.get("/snapshot")
def snapshot():
    """获取单帧快照"""
    frame = get_frame()
    if frame is None:
        return Response(content="Camera not available", status_code=503)
    
    return Response(
        content=frame,
        media_type="image/jpeg",
        headers={
            "Cache-Control": "no-store, max-age=0",
            "X-Camera-Source": "local-standalone"
        }
    )

@app.get("/stream.mjpg")
def stream():
    """MJPEG流"""
    def generate():
        fps = 6  # 6fps
        frame_delay = 1.0 / fps
        
        while True:
            frame = get_frame()
            if frame is not None:
                yield (
                    b"--frame\r\n"
                    b"Content-Type: image/jpeg\r\n"
                    + f"Content-Length: {len(frame)}\r\n\r\n".encode()
                    + frame
                    + b"\r\n"
                )
            time.sleep(frame_delay)
    
    return StreamingResponse(
        generate(),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )

@app.on_event("shutdown")
def shutdown():
    """关闭时释放摄像头"""
    global camera
    if camera is not None:
        camera.release()
        logger.info("Camera released")

if __name__ == "__main__":
    logger.info("Starting standalone camera service on port 8001...")
    uvicorn.run(app, host="0.0.0.0", port=8001, log_level="info")
