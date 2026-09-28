import random
import matplotlib.pyplot as plt
import matplotlib.animation as animation

# ---------- 设置中文字体（解决中文显示问题） ----------
plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'WenQuanYi Micro Hei']  # 按顺序尝试
plt.rcParams['axes.unicode_minus'] = False   # 解决负号显示异常

def is_sorted(arr):
    return all(arr[i] <= arr[i+1] for i in range(len(arr)-1))

def bogosort_generator(arr):
    count = 0
    while not is_sorted(arr):
        random.shuffle(arr)
        count += 1
        yield arr.copy(), count, False
    yield arr.copy(), count, True

def update_plot(frame, bars, text):
    arr, count, sorted_flag = frame
    # 更新柱状图高度
    for bar, val in zip(bars, arr):
        bar.set_height(val)
    # 根据排序状态改变颜色和文字
    color = 'green' if sorted_flag else 'skyblue'
    for bar in bars:
        bar.set_color(color)
    status = '✓ 已排序！' if sorted_flag else '✗ 洗牌中...'
    text.set_text(f"尝试次数: {count}  {status}")
    return bars, text

def main():
    # 数据长度建议 5~8，太长会等很久
    data = list(range(1, 7))
    random.shuffle(data)

    fig, ax = plt.subplots()
    ax.set_ylim(0, max(data) + 2)
    ax.set_title("猴子排序可视化 (Bogosort)")

    bars = ax.bar(range(len(data)), data, color='skyblue')
    text = ax.text(0.02, 0.95, "", transform=ax.transAxes, fontsize=12,
                   verticalalignment='top')

    gen = bogosort_generator(data)

    # ---------- 关键修复：通过 fargs 传递 bars 和 text ----------
    ani = animation.FuncAnimation(
        fig, update_plot, frames=gen, interval=200,
        repeat=False, cache_frame_data=False,
        fargs=(bars, text)   # 这里传入额外参数
    )

    plt.show()

if __name__ == "__main__":
    main()