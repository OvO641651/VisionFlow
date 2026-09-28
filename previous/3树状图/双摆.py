import numpy as np
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation

# ========== 参数 ==========
L1, L2 = 1.0, 1.0
m1, m2 = 1.0, 1.0
g = 9.81

# 随机初始条件（能量较低，避免直接发散）
np.random.seed()  # 每次运行不同
theta1 = np.random.uniform(0, 2*np.pi)
theta2 = np.random.uniform(0, 2*np.pi)
omega1 = np.random.uniform(-2, 2)   # 收窄范围
omega2 = np.random.uniform(-2, 2)

# 动画帧间隔 (秒)
frame_dt = 1/30
# 积分子步数（每帧内再细分，提高精度）
N_sub = 15
sub_dt = frame_dt / N_sub

# ========== 运动方程导数 ==========
def derivatives(th1, th2, om1, om2):
    delta = th1 - th2
    denom = (m1+m2)*L1*L2 - m2*L1*L2*np.cos(delta)**2
    if abs(denom) < 1e-12:
        denom = 1e-12
    dom1 = (m2*L2*om2**2*np.sin(delta)*np.cos(delta)
            + m2*g*np.sin(th2)*np.cos(delta)
            + m2*L1*om1**2*np.sin(delta)*np.cos(delta)
            - (m1+m2)*g*np.sin(th1)) / denom
    dom2 = (-m2*L2*om2**2*np.sin(delta)*np.cos(delta)
            + (m1+m2)*(g*np.sin(th1)*np.cos(delta)
                       - L1*om1**2*np.sin(delta)
                       - g*np.sin(th2))) / denom
    return np.array([om1, om2, dom1, dom2])

# ========== 单步 RK4 ==========
def rk4_step(state, dt):
    k1 = derivatives(*state)
    k2 = derivatives(*(state + dt/2 * k1))
    k3 = derivatives(*(state + dt/2 * k2))
    k4 = derivatives(*(state + dt * k3))
    return state + (dt/6) * (k1 + 2*k2 + 2*k3 + k4)

# ========== 绘图 ==========
fig, ax = plt.subplots(figsize=(6,6))
ax.set_xlim(-2.5, 2.5)
ax.set_ylim(-2.5, 2.5)
ax.set_aspect('equal')
ax.grid(True, linestyle='--', alpha=0.5)
ax.set_title("Stable Double Pendulum (infinite)")

line, = ax.plot([], [], 'o-', lw=2, color='black')
trail, = ax.plot([], [], '-', lw=1, color='red', alpha=0.5)
trail_len = 300
trail_x, trail_y = [], []

def init():
    line.set_data([], [])
    trail.set_data([], [])
    return line, trail

def update(frame):
    global theta1, theta2, omega1, omega2

    # 用多步子步骤稳定积分一帧
    state = np.array([theta1, theta2, omega1, omega2])
    for _ in range(N_sub):
        state = rk4_step(state, sub_dt)
    theta1, theta2, omega1, omega2 = state

    # 数值保护：万一溢出就重置摆（实际极少发生）
    if any(np.isnan(state)) or any(np.abs(state) > 1e10):
        theta1 = np.random.uniform(0, 2*np.pi)
        theta2 = np.random.uniform(0, 2*np.pi)
        omega1 = np.random.uniform(-2, 2)
        omega2 = np.random.uniform(-2, 2)
        trail_x.clear()
        trail_y.clear()
        return line, trail

    # 坐标
    x1 = L1 * np.sin(theta1)
    y1 = L1 * np.cos(theta1)
    x2 = x1 + L2 * np.sin(theta2)
    y2 = y1 + L2 * np.cos(theta2)

    # 更新图形
    px = [0, x1, x2]
    py = [0, y1, y2]
    line.set_data(px, py)

    trail_x.append(x2)
    trail_y.append(y2)
    if len(trail_x) > trail_len:
        trail_x.pop(0)
        trail_y.pop(0)
    trail.set_data(trail_x, trail_y)

    return line, trail

ani = FuncAnimation(fig, update, frames=None, init_func=init,
                    blit=True, interval=frame_dt*1000, repeat=False,
                    cache_frame_data=False)
plt.show()