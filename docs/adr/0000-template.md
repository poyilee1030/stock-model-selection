# ADR-NNNN：<標題>

- 狀態：提議 | 接受 | 取代（由 ADR-XXXX） | 撤回
- 日期：YYYY-MM-DD
- 相關 step：step-N

> 何時需要 ADR：本專案要計算一個屬於 Data Center canonical 類型的數值（見 `docs/contracts/feature-ownership.md` §1），或要偏離 `docs/decisions.md` 的任何決議。
> 檔名：`docs/adr/NNNN-<簡短名稱>.md`，編號遞增，不重複使用。

## 背景

要解決什麼問題？為什麼現在要決定？

## Data Center 的現況

- Data Center 是否已提供這個數值？若有，為什麼不能用？
- 是否已向 Data Center 申請？申請的結果或預計時程。

## 決議

要做什麼，精確到公式、輸入資料集與欄位、時間窗口、缺值處理。

## 替代方案

列出考慮過的其他做法，以及不採用的理由。

## 影響

- PIT：這個數值使用哪些輸入、在 T_C 是否都可見、達到哪個 PIT 層級。
- 與 Data Center 的一致性：Data Center 之後若提供同一個指標，如何切換、如何比較差異。
- 受影響的 step、契約與測試。

## 退場條件

在什麼情況下撤回本 ADR，例如 Data Center 提供了同樣的指標。
