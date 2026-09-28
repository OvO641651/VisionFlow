import cv2
import numpy as np


class DetectorShape:
    def __init__(self):
        self.a = 1

    def gray(self, img):
        self.a = 2
        if len(img.shape) == 3:
            img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        data = []
        return img, data

    def gray_with_preserve_lines(self, clean_roi, display_roi):
        """
        :param clean_roi: 纯净层 ROI 图像 (BGR 3通道，没有任何划痕)
        :param display_roi: 显示层 ROI 图像 (BGR 3通道，包含之前节点绘制的任意颜色线条)
        :return: 带有原本线条的 3 通道灰度图像
        """
        # 基于纯净 ROI 生成 3 通道灰度背景
        roi_gray = cv2.cvtColor(clean_roi, cv2.COLOR_BGR2GRAY)
        roi_gray_3ch = cv2.cvtColor(roi_gray, cv2.COLOR_GRAY2BGR)

        # 通过对比，找出显示层中新增的任意颜色的线条像素
        diff_bgr = np.sum(np.abs(display_roi.astype(np.int16) - clean_roi.astype(np.int16)), axis=2)
        mask_lines = diff_bgr > 0

        # 将这些任意颜色的线条覆盖回灰度图上
        roi_gray_3ch[mask_lines] = display_roi[mask_lines]

        return roi_gray_3ch


    def line_detector(self, img, rho = 1.0, theta = np.pi / 180,
                      threshold = 100, min_line_length = 100.0,
                      max_line_gap = 10.0, canny_low = 50,
                      canny_high = 150, aperture = 3,
                      roi_offset_x=0, roi_offset_y=0):
        """
        检测图像中的直线段，并在原图上绘制绿色线段。

        参数:
            img: 输入图像（BGR格式）
            rho: 距离分辨率（像素）
            theta: 角度分辨率（弧度）
            threshold: 累加器阈值，值越小检测到的线段越多
            minLineLength: 最小线段长度，短于此值的线段被丢弃
            maxLineGap: 同一线段上允许的最大间断间隔（像素）
            canny_low: Canny边缘检测的低阈值
            canny_high: Canny边缘检测的高阈值
            aperture: Sobel算子的大小
            roi_offset_x: 直线检测区域的 x轴偏移量
            roi_offset_y: 直线检测区域的 y轴偏移量

        返回:
            绘制了线段的图像（与输入img是同一对象）
        """
        self.a = 3
        if len(img.shape) == 2:
            gray = img
        else:
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        edges = cv2.Canny(gray, canny_low, canny_high, apertureSize=aperture)
        lines = cv2.HoughLinesP(edges, rho=rho, theta=theta, threshold=threshold,
                                minLineLength=min_line_length, maxLineGap=max_line_gap)
        line_data = []
        if lines is not None:
            for line in lines:
                x1, y1, x2, y2 = line[0]
                cv2.line(img, (x1, y1), (x2, y2), (0, 255, 0), 2)
                # 把相对于子图的坐标，加上偏移量，转化为主图的真实坐标
                x1 += roi_offset_x
                y1 += roi_offset_y
                x2 += roi_offset_x
                y2 += roi_offset_y
                line_data.append((x1, y1, x2, y2))
        return img, line_data

    def circle_detector(self, img, method = cv2.HOUGH_GRADIENT, dp = 1.0,
                        min_dist = 150.0, param1 = 100.0, param2 = 80.0,
                        min_radius = 20, max_radius = 0,
                        roi_offset_x=0, roi_offset_y=0):
        """
        检测图像中的圆形，并在原图上绘制红色圆。

        参数:
            img: 输入图像（BGR格式）
            method: 检测方法，目前仅支持cv2.HOUGH_GRADIENT
            dp: 累加器分辨率与图像分辨率的反比（dp=1时分辨率相同）
            minDist: 圆心之间的最小距离，避免检测到相邻的圆
            param1: Canny边缘检测的高阈值（低阈值为它的一半）
            param2: 圆心检测的累加器阈值，越小检测到的圆越多（可能包含假圆）
            minRadius: 最小圆半径
            maxRadius: 最大圆半径（0表示无限制）
            roi_offset_x: 直线检测区域的 x轴偏移量
            roi_offset_y: 直线检测区域的 y轴偏移量

        返回:
            绘制了圆形的图像
        """
        self.a = 4
        if len(img.shape) == 2:
            gray = img
        else:
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        circles = cv2.HoughCircles(gray, method, dp, min_dist, param1=param1,
                                       param2=param2, minRadius=min_radius,
                                       maxRadius=max_radius)
        circle_data = []
        if circles is not None:
            circles = np.round(circles[0, :]).astype(int)
            for (x, y, r) in circles:
                cv2.circle(img, (x, y), r, (0, 0, 255), 2)  # 红色圆
                cv2.circle(img, (x, y), 2, (0, 0, 255), 3)  # 圆心
                circle_data.append((x + roi_offset_x, y + roi_offset_y, r))
        return img, circle_data


def main():

    detector = DetectorShape()
    img = cv2.imread('image/lena.png')
    img, _ = detector.gray(img)


    ''' 
    line_data = []
    img, line_data= detector.line_detector(img)
    print(line_data)
    '''

    circle_data = []
    img, circle_data = detector.circle_detector(img)
    print(circle_data)

    cv2.imshow('img', img)
    cv2.waitKey(0)


    '''
    cap = cv2.VideoCapture(0)
    while(1):
        ret, frame = cap.read()  # 获取每一帧
        if ret == False:
            print('无法打开摄像头')
            break

        detector = Detector()
        #frame = detector.line_detector(frame)
        frame = detector.circle_detector(frame)
        cv2.imshow('video', frame)
        if cv2.waitKey(1) & 0XFF == ord('q'):
            break

    #cv2.waitKey() # 播放视频不需要，如果使用了会导致按下q键后视频不能退出，会卡在最后一个画面
    cap.release()  # 释放内存
    cv2.destroyAllWindows()
    '''



if __name__ == '__main__':
    main()