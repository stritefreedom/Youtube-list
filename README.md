# 🎯 YouTube 播放清單整理專案（CSV版）

本專案用於解析 YouTube 播放清單，並輸出為 CSV 表格檔案。

---

# 📌 輸出格式

輸出檔案位置：

output/*.csv

欄位如下：

影片標題名稱,影片網址,說明

---

# 🧾 範例

紅蓮華 (鬼滅之刃OP),https://www.youtube.com/watch?v=xxxx,動畫OP
Unravel (東京喰種OP),https://www.youtube.com/watch?v=xxxx,動畫OP
遊戲戰鬥BGM合集,https://www.youtube.com/watch?v=xxxx,遊戲BGM

---

# 🧠 工作流程

## 1️⃣ 安裝環境

請安裝：

- Python
- yt-dlp

（可選）
- ffmpeg

---

## 2️⃣ 解析播放清單（不下載影片）

請先取得播放清單資訊：

yt-dlp --flat-playlist --dump-single-json "<播放清單網址>" > output/playlist.json

---

## 3️⃣ 使用播放清單名稱當檔名（重要）

請從 playlist.json 中取得：

playlist_title

並進行檔名處理：

- 移除非法字元（\/:*?"<>|）
- 去除前後空白
- 建議限制長度（避免過長）

---

## 4️⃣ 轉換為 CSV

請將：

output/playlist.json

轉換為：

output/<播放清單名稱>.csv

---

# 📊 轉換規則

## 欄位說明

| 欄位 | 說明 |
|------|------|
| 影片標題名稱 | YouTube 影片標題 |
| 影片網址 | https://www.youtube.com/watch?v=影片ID |
| 說明 | 使用者提供的「類型」 |

---

## 資料處理規則

- 移除標題中的：
  - 換行（\n）
  - 逗號（,）→ 建議轉空格
- 不下載影片
- 保持播放清單順序
- 若影片ID存在才輸出
- 可選：去除重複影片（依影片ID）


---

## ✔ 每個播放清單輸出一個 CSV

檔名使用「播放清單名稱」：

output/動畫OP合集.csv  
output/遊戲BGM精選.csv  

---

## ✔ 說明欄填入類型名稱

例如：

紅蓮華,https://...,動畫OP

---

# ⚠️ 注意事項

- ❌ 不下載影片
- ❌ 不增加其他欄位
- ✔ 僅做資料整理
- ✔ 所有輸出放在 output/

---

# 🚀 Codex 執行指示

請執行：

1. 使用 yt-dlp 取得 playlist.json
2. 讀取 playlist_title 作為檔名
3. 清理檔名（避免非法字元）
4. 解析 entries
5. 輸出 CSV（三欄）
6. 填入「說明」欄

---

# 🧩 任務摘要（給 Codex）

解析 YouTube 播放清單 → 輸出 CSV

檔名：
播放清單名稱.csv

欄位：
影片標題名稱
影片網址
說明（= 類型）

每個播放清單輸出一個檔案
