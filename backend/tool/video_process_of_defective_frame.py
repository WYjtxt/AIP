# 图像花帧情况处理
# 图像滤波、插值、错误恢复机制
#
# import cv2
# import numpy as np
# from datetime import datetime
#
# # 判断两帧图像是否相似
# def is_frames_corrupted(frame1, frame2, threshold=0.99):
#     difference = cv2.absdiff(frame1, frame2)
#     mean_difference = np.mean(difference)
#     similarity = 1 - (mean_difference / 255.0)
#     return similarity >= threshold
#
# # 判断视频中是否存在花帧
# # def find_glitch_in_video(video_path, threshold=0.99, diff=0):
# #     frame_count = 0
# #     glitch_frame_count = 0
# #     cap = cv2.VideoCapture(video_path)
# def find_glitch_in_video(cap, threshold=0.99, diff=0):
#     frame_count = 0
#     glitch_frame_count = 0
#     # cap = cv2.VideoCapture(video_path)
#
#     if not cap.isOpened():
#         print("Error opening video file")
#         return None
#
#     ret, prev_frame = cap.read()
#     prev_frame = cv2.cvtColor(prev_frame, cv2.COLOR_BGR2GRAY)
#     start_time = datetime.now()
#     # print(f"Start time: {start_time}")
#     while cap.isOpened():
#         ret, curr_frame = cap.read()
#         end_time = datetime.now()
#         # print(f"End time: {end_time}")
#         if not ret:
#             break
#         if (end_time - start_time).seconds > diff:
#             # print(f"耗时：{diff}-{(end_time - start_time).seconds}")
#             # print("Video is too long, exiting...")
#             break
#         frame_count += 1
#         curr_frame_gray = cv2.cvtColor(curr_frame, cv2.COLOR_BGR2GRAY)
#         if is_frames_corrupted(prev_frame, curr_frame_gray, threshold):
#             glitch_frame_count += 1
#             # print(f"Glitch found in the video's frame {frame_count}")
#             # cv2.imshow("Glitch Frame", curr_frame)
#             # cv2.waitKey(0)
#             # cv2.destroyAllWindows()
#             # cv2.imwrite("glitch_frame.jpg", curr_frame)
#         else:
#             prev_frame = curr_frame_gray
#             # print("No glitch found in the video's frame")
#     cap.release()
#     if glitch_frame_count:
#         return True
#     else:
#         return False
#
# if __name__ == "__main__":
#     video_path = r"D:\Algorithms\Video Quality Diagnosis\Video Quality Diagnosis\test.mp4"
#     bool_value = find_glitch_in_video(video_path)
#     print(bool_value)
# 图像花帧情况处理
# 图像滤波、插值、错误恢复机制

# 花帧检测

import cv2
import math
import numpy as np
from datetime import datetime

# 判断两帧图像是否相似
def is_frames_corrupted(frame1, frame2, threshold=0.99):
    if frame1 is None or frame2 is None:
        return False
    difference = cv2.absdiff(frame1, frame2)
    mean_difference = np.mean(difference)
    # print(f"mean_difference: {mean_difference}")
    similarity = 1 - (mean_difference / 255.0)
    return similarity >= threshold

# 判断视频中是否存在花帧
def run(cap, fps, prewarn_threshold=90, warn_threshold=99, diff=0):
    # print(f"{prev_frame}-{prev_frame.shape}")
    frame_count = 0
    prev_frame = None
    glitch_frame_count = 0
    # 获取帧率
    # fps = int(cap.get(cv2.CAP_PROP_FPS))
    prewarn_threshold = math.ceil(prewarn_threshold * 25 / 100)
    warn_threshold = math.floor(warn_threshold * 25 / 100)
    # print(f"prewarn_threshold: {prewarn_threshold}, warn_threshold: {warn_threshold}")
    start_time = datetime.now()
    # print(f"Start time: {start_time}")
    try:
        while True:
            # cap = cv2.VideoCapture(video_stream_url)
            if cap.isOpened():
                ret, curr_frame = cap.read()
                # print(curr_frame)
                if not ret:
                    # print("Exiting....")
                    break
                # print(curr_frame.shape)
                frame_count += 1
                # print(f"frame count is {frame_count}")
                end_time = datetime.now()
                # print(f"End time: {end_time}")
                if (end_time - start_time).seconds > diff:  # 超时退出
                    # print(f"耗时：{diff}-{(end_time - start_time).seconds}")
                    break
                curr_frame_gray = cv2.cvtColor(curr_frame, cv2.COLOR_BGR2GRAY)

                if prev_frame is not None:
                    if not is_frames_corrupted(prev_frame, curr_frame_gray):
                        glitch_frame_count += 1
                prev_frame = curr_frame_gray
            else:
                print("视频流打开失败")

    except Exception as e:
        print(f"Error occurred: {e}")
    finally:
        cap.release()

    # print(f"Glitch frame count: {glitch_frame_count}")
    if glitch_frame_count > warn_threshold * fps / 100:
        return "报警"
    elif warn_threshold * fps / 100 > glitch_frame_count > prewarn_threshold * fps / 100:
        return "预警"
    else:
        return "正常"

# 测试
if __name__ == '__main__':
    cap = cv2.VideoCapture(r"rtsp://12138@192.168.7.40")
    # print(run(cap, prewarn_threshold=1, warn_threshold=20, diff=1))