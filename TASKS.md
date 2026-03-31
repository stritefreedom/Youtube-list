```md
# TASKS.md

## Phase 1：MVP

---

### Task 01：建立主視窗
- 建立 PySide6 應用程式
- 建立主視窗
- 顯示空畫面

完成條件：
- 程式可以啟動
- 視窗正常顯示

---

### Task 02：圖片載入
- 加入「開啟圖片」功能
- 顯示圖片於畫面

完成條件：
- 可載入 PNG / JPG
- 圖片正常顯示

---

### Task 03：圖片縮放與拖曳
- 支援縮放
- 支援拖曳畫面

完成條件：
- 滑鼠滾輪縮放
- 滑鼠拖曳移動

---

### Task 04：Region 資料模型
- 建立 Region dataclass
- 包含：
  - id
  - bbox
  - text

完成條件：
- 可建立 Region 物件

---

### Task 05：OCR 整合
- 整合 PaddleOCR
- 對圖片執行 OCR

完成條件：
- 回傳文字與 bbox

---

### Task 06：顯示文字框
- 將 OCR bbox 畫在畫面上

完成條件：
- 可視化文字區

---

### Task 07：手動調整文字框
- 可拖曳 bbox
- 可調整大小

完成條件：
- 使用者可修改位置

---

### Task 08：翻譯模組（OpenAI）
- 使用 requests 呼叫 API
- 傳入文字
- 回傳翻譯

完成條件：
- 能取得翻譯文字

---

### Task 09：嵌字功能
- 使用 Pillow/OpenCV 畫文字

完成條件：
- 翻譯文字顯示在圖片上

---

### Task 10：匯出 PNG
- 將結果儲存成圖片

完成條件：
- 匯出檔案可開啟

---

## Phase 2（暫不實作）

- Gemini 支援
- 術語系統
- JSON 專案
- 預覽視窗

---

## 進度紀錄

### 2026-03-31

- OCR 主流程已由 `core/ocr.py` 轉為以 `core/manga_ocr_pipeline.py` 為主（偵測文字框 + 逐框 OCR）。
- `core/ocr.py` 仍保留 `detect_regions` / `run_ocr` 對外介面，並保留 fixture fallback 行為，避免測試流程中斷。
- 測試 `tests/test_ocr_page001.py` 已更新為新模式 `manga_ocr_pipeline` 的斷言。
- `scripts/verify_real_ocr.py` 已改為使用目前主流程進行 OCR runtime 驗證。
