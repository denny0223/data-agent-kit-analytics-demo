# Data Agent Kit Analytics Demo

**[開啟互動式儀表板](https://denny.one/data-agent-kit-analytics-demo/)**

2026 年 10 月 27 日 [GDG Cloud Taipei / DevFest 暖身場：Google Cloud 與 AI 技術應用小聚](https://gdg.community.dev/events/details/google-gdg-cloud-taipei-presents-gdg-cloud-taipei-devfest-nuan-shen-chang-google-cloud-yu-ai-ji-shu-ying-yong-xiao-ju/)講題「使用 Data Agent Kit 與 Antigravity IDE 進行資料分析」的實作與展示程式碼。

以 Google Codelabs [使用 Data Agent Kit 和 Antigravity IDE 進行分析](https://codelabs.developers.google.com/dak-analytics-eng-antigravity-ide?hl=zh-tw)為基礎，使用 Cymbal Pets 範例資料，透過 BigQuery、Cloud SQL 與 Cloud Storage 調查平均訂單金額（AOV）下降的原因，建立 dbt 模型，並將分析結果整理成互動式儀表板。

## 內容

- `index.html`：分享現場使用的單頁儀表板，可切換月份、AOV、營收與訂單數，並查看通路組成與 SQL 範例。
- `dbt/models/staging/`：BigQuery 訂單與訂單明細，以及經由 `EXTERNAL_QUERY` 讀取的 Cloud SQL 客戶、寵物資料。
- `dbt/models/marts/fct_order_analysis.sql`：維持每筆訂單一列，先彙整訂單明細與每位客戶的寵物資料，再聯結。
- `dbt/models/**/*.yml`：來源定義與唯一性、非空值測試。

儀表板內嵌的是 lab 查詢結果快照，涵蓋 2024 年 8 月至 2025 年 1 月；頁面不會連線到 Google Cloud，也不會隨 `dbt build` 自動更新。頁面中的預測與毛利摘要來自分享時的分析結果。

## 瀏覽儀表板

可以直接使用上方線上展示，或下載並開啟 `index.html`。也可以在 repo 根目錄執行：

```bash
python -m http.server 8000
```

開啟 <http://localhost:8000/>。版面使用 Google 提供的 Tailwind CSS 瀏覽器腳本，需要網路載入樣式；「下載 HTML」會保存頁面，仍保留此樣式依賴。

## 執行 dbt

先依官方 lab 建立 Google Cloud 資源，並完成 DAK 與應用程式預設憑證（ADC）設定。這個 repo 不包含雲端資源佈建腳本。

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp dbt/profiles.example.yml dbt/profiles.yml
export GOOGLE_CLOUD_PROJECT=your-project-id
dbt build --project-dir dbt --profiles-dir dbt
```

`dbt/profiles.yml` 是本機設定，不會提交。請使用自己的 Google Cloud project，並確認 `cymbal_pets` dataset 已由 lab 建立。來源資料的 project 會跟隨 dbt target。

這次實作的 BigQuery location 是 `US`，Cloud SQL 聯合查詢使用 `us.cymbal-pets-cloudsql`。若你的 lab 使用 `us-central1` 或其他位置，請同步調整 `dbt/profiles.yml` 的 `location`，以及 `stg_customers.sql`、`stg_pet_profiles.sql` 中的連線名稱，與實際資源一致。

分享準備時的建置紀錄為 5 個模型成功、23 項測試通過。重跑會在自己的 Google Cloud 專案執行查詢與建立模型，並可能產生費用；完成 lab 後請依官方清理步驟處理資源。

## GitHub Pages

`gh-pages` 同時保存原始碼與網站檔案，GitHub Pages 從分支根目錄發布。

直接修改 `index.html` 並推送 `gh-pages`，即可更新線上儀表板。
