# V14: chained multi-year horizons (C0, five seeds, fixed 150 epochs)

Every year after the last observed one receives its history inputs from the ensemble's own
estimate of the previous year; covariates frozen at the last observed year. Reference:
historical average of the years up to the last observed one. Data: horizons.json.

| Source | Last observed -> target | h | District MAE C0 / hist. | Spearman C0 / hist. | Cell AUC C0 / hist. | Cell AP C0 / hist. |
|---|---|---:|---:|---:|---:|---:|
| CENACOM | 2015 -> 2016 | 1 | 1.714 / 1.863 | 0.968 / 0.952 | 0.981 / 0.951 | 0.903 / 0.855 |
| CENACOM | 2015 -> 2017 | 2 | 2.579 / 2.376 | 0.933 / 0.933 | 0.977 / 0.952 | 0.881 / 0.838 |
| CENACOM | 2014 -> 2015 | 1 | 2.241 / 2.153 | 0.928 / 0.924 | 0.920 / 0.500 | 0.670 / 0.147 |
| CENACOM | 2014 -> 2016 | 2 | 1.946 / 1.943 | 0.962 / 0.942 | 0.925 / 0.500 | 0.709 / 0.153 |
| CENACOM | 2014 -> 2017 | 3 | 2.290 / 2.344 | 0.939 / 0.925 | 0.933 / 0.500 | 0.710 / 0.137 |
| ONSV | 2023 -> 2024 | 1 | 0.569 / 0.607 | 0.817 / 0.817 | 0.926 / 0.785 | 0.355 / 0.294 |
| ONSV | 2022 -> 2023 | 1 | 0.572 / 0.603 | 0.803 / 0.801 | 0.935 / 0.732 | 0.431 / 0.254 |
| ONSV | 2022 -> 2024 | 2 | 0.563 / 0.606 | 0.804 / 0.780 | 0.926 / 0.724 | 0.371 / 0.240 |
| ONSV | 2021 -> 2022 | 1 | 0.578 / 0.642 | 0.828 / 0.817 | 0.930 / 0.650 | 0.352 / 0.170 |
| ONSV | 2021 -> 2023 | 2 | 0.607 / 0.677 | 0.772 / 0.726 | 0.928 / 0.636 | 0.372 / 0.167 |
| ONSV | 2021 -> 2024 | 3 | 0.579 / 0.686 | 0.791 / 0.721 | 0.922 / 0.639 | 0.348 / 0.167 |

In ONSV the network keeps its advantage up to three years ahead (cell AUC 0.92-0.93 at
every horizon). In CENACOM the cell ranking keeps its advantage at two and three years,
while the district MAE to 2017 loses (the 2017 level change, see performance-v10.md).
From 2014 the historical average has no located year, so its cell ranking is uninformative
(AUC 0.50). Horizons are evaluated on 2015-2017 and 2022-2024; no evidence exists for
2026-2027 themselves.
