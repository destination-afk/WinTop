# -*- coding: utf-8 -*-
"""生成 WinTop 的程序图标 win.ico：透明底 + 霓虹绿圆角方框（与工具视觉效果一致）。"""
import math
import struct

SIZES = [16, 32, 48, 64]
GREEN = (156, 255, 0)          # BGR：#00FF9C
DARK = (24, 20, 16)            # BGR：#101418


def in_rrect(x, y, w, h, r, m=0):
    """点 (x,y) 是否在圆角矩形内（外扩 m 像素，负数为内缩）。"""
    x0, y0, x1, y1 = -m, -m, w + m, h + m
    r = max(0, min(r + m, (x1 - x0) / 2, (y1 - y0) / 2))
    if not (x0 + r <= x < x1 - r or y0 + r <= y < y1 - r):
        pass
    cx = min(max(x, x0 + r), x1 - r)
    cy = min(max(y, y0 + r), y1 - r)
    return (x - cx) ** 2 + (y - cy) ** 2 <= r * r


def render(size):
    b = size / 16.0
    border = max(2, round(2.4 * b))
    r_out = round(3.2 * b)
    px = bytearray(size * size * 4)
    for y in range(size):
        for x in range(size):
            i = (y * size + x) * 4
            outer = in_rrect(x, y, size, size, r_out)
            inner = in_rrect(x, y, size, size, r_out, -border)
            if outer and not inner:
                px[i:i + 3] = bytes(GREEN)          # 绿色描边
                px[i + 3] = 255
            elif outer and inner:
                px[i:i + 3] = bytes(DARK)           # 深色内芯
                px[i + 3] = 235
            # 其余全透明
    return px


def ico_image(size, px):
    # BITMAPINFOHEADER（ICO 里 height 写 2 倍：XOR + AND 两块）
    hdr = struct.pack("<IiiHHIIiiII", 40, size, size * 2, 1, 32, 0,
                      size * size * 4, 0, 0, 0, 0)
    xor = b"".join(px[y * size * 4:(y + 1) * size * 4]     # px 已是 BGRA，只需自下而上
                   for y in range(size - 1, -1, -1))
    and_stride = ((size + 31) // 32) * 4
    and_mask = b"\x00" * and_stride * size          # 32 位自带 alpha，掩码全 0
    return hdr + xor + and_mask


imgs = [(s, ico_image(s, render(s))) for s in SIZES]
out = struct.pack("<HHH", 0, 1, len(imgs))
offset = 6 + 16 * len(imgs)
entries = b""
for s, data in imgs:
    entries += struct.pack("<BBBBHHII", s if s < 256 else 0, s if s < 256 else 0,
                           0, 0, 1, 32, len(data), offset)
    offset += len(data)
with open(__file__.replace("gen_icon.py", "win.ico"), "wb") as f:
    f.write(out + entries + b"".join(d for _, d in imgs))
print("win.ico OK,", sum(len(d) for _, d in imgs), "bytes of images")
