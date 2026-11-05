# -*- coding: utf-8 -*-
"""
講義 PDF 是整頁圖片（pypdf 抽不到字），用 OCR：PyMuPDF 把每頁轉成圖、RapidOCR（純 pip、中文模型內建）認字。
輸出到 00money\講義_text\（覆蓋原本沒字的檔），每頁加頁碼，一個檔最多 3 MB。
第一次會自動 pip install pymupdf rapidocr-onnxruntime（約 60 MB，要網路）。336 頁大約 10～25 分鐘，可以中途關掉，再跑會跳過已經做完的 PDF。

用法：雙擊「講義OCR.bat」，或 python pdf_ocr.py [講義資料夾] [--dpi 150]
"""
import os, sys, io, re, time, subprocess, argparse

HERE = os.path.dirname(os.path.abspath(__file__))


def ensure(pkg, mod):
    try:
        return __import__(mod)
    except ImportError:
        print("  安裝 %s …" % pkg, flush=True)
        subprocess.call([sys.executable, "-m", "pip", "install", "--quiet", pkg])
        return __import__(mod)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src", nargs="?", default=os.path.join(os.path.dirname(HERE), "講義"))
    ap.add_argument("--dpi", type=int, default=150)
    ap.add_argument("--redo", action="store_true", help="已經 OCR 過的也重做")
    a = ap.parse_args()
    fitz = ensure("pymupdf", "fitz")
    ensure("rapidocr-onnxruntime", "rapidocr_onnxruntime")
    from rapidocr_onnxruntime import RapidOCR
    ocr = RapidOCR()
    out_dir = os.path.join(HERE, "講義_text"); os.makedirs(out_dir, exist_ok=True)
    if not os.path.isdir(a.src):
        print("  找不到講義資料夾：%s" % a.src); return 1
    pdfs = sorted(f for f in os.listdir(a.src) if f.lower().endswith(".pdf"))
    print("  %d 個 PDF，OCR 中（每頁約 1～4 秒）…" % len(pdfs), flush=True)
    t0 = time.time(); done_pages = 0; summary = []
    for fn in pdfs:
        base = os.path.splitext(fn)[0]
        out_p = os.path.join(out_dir, base + ".md")
        if not a.redo and os.path.exists(out_p):
            with io.open(out_p, "r", encoding="utf-8", errors="ignore") as f:
                head = f.read(200)
            if "OCR" in head:
                print("  %s 已經 OCR 過，跳過" % fn); continue
        try:
            doc = fitz.open(os.path.join(a.src, fn))
        except Exception as e:
            print("  %s 開不了：%s" % (fn, str(e)[:80])); continue
        n = len(doc); parts = []; n_empty = 0; n_chars = 0
        for i in range(n):
            page = doc[i]
            pix = page.get_pixmap(dpi=a.dpi)
            try:
                res, _ = ocr(pix.tobytes("png"))
            except Exception as e:
                res = None
            lines = []
            if res:
                rows = []
                for box, txt, score in res:
                    ys = [p[1] for p in box]; xs = [p[0] for p in box]
                    rows.append((round(sum(ys) / len(ys) / 18), min(xs), txt))
                rows.sort()
                cur_y = None; line = []
                for y, x, txt in rows:
                    if cur_y is None or y == cur_y:
                        line.append(txt)
                    else:
                        lines.append(" ".join(line)); line = [txt]
                    cur_y = y
                if line: lines.append(" ".join(line))
            t = "\n".join(lines).strip()
            if len(t) < 10:
                n_empty += 1; t = "[這頁 OCR 認不出字]"
            n_chars += len(t)
            parts.append("\n\n===== 第 %d 頁 =====\n%s" % (i + 1, t))
            done_pages += 1
            if (i + 1) % 10 == 0 or i + 1 == n:
                el = time.time() - t0
                print("    %s  %d/%d 頁  %.0f 秒" % (fn, i + 1, n, el), flush=True)
        text = "# %s（OCR，%d 頁，%d 頁認不出字，%d 字）\n" % (fn, n, n_empty, n_chars) + "".join(parts)
        data = text.encode("utf-8"); MAX = 3 * 1024 * 1024; pos = 0; k = 0
        while pos < len(data):
            chunk = data[pos:pos + MAX]
            cut = chunk.rfind("\n===== ".encode("utf-8")) if pos + MAX < len(data) else len(chunk)
            if cut <= 0: cut = len(chunk)
            k += 1
            name = "%s%s.md" % (base, "" if (pos == 0 and pos + cut >= len(data)) else "_part%d" % k)
            with io.open(os.path.join(out_dir, name), "wb") as f:
                f.write(data[pos:pos + cut])
            pos += cut
        summary.append((fn, n, n_empty, n_chars))
        print("  %s：%d 頁，%d 頁認不出字，共 %d 字" % (fn, n, n_empty, n_chars), flush=True)
    with io.open(os.path.join(out_dir, "_摘要_OCR.txt"), "w", encoding="utf-8") as f:
        for fn, n, n_empty, n_chars in summary:
            f.write("%s\t%d 頁\t%d 頁認不出\t%d 字\n" % (fn, n, n_empty, n_chars))
    print("\n  完成（%.0f 分）。跟 Claude 說「講義 OCR 好了」。" % ((time.time() - t0) / 60))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n已中斷，再跑會接著做還沒做的 PDF。"); sys.exit(130)
    except Exception as e:
        import traceback; traceback.print_exc()
        print("\n失敗：%s" % str(e)[:300]); sys.exit(1)
