#!/usr/bin/env python3
"""
Coco 猫娘主题 Slack GIF 生成器
制作一张可爱的"喵~ Coco爱你"动画 GIF
"""
import sys
import math
import os

# 添加技能路径（绝对路径）
SKILL_PATH = r"C:\Users\18085\Desktop\claude_code\2_学习\how-to-harness\s00_evolution\agent\skills\slack-gif-creator"
sys.path.insert(0, SKILL_PATH)

from PIL import Image, ImageDraw, ImageFont
from core.gif_builder import GIFBuilder
from core.frame_composer import (
    create_gradient_background,
    draw_circle,
    draw_star,
)
from core.easing import interpolate

# ============ 配置 ============
WIDTH, HEIGHT = 480, 480
FPS = 15
NUM_FRAMES = 45  # 3秒动画

# 颜色定义
BG_TOP = (255, 182, 193)      # 浅粉
BG_BOTTOM = (255, 218, 185)   # 浅桃
HEART_COLOR = (255, 69, 105)  # 爱心红
HEART_OUTLINE = (220, 20, 60)
STAR_COLOR = (255, 215, 0)    # 金色星星
STAR_OUTLINE = (255, 165, 0)
FLOWER_COLOR = (255, 105, 180)  # 粉色小花
FLOWER_CENTER = (255, 255, 0)
TEXT_COLOR = (255, 255, 255)
TEXT_OUTLINE = (255, 105, 180)

# 尝试加载一个好看的字体（Windows 自带）
def load_font(size):
    font_paths = [
        "C:/Windows/Fonts/msyhbd.ttc",   # 微软雅黑粗体
        "C:/Windows/Fonts/msyh.ttc",     # 微软雅黑
        "C:/Windows/Fonts/simhei.ttf",   # 黑体
        "C:/Windows/Fonts/arialbd.ttf",  # Arial Bold
    ]
    for path in font_paths:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    return ImageFont.load_default()


def draw_heart(draw, cx, cy, size, fill, outline, width=3):
    """绘制一颗爱心"""
    # 爱心由两个圆和一个三角形组成
    r = size * 0.5
    # 两个圆
    draw.ellipse([cx - r, cy - r, cx, cy + r], fill=fill, outline=outline, width=width)
    draw.ellipse([cx, cy - r, cx + r, cy + r], fill=fill, outline=outline, width=width)
    # 三角形
    draw.polygon(
        [(cx - r * 1.05, cy + r * 0.2), (cx + r * 1.05, cy + r * 0.2), (cx, cy + r * 2.2)],
        fill=fill, outline=outline
    )


def draw_flower(draw, cx, cy, size, petal_color, center_color):
    """绘制一朵小花"""
    num_petals = 6
    for i in range(num_petals):
        angle = i * (360 / num_petals) * math.pi / 180
        px = cx + size * 0.6 * math.cos(angle)
        py = cy + size * 0.6 * math.sin(angle)
        draw.ellipse(
            [px - size * 0.35, py - size * 0.35, px + size * 0.35, py + size * 0.35],
            fill=petal_color, outline=(255, 20, 147), width=2
        )
    # 花心
    draw.ellipse(
        [cx - size * 0.25, cy - size * 0.25, cx + size * 0.25, cy + size * 0.25],
        fill=center_color, outline=(255, 140, 0), width=2
    )


def draw_sparkle(draw, cx, cy, size, color):
    """绘制四角星闪光"""
    points = []
    for i in range(8):
        angle = (i * 45 - 90) * math.pi / 180
        radius = size if i % 2 == 0 else size * 0.3
        px = cx + radius * math.cos(angle)
        py = cy + radius * math.sin(angle)
        points.append((px, py))
    draw.polygon(points, fill=color, outline=(255, 215, 0), width=2)


