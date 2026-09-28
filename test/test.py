import cv2
import numpy as np
import math


# ===============================
# 参数
# ===============================

IMAGE_PATH = "image/lena.png"


# ROI区域
ROI_X = 200
ROI_Y = 200
ROI_W = 500
ROI_H = 300


# ===============================
# 读取图片
# ===============================

img = cv2.imread(IMAGE_PATH)

if img is None:
    raise Exception("图片不存在")


result = img.copy()


# ===============================
# 1. ROI
# ===============================

roi = img[
    ROI_Y:ROI_Y+ROI_H,
    ROI_X:ROI_X+ROI_W
]


cv2.rectangle(
    result,
    (ROI_X, ROI_Y),
    (ROI_X+ROI_W, ROI_Y+ROI_H),
    (255,0,0),
    2
)



# ===============================
# 2. 灰度
# ===============================

gray = cv2.cvtColor(
    roi,
    cv2.COLOR_BGR2GRAY
)



# ===============================
# 3. 边缘检测
# ===============================

edges = cv2.Canny(
    gray,
    50,
    150
)



# ===============================
# 4. 获取边缘点
# ===============================

ys,xs = np.where(edges>0)


points=[]

for x,y in zip(xs,ys):

    # 转回原图坐标
    px=x+ROI_X
    py=y+ROI_Y

    points.append(
        [px,py]
    )


points=np.array(points)



print("边缘点数量:",len(points))


# ===============================
# 绘制边缘点
# ===============================

for p in points:

    cv2.circle(
        result,
        tuple(p),
        2,
        (0,0,255),
        -1
    )



# ===============================
# 5. 直线拟合
# ===============================

if len(points)>10:


    # OpenCV最小距离拟合
    line=cv2.fitLine(
        points,
        cv2.DIST_L2,
        0,
        0.01,
        0.01
    )


    vx,vy,x0,y0=line.flatten()


    # ===============================
    # 计算直线两个端点
    # ===============================


    length=1000


    x1=int(x0-vx*length)
    y1=int(y0-vy*length)

    x2=int(x0+vx*length)
    y2=int(y0+vy*length)



    cv2.line(
        result,
        (x1,y1),
        (x2,y2),
        (0,255,0),
        2
    )


    # ===============================
    # 计算角度
    # ===============================

    angle=math.degrees(
        math.atan2(vy,vx)
    )


    print(
        "直线角度:",
        angle
    )



    # ===============================
    # 计算拟合误差
    # ===============================


    # 点到直线距离

    errors=[]

    for x,y in points:


        distance=abs(
            vy*x
            -
            vx*y
            +
            (vx*y0-vy*x0)
        )


        errors.append(distance)


    error=np.mean(errors)


    print(
        "拟合误差:",
        error,
        "pixel"
    )



    # ===============================
    # 显示文字
    # ===============================


    cv2.putText(
        result,
        f"Angle:{angle:.3f}",
        (50,50),
        cv2.FONT_HERSHEY_SIMPLEX,
        1,
        (0,255,0),
        2
    )


    cv2.putText(
        result,
        f"Error:{error:.3f}px",
        (50,90),
        cv2.FONT_HERSHEY_SIMPLEX,
        1,
        (0,255,0),
        2
    )


else:

    print("边缘点不足")



# ===============================
# 显示
# ===============================


cv2.imshow(
    "Line Detect",
    result
)


cv2.imshow(
    "Edges",
    edges
)


cv2.waitKey(0)

cv2.destroyAllWindows()