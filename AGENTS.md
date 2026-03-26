# AGENTS.md

## 專案說明
本專案為「漫畫翻譯嵌字桌面工具」。

請注意：
- 這是 **純本機桌面應用程式**
- **不是 Web App**
- 不要引入任何前後端架構（例如 React / API server）

---

## 技術棧（固定）

- Python 3.10+
- UI：PySide6
- OCR：PaddleOCR（後續可支援 MangaOCR）
- 圖像處理：OpenCV + Pillow
- API 呼叫：requests
- 金鑰管理：keyring
- 資料儲存：JSON（MVP）

---

## 核心原則

1. 所有功能必須在本機執行
2. API key 僅能儲存在本機（使用 keyring）
3. 不得將任何資料上傳到第三方伺服器（除了使用者主動呼叫 OpenAI / Gemini）
4. 不要實作帳號系統或登入系統
5. UI 必須為桌面視窗（PySide6）

---

## 開發優先順序（MVP）

請嚴格依照順序開發：

1. 主視窗（圖片載入）
2. 圖片顯示與縮放
3. 文字區資料模型（Region）
4. OCR 模組整合
5. 顯示 OCR 結果
6. 手動調整文字框
7. 翻譯模組（OpenAI）
8. 基本嵌字（draw text）
9. 匯出 PNG

---

## 不要做的事情（重要）

- ❌ 不要加入 Web 技術（React / Flask API server）
- ❌ 不要實作登入 / 帳號
- ❌ 不要做雲端儲存
- ❌ 不要實作複雜插件系統（MVP 階段）
- ❌ 不要過度設計架構

---

## 程式碼風格

- 模組化（core / ui / models 分離）
- 每個功能單一責任
- 使用 dataclass 定義資料結構
- 避免超過 500 行單一檔案

---

## 測試要求

每完成一個功能需確保：

- 程式可以啟動
- UI 不崩潰
- 功能可以基本操作

---

## API 使用規範

- API key 來源：使用者輸入
- 儲存方式：keyring
- 呼叫方式：requests（不可硬寫 key）

---

## 最終目標（MVP）

使用者可以：
1. 載入漫畫圖片
2. 偵測文字
3. 取得 OCR 文字
4. 呼叫 AI 翻譯
5. 將翻譯結果貼回圖片
6. 匯出 PNG
