import clr
import sys

# 加载 C# 生成的 DLL
clr.AddReference(r"SharpCamera.dll")

# 引入 C# 里的命名空间和类
from SharpCamera import CameraControl

# 直接实例化 C# 的类，调用它的方法
cam = CameraControl()
cam.OpenCamera(0)  # 打开摄像头
cam.SetBrightness(50)  # 直接调节亮度 (完全跟厂家软件一模一样)
cam.SetContrast(30)