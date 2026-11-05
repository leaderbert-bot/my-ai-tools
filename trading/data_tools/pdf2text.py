# -*- coding: utf-8 -*-
"""
把 Dropbox\講義 裡的 PDF 講義抽成文字檔（每頁加頁碼），存到 00money\講義_text\，一個檔最多 3 MB，給 Claude 讀。
- 只抽 PDF 裡本來就有的文字（PowerPoint 匯出的都有）。整頁是圖片的會記成「[圖片頁]」並統計；圖片頁太多再說，可能要 OCR。
- 第一次會自動安裝 pypdf（pip install pypdf）。
用法：雙擊「講義轉文字.bat」，或 python pdf2text.py [講義資料夾]
"""
import os, sys, io, re, subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(HERE), "講義")
OUT = os.path.join(HERE, "講義_text")
MAX = 3 * 1024 * 1024

try:
    import pypdf
except ImportError:
    print("  安裝 pypdf …")
    subprocess.call([sys.executable, "-m", "pip", "install", "--quiet", "pypdf"])
    import pypdf


def clean(t):
    t = t.replace("\x00", "")
    t = re.sub(r"[ \t　]+", " ", t)
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t.strip()


def main():
    if not os.path.isdir(SRC):
        print("  找不到講義資料夾：%s" % SRC); return 1
    os.makedirs(OUT, exist_ok=True)
    pdfs = sorted(f for f in os.listdir(SRC) if f.lower().endswith(".pdf"))
    print("  %d 個 PDF → %s" % (len(pdfs), OUT))
    summary = []
    for fn in pdfs:
        p = os.path.join(SRC, fn)
        try:
            r = pypdf.PdfReader(p)
        except Exception as e:
            print("  %s 讀不到：%s" % (fn, str(e)[:80])); continue
        n = len(r.pages); n_img = 0; parts = []
        for i, pg in enumerate(r.pages):
            try:
                t = clean(pg.extract_text() or "")
            except Exception:
                t = ""
            if len(t) < 30:
                n_img += 1; t = "[圖片頁，沒有文字]"
            parts.append("\n\n===== 第 %d 頁 =====\n%s" % (i + 1, t))
            if (i + 1) % 50 == 0:
                print("    %s  %d/%d 頁" % (fn, i + 1, n), flush=True)
        base = os.path.splitext(fn)[0]
        text = "# %s（%d 頁，%d 頁沒有文字）\n" % (fn, n, n_img) + "".join(parts)
        # 切成 ≤ 3 MB 的檔
        data = text.encode("utf-8"); k = 0; pos = 0
        while pos < len(data):
            chunk = data[pos:pos + MAX]
            cut = chunk.rfind("\n===== ".encode("utf-8")) if pos + MAX < len(data) else len(chunk)
            if cut <= 0: cut = len(chunk)
            k += 1
            name = "%s%s.md" % (base, "" if (pos == 0 and pos + cut >= len(data)) else "_part%d" % k)
            with io.open(os.path.join(OUT, name), "wb") as f:
                f.write(data[pos:pos + cut])
            pos += cut
        summary.append((fn, n, n_img, k))
        print("  %s：%d 頁，%d 頁沒有文字，存成 %d 個檔" % (fn, n, n_img, k))
    with io.open(os.path.join(OUT, "_摘要.txt"), "w", encoding="utf-8") as f:
        for fn, n, n_img, k in summary:
            f.write("%s\t%d 頁\t%d 頁沒有文字\t%d 檔\n" % (fn, n, n_img, k))
    print("\n  完成。跟 Claude 說「講義轉好了」。沒有文字的頁數如果超過一半，那份是圖片掃描檔，要另外想辦法。")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print("\n失敗：%s" % str(e)[:300]); sys.exit(1)
