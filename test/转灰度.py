import cv2
import os

def convert_to_grayscale(input_path, output_dir, output_filename=None):
    """
    将图片转换为灰度图并保存到指定目录

    Args:
        input_path (str): 输入图片路径
        output_dir (str): 输出目录路径（若不存在则自动创建）
        output_filename (str, optional): 输出文件名，默认为原文件名
    """
    # 读取图片
    img = cv2.imread(input_path)
    if img is None:
        raise ValueError(f"无法读取图片: {input_path}")

    # 转换为灰度图
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # 确定输出文件名
    if output_filename is None:
        output_filename = os.path.basename(input_path)

    # 创建输出目录（如果不存在）
    os.makedirs(output_dir, exist_ok=True)

    # 构造完整输出路径并保存
    output_path = os.path.join(output_dir, output_filename)
    cv2.imwrite(output_path, gray)

    print(f"灰度图片已保存至: {output_path}")

if __name__ == "__main__":
    # ========== 在这里直接修改路径 ==========
    input_path = "lena.png"        # 你的输入图片路径
    output_dir = "."                # 输出目录
    output_filename = "lena_gray.png"           # 可选，不指定则使用原文件名
    # ======================================

    try:
        convert_to_grayscale(input_path, output_dir, output_filename)
    except Exception as e:
        print(f"错误: {e}")