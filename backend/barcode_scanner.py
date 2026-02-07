from __future__ import annotations
from dataclasses import dataclass
from typing import List
import numpy as np
import cv2
from PIL import Image, ImageOps
import io

@dataclass
class BarcodeResult:
    type: str
    data: str
    rect: tuple  # (x,y,w,h)

def _decode_pyzbar(img_gray) -> List[BarcodeResult]:
    from pyzbar.pyzbar import decode
    out = []
    for obj in decode(img_gray):
        s = obj.data.decode("utf-8", errors="ignore").strip()
        if s:
            x, y, w, h = obj.rect
            out.append(BarcodeResult(obj.type, s, (x, y, w, h)))
    return out

def _try_decode_with_rotations(gray: np.ndarray) -> List[BarcodeResult]:
    # 0/90/180/270
    imgs = [
        gray,
        cv2.rotate(gray, cv2.ROTATE_90_CLOCKWISE),
        cv2.rotate(gray, cv2.ROTATE_180),
        cv2.rotate(gray, cv2.ROTATE_90_COUNTERCLOCKWISE),
    ]
    for g in imgs:
        # 多倍率放大
        for s in [1.0, 1.5, 2.0, 3.0]:
            gg = cv2.resize(g, None, fx=s, fy=s, interpolation=cv2.INTER_CUBIC) if s != 1.0 else g

            # 不要只做二值化：同時試 raw / CLAHE / adaptive
            variants = [gg]
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            variants.append(clahe.apply(gg))
            variants.append(cv2.adaptiveThreshold(gg, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                                cv2.THRESH_BINARY, 31, 2))

            for v in variants:
                res = _decode_pyzbar(v)
                if res:
                    return res
    return []

def _find_barcode_like_rois(bgr: np.ndarray):
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (3,3), 0)

    gradX = cv2.Sobel(gray, ddepth=cv2.CV_32F, dx=1, dy=0, ksize=-1)
    gradY = cv2.Sobel(gray, ddepth=cv2.CV_32F, dx=0, dy=1, ksize=-1)
    gradient = cv2.subtract(gradX, gradY)
    gradient = cv2.convertScaleAbs(gradient)

    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (25, 7))
    closed = cv2.morphologyEx(gradient, cv2.MORPH_CLOSE, kernel)
    closed = cv2.erode(closed, None, iterations=2)
    closed = cv2.dilate(closed, None, iterations=2)

    _, thresh = cv2.threshold(closed, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    cnts, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    cnts = sorted(cnts, key=cv2.contourArea, reverse=True)

    rois = []
    H, W = gray.shape[:2]
    for c in cnts[:8]:
        x, y, w, h = cv2.boundingRect(c)
        if w < 80 or h < 30:
            continue
        pad = 12
        x0 = max(0, x - pad); y0 = max(0, y - pad)
        x1 = min(W, x + w + pad); y1 = min(H, y + h + pad)
        rois.append((x0, y0, x1, y1))
    return rois

def decode_barcodes_from_bytes(image_bytes: bytes) -> List[BarcodeResult]:
    # ✅ PIL 讀 bytes + EXIF transpose
    pil = Image.open(io.BytesIO(image_bytes))
    pil = ImageOps.exif_transpose(pil).convert("RGB")
    rgb = np.array(pil)
    bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)

    # 1) 先試整張（有些情況直接就會成功）
    gray_full = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    res = _try_decode_with_rotations(gray_full)
    if res:
        return res

    # 2) 找 ROI 再解碼（穩很多）
    rois = _find_barcode_like_rois(bgr)
    for (x0, y0, x1, y1) in rois:
        roi = bgr[y0:y1, x0:x1]
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        res = _try_decode_with_rotations(gray)
        if res:
            return res

    return []

