import tkinter as tk
from tkinter import ttk
import cv2
from PIL import Image, ImageTk


class UVCCameraTool:
    def __init__(self, root):
        self.root = root
        self.root.title("UVC 摄像头控制工具")
        self.root.geometry("820x600")

        self.cap = None
        self.is_running = False
        self.current_device_index = 0
        self.control_vars = {}

        # --- 左侧：控制面板 ---
        self.left_frame = ttk.Frame(root, padding=10, width=300)
        self.left_frame.pack(side='left', fill='y', padx=5)

        # 1. 设备选择与开关
        device_frame = ttk.LabelFrame(self.left_frame, text="摄像头控制")
        device_frame.pack(fill='x', pady=(0, 10))

        # 下拉框选择设备
        ttk.Label(device_frame, text="选择设备:").pack(anchor='w', pady=(5, 0))
        self.device_combo = ttk.Combobox(device_frame, values=["0 (默认摄像头)", "1", "2"], width=15, state='readonly')
        self.device_combo.current(0)
        self.device_combo.pack(anchor='w', pady=5)

        # 打开/关闭按钮
        self.toggle_btn = ttk.Button(device_frame, text="打开摄像头", command=self.toggle_camera)
        self.toggle_btn.pack(fill='x', pady=5)

        # 2. UVC 属性 (视频 Proc Amp)
        self.proc_frame = ttk.LabelFrame(self.left_frame, text="视频 Proc Amp")
        self.proc_frame.pack(fill='x')

        # 控件生成逻辑
        controls_config = [
            ("亮度(B)", 0, -127, 127, False),
            ("对比度(C)", 32, 0, 127, False),
            ("色调(H)", 0, -127, 127, False),
            ("饱和度(S)", 64, 0, 127, False),
            ("清晰度(P)", 2, 0, 100, False),
            ("伽玛(G)", 100, 1, 500, False),
            ("白平衡(W)", 4600, 1000, 10000, True),
            ("逆光对比(B)", 1, 0, 10, False),
            ("增益(G)", 0, 0, 255, False),
        ]

        for label, default, min_v, max_v, auto_checked in controls_config:
            row = ttk.Frame(self.proc_frame)
            row.pack(fill='x', pady=3)
            ttk.Label(row, text=label, width=10).pack(side='left')

            # 滑块
            slider = tk.Scale(row, from_=min_v, to=max_v, orient='horizontal', showvalue=0, length=120)
            slider.set(default)
            slider.pack(side='left', expand=True, fill='x')

            # 数值框
            entry_var = tk.StringVar(value=str(default))
            ttk.Entry(row, textvariable=entry_var, width=6).pack(side='left', padx=5)

            # 自动复选框
            auto_var = tk.BooleanVar(value=auto_checked)
            chk = ttk.Checkbutton(row, text="自动", variable=auto_var)
            chk.pack(side='left')

            # 联动逻辑（滑块 <-> 数值框）
            slider.config(command=lambda v, var=entry_var: var.set(str(int(float(v)))))
            entry_var.trace('w', lambda *a, s=slider, var=entry_var: self.update_slider(s, var))

            # 【新增关键点 1】：白平衡勾选“自动”时，禁用滑块
            if label == "白平衡(W)":
                def toggle_slider(*args, s=slider, av=auto_var):
                    # 如果勾选了自动，滑块变灰不可用；否则恢复正常
                    s.config(state='disabled' if av.get() else 'normal')

                # 绑定复选框的状态变化
                auto_var.trace_add('write', toggle_slider)
                # 初始化时立即执行一次（因为默认勾选了自动）
                if auto_checked:
                    slider.config(state='disabled')

            self.control_vars[label] = {'slider': slider, 'entry_var': entry_var, 'auto_var': auto_var}

        # 应用设置按钮（直接应用）
        ttk.Button(self.left_frame, text="应用当前设置", command=self.apply_settings).pack(pady=15)

        # --- 右侧：视频预览 ---
        self.right_frame = ttk.Frame(root, padding=10)
        self.right_frame.pack(side='right', fill='both', expand=True)

        self.video_label = ttk.Label(self.right_frame, text="摄像头未开启", anchor='center')
        self.video_label.pack(expand=True)

    def update_slider(self, slider, var):
        try:
            slider.set(int(var.get()))
        except:
            pass

    def toggle_camera(self):
        if self.is_running:
            self.stop_camera()
        else:
            self.start_camera()

    def start_camera(self):
        # 解析设备索引
        dev_str = self.device_combo.get()
        try:
            self.current_device_index = int(dev_str.split()[0]) if "(" in dev_str else int(dev_str)
        except:
            self.current_device_index = 0

        # 【新增关键点 2】：强制指定后端为 DirectShow (cv2.CAP_DSHOW)
        # 这是 Windows 下解决 OpenCV 无法调节参数的核心修复方法
        self.cap = cv2.VideoCapture(self.current_device_index, cv2.CAP_DSHOW)

        if not self.cap.isOpened():
            self.video_label.config(text="无法打开摄像头，请检查连接！")
            return

        self.is_running = True
        self.toggle_btn.config(text="关闭摄像头")
        self.apply_settings()  # 打开时应用一次默认设置

        self.update_frame()

    def stop_camera(self):
        self.is_running = False
        if self.cap:
            self.cap.release()
            self.cap = None
        self.video_label.config(image='', text="摄像头已关闭")
        self.toggle_btn.config(text="打开摄像头")

    def update_frame(self):
        if self.is_running and self.cap and self.cap.isOpened():
            ret, frame = self.cap.read()
            if ret:
                # OpenCV 是 BGR，Tkinter 需要 RGB
                frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                # 缩放以适应界面
                h, w, _ = frame.shape
                max_size = 480
                if max(h, w) > max_size:
                    scale = max_size / max(h, w)
                    frame = cv2.resize(frame, (int(w * scale), int(h * scale)))

                img = Image.fromarray(frame)
                imgtk = ImageTk.PhotoImage(image=img)
                self.video_label.config(image=imgtk)
                self.video_label.image = imgtk  # 保持引用防止被垃圾回收

        # 循环调用（每 20ms 一帧，约 50fps）
        if self.is_running:
            self.root.after(20, self.update_frame)

    def apply_settings(self):
        if not self.cap or not self.cap.isOpened():
            print("请先打开摄像头再应用设置。")
            return

        print("\n--- 开始应用参数 ---")
        for label, data in self.control_vars.items():
            prop_id = None
            val = data['slider'].get()
            auto = data['auto_var'].get()

            if label == "白平衡(W)":
                self.cap.set(cv2.CAP_PROP_AUTO_WB, 1 if auto else 0)
                if auto:
                    # 白平衡自动时依然尝试关闭曝光（因为曝光和白平衡常常绑定）
                    print(f"  [信息] {label} 处于自动模式，跳过手动色温设置。")
                    continue
                else:
                    prop_id = cv2.CAP_PROP_WB_TEMPERATURE
            elif label == "增益(G)":
                prop_id = cv2.CAP_PROP_GAIN
            elif label == "亮度(B)":
                prop_id = cv2.CAP_PROP_BRIGHTNESS
            elif label == "对比度(C)":
                prop_id = cv2.CAP_PROP_CONTRAST
            elif label == "饱和度(S)":
                prop_id = cv2.CAP_PROP_SATURATION
            elif label == "清晰度(P)":
                prop_id = cv2.CAP_PROP_SHARPNESS
            elif label == "伽玛(G)":
                prop_id = cv2.CAP_PROP_GAMMA

            if prop_id is not None:
                old_val = self.cap.get(prop_id)
                success = self.cap.set(prop_id, val)

                import time
                time.sleep(0.15)  # 给摄像头更长的响应时间（0.15秒）
                new_val = self.cap.get(prop_id)

                if abs(new_val - old_val) > 0.5:
                    print(f"  ✅ 设置成功: {label} (原值: {old_val:.1f} -> 现值: {new_val:.1f})")
                else:
                    if new_val == -1.0:
                        print(f"  ❌ 失败: {label} 硬件完全不支持 (返回值 -1.0)")
                    else:
                        # 【优化提示语】：告知用户可能是被曝光锁定了，并直接给出当前真实值
                        print(f"  ⛔ 被固件锁定: {label} 调节无效！(设备强制停留在 {new_val:.1f})")
        print("--- 应用完成 ---\n")


if __name__ == "__main__":
    root = tk.Tk()
    app = UVCCameraTool(root)
    root.mainloop()