def main():
    builder = GIFBuilder(width=WIDTH, height=HEIGHT, fps=FPS)
    font_big = load_font(52)
    font_small = load_font(30)

    for i in range(NUM_FRAMES):
        t = i / (NUM_FRAMES - 1)  # 0.0 ~ 1.0

        # 渐变背景
        frame = create_gradient_background(WIDTH, HEIGHT, BG_TOP, BG_BOTTOM)
        draw = ImageDraw.Draw(frame)

        # ===== 背景装饰：闪烁的星星 =====
        sparkle_positions = [
            (60, 80), (420, 70), (90, 380), (400, 400), (240, 60)
        ]
        for idx, (sx, sy) in enumerate(sparkle_positions):
            # 星星闪烁（大小随正弦变化）
            sparkle_phase = (t * 2 * math.pi + idx * 1.3) % (2 * math.pi)
            sparkle_size = 8 + 6 * abs(math.sin(sparkle_phase))
            alpha = 0.5 + 0.5 * abs(math.sin(sparkle_phase))
            color = (
                int(255 * alpha + 255 * (1 - alpha)),
                int(215 * alpha + 255 * (1 - alpha)),
                int(0 * alpha + 255 * (1 - alpha)),
            )
            draw_sparkle(draw, sx, sy, int(sparkle_size), color)

        # ===== 旋转的小花（角落） =====
        flower_angle = t * 2 * math.pi
        flower_size = 22 + 3 * math.sin(flower_angle * 2)
        draw_flower(draw, 400, 120, int(flower_size), FLOWER_COLOR, FLOWER_CENTER)
        draw_flower(draw, 80, 300, int(flower_size * 0.8), (255, 182, 193), (255, 255, 0))

        # ===== 中央跳动的大爱心 =====
        # 心跳效果：两次快速跳动 + 停顿
        heartbeat = math.sin(t * 4 * math.pi)
        if heartbeat > 0.8:
            heart_scale = 1.0 + 0.15 * (heartbeat - 0.8) / 0.2
        else:
            heart_scale = 1.0
        heart_size = 90 * heart_scale
        heart_cx, heart_cy = WIDTH // 2, HEIGHT // 2 - 30

        # 爱心光晕（半透明大爱心）
        glow = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
        glow_draw = ImageDraw.Draw(glow)
        draw_heart(glow_draw, heart_cx, heart_cy, heart_size * 1.25, (255, 105, 180, 60), (255, 105, 180, 60), 0)
        frame = Image.alpha_composite(frame.convert("RGBA"), glow).convert("RGB")
        draw = ImageDraw.Draw(frame)

        # 主爱心
        draw_heart(draw, heart_cx, heart_cy, heart_size, HEART_COLOR, HEART_OUTLINE, 4)

        # 爱心上的高光
        highlight_r = heart_size * 0.18
        draw.ellipse(
            [heart_cx - heart_size * 0.3, heart_cy - heart_size * 0.1,
             heart_cx - heart_size * 0.3 + highlight_r * 2, heart_cy - heart_size * 0.1 + highlight_r * 2],
            fill=(255, 182, 193), outline=None
        )

        # ===== 弹跳的文字 =====
        # "喵~" 文字弹跳
        bounce_y = interpolate(0, 40, t, easing="bounce_out")
        text1 = "喵~"
        bbox1 = draw.textbbox((0, 0), text1, font=font_big)
        tw1 = bbox1[2] - bbox1[0]
        tx1 = (WIDTH - tw1) // 2
        ty1 = HEIGHT - 130 - int(bounce_y)
        # 文字描边
        for dx in (-2, 2):
            for dy in (-2, 2):
                draw.text((tx1 + dx, ty1 + dy), text1, font=font_big, fill=TEXT_OUTLINE)
        draw.text((tx1, ty1), text1, font=font_big, fill=TEXT_COLOR)

        # "Coco爱你" 文字
        text2 = "Coco爱你"
        bbox2 = draw.textbbox((0, 0), text2, font=font_small)
        tw2 = bbox2[2] - bbox2[0]
        tx2 = (WIDTH - tw2) // 2
        ty2 = HEIGHT - 70
        for dx in (-2, 2):
            for dy in (-2, 2):
                draw.text((tx2 + dx, ty2 + dy), text2, font=font_small, fill=TEXT_OUTLINE)
        draw.text((tx2, ty2), text2, font=font_small, fill=TEXT_COLOR)

        builder.add_frame(frame)

    # 保存 GIF
    output_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "coco_love.gif"
    )
    info = builder.save(
        output_path,
        num_colors=128,
        remove_duplicates=False,
    )
    print(f"\nGIF 已保存到: {output_path}")


if __name__ == "__main__":
    main()
