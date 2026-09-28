import cv2
import numpy as np

class DetectorShape:
    def __init__(self):
        pass

    def gray(self, img):
        if len(img.shape) == 3:
            img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        data = []
        return img, data

    def line_detector(self, img, rho=1.0, theta=np.pi / 180,
                      threshold=100, minLineLength=100.0,
                      maxLineGap=10.0, canny_low=50,
                      canny_high=150, aperture=3,
                      roi_offset_x=0, roi_offset_y=0):  # 新增偏移量参数
        """
        检测图像中的直线段，并在原图上绘制绿色线段。
        """
        if len(img.shape) == 2:
            gray = img
        else:
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        edges = cv2.Canny(gray, canny_low, canny_high, apertureSize=aperture)
        lines = cv2.HoughLinesP(edges, rho=rho, theta=theta, threshold=threshold,
                                minLineLength=minLineLength, maxLineGap=maxLineGap)
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

    def circle_detector(self, img, method=cv2.HOUGH_GRADIENT, dp=1.0,
                        minDist=150.0, param1=100.0, param2=120.0,
                        minRadius=20, maxRadius=0,
                        roi_offset_x=0, roi_offset_y=0):
        if len(img.shape) == 2:
            gray = img
        else:
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        circles = cv2.HoughCircles(gray, method, dp, minDist, param1=param1,
                                   param2=param2, minRadius=minRadius,
                                   maxRadius=maxRadius)
        circle_data = []
        if circles is not None:
            circles = np.round(circles[0, :]).astype(int)
            for (x, y, r) in circles:
                cv2.circle(img, (x, y), r, (0, 0, 255), 2)
                cv2.circle(img, (x, y), 2, (0, 0, 255), 3)
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