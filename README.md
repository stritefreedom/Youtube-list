# Manga Translator Studio

本專案是一款「本機漫畫翻譯嵌字工具」。

---

## 功能

- 漫畫文字區偵測
- OCR 文字辨識
- 使用 OpenAI / Gemini API 翻譯（使用者自備 API key）
- 自動嵌字
- 手動調整文字
- 匯出 PNG

---

## 特點

- 完全本機運行
- 不需登入
- 不使用雲端服務
- 支援自訂術語規則（未來）

---

## 開發環境

- Python 3.10+
- Windows（優先支援）

---

## 安裝（建議：乾淨環境 + Headless OpenCV）

```bash
bash scripts/setup_clean_env.sh
source .venv/bin/activate
```

此流程會在最後強制移除 GUI 版 OpenCV 套件並重新安裝：

- `opencv-python`（移除）
- `opencv-contrib-python`（移除）
- `opencv-python-headless==4.10.0.84`（重裝）

---

## 執行

```bash
source .venv/bin/activate
python app.py
```

---

## 專案結構

```text
.
├─ app.py
├─ ui/
├─ core/
├─ models/
├─ storage/
├─ scripts/
└─ tests/
```

---

## 使用方式（MVP）

1. 開啟程式
2. 載入圖片
3. 點擊「執行 OCR」
4. 在下方文字視窗查看 OCR 摘要與文字結果
5. 編輯文字框（開發中）
6. 點擊翻譯（開發中）
7. 匯出圖片（開發中）

---

## API Key 設定

使用者需自行提供：

- OpenAI API Key
- 或 Gemini API Key

Key 會儲存在本機（keyring）。

---

## 開發狀態

🚧 MVP 開發中

---

## 未來功能

- 批次處理
- 多頁專案
- 術語規則系統
- 高級排版
- 插件系統
