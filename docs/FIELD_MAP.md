# 误差配套实验：数据表字段地图

> 由 `ExamConfig_3.xml` 的 Para 顺序生成；界面顺序 = XML 顺序。
> 6× 表是“行=量、列=次数1..6”；INDEX 行是次数，不用填。

## 薄板（TestTarget #1）

| # | 字段名 | 界面标签 | 类型 | 分值 | 填法/示例 |
|---|---|---|---|---|---|
| 1 | `InsUncertainPara` | (1) 根据参数计算下列B类不确定度 | TList(4列; INDEX,GZCUncertain,YBKCUncertain,QFCUncertain) | 0 | 3 行 × 4 列（0 分）；例 钢直尺行=0.000002040816, 0.000027700831, 0.010000000000, 0.000004271816 |
| 2 | `Choose1` | (2) 选择测量带孔薄板长度的仪器(A：钢直尺B：游标卡尺C：千分尺)： | string | 2 | A |
| 3 | `Choose2` | (3) 选择测量带孔薄板宽度的仪器(A：钢直尺B：游标卡尺C：千分尺)： | string | 2 | B |
| 4 | `Choose3` | (4) 选择测量带孔薄板厚度的仪器(A：钢直尺B：游标卡尺C：千分尺)： | string | 2 | C |
| 5 | `Choose4` | (5) 选择测量带孔薄板孔径的仪器(A：钢直尺B：游标卡尺C：千分尺)： | string | 2 | A |
| 6 | `GBDataPara` | (6) 将测得的带孔薄板的长、宽、厚和孔径记录到表格中： | TList(6列; INDEX,GBLengthData,GBWidthData,GBThicknessData,GBDiameterData) | 24 | 6 列 × 4 行：L/B/H/D；例 L=140.0, B=38.04, H=1.997, D=6.8 |
| 7 | `GBLengthAvg` | (7) 带孔薄板长度L的平均值(mm)= | double | 2 | 140.0 |
| 8 | `GBLengthBZC` | (8) 带孔薄板长度的标准差S= | double | 0 | 0.0 |
| 9 | `GBLengthUncertainA` | (9) 带孔薄板长度的A类不确定度ΔA= | double | 1 | 0.0 |
| 10 | `GBLengthUncertainB` | (10) 带孔薄板长度的B类不确定度ΔB= | double | 1 | 0.12 |
| 11 | `GBLengthUncertain` | (11) 带孔薄板长度的不确定度ΔL= | double | 1 | 0.12 |
| 12 | `GBWidthAvg` | (12) 带孔薄板宽度B的平均值(mm)= | double | 2 | 38.04 |
| 13 | `GBWidthBZC` | (13) 带孔薄板宽度的标准差S= | double | 0 | 0.0 |
| 14 | `GBWidthUncertainA` | (14) 带孔薄板宽度的A类不确定度ΔA= | double | 1 | 0.0 |
| 15 | `GBWidthUncertainB` | (15) 带孔薄板宽度的B类不确定度Δb= | double | 1 | 0.012 |
| 16 | `GBWidthUncertain` | (16) 带孔薄板宽度的不确定度ΔB= | double | 1 | 0.012 |
| 17 | `GBThicknessAvg` | (17) 带孔薄板厚度H的平均值(mm)= | double | 2 | 1.997 |
| 18 | `GBThicknessBZC` | (18) 带孔薄板厚度的标准差S= | double | 0 | 0.0 |
| 19 | `GBThicknessUncertainA` | (19) 带孔薄板厚度的A类不确定度ΔA= | double | 1 | 0.0 |
| 20 | `GBThicknessUncertainB` | (20) 带孔薄板厚度的B类不确定度ΔB= | double | 1 | 0.0024 |
| 21 | `GBThicknessUncertain` | (21) 带孔薄板厚度的不确定度ΔH= | double | 1 | 0.0024 |
| 22 | `GBDiameterAvg` | (22) 带孔薄板孔径D的平均值(mm)= | double | 2 | 6.8 |
| 23 | `GBDiameterBZC` | (23) 带孔薄板孔径的标准差S= | double | 0 | 0.0 |
| 24 | `GBDiameterUncertainA` | (24) 带孔薄板孔径的A类不确定度ΔA= | double | 1 | 0.0 |
| 25 | `GBDiameterUncertainB` | (25) 带孔薄板孔径的B类不确定度ΔB= | double | 1 | 0.12 |
| 26 | `GBDiameterUncertain` | (26) 带孔薄板孔径的不确定度ΔD= | double | 1 | 0.12 |
| 27 | `GBV` | (27) 计算带孔薄板的体积V(mm³)= | double | 2 | 10272.60 |
| 28 | `GBVRelativeUncertain` | (28) 计算体积的相对不确定度ΔV/V= | double | 1 | 0.0019 |
| 29 | `GBVUncertain` | (29) 计算体积的不确定度ΔV(mm³)= | double | 1 | 20 |
| 30 | `GBVExpression` | (30) 带孔薄板体积表达式V±ΔV： | string | 3 | 10273±20 |
| 31 | `IsMeasureGBWidthUseYBKC` | 游标卡尺读数是否准确： | bool | 1 | （隐藏，不显示；由 6× 小数位自动判定） |
| 32 | `IsMeasureGBThicknessUseQFC` | 千分尺读数是否准确： | bool | 1 | （隐藏，不显示；由 6× 小数位自动判定） |

## 100张纸（TestTarget #2）

| # | 字段名 | 界面标签 | 类型 | 分值 | 填法/示例 |
|---|---|---|---|---|---|
| 1 | `InsUncertainPara2` | (1) 根据参数计算下列B类不确定度 | TList(3列; INDEX,GZCUncertain2,YBKCUncertain2,QFCUncertain2) | 0 | 3 行 × 3 列（0 分）；例 钢直尺行=0.000000694444, 0.000001384083, 0.000711111111 |
| 2 | `Choose5` | (2) 选择测量100张纸长度的仪器(A：钢直尺B：游标卡尺C：千分尺)： | string | 2 | A |
| 3 | `Choose6` | (3) 选择测量100张纸宽度的仪器(A：钢直尺B：游标卡尺C：千分尺)： | string | 2 | A |
| 4 | `Choose7` | (4) 选择测量100张纸厚度的仪器(A：钢直尺B：游标卡尺C：千分尺)： | string | 2 | C |
| 5 | `PaperDataPara` | (5) 将测得的100张纸的长、宽和厚度记录到实验数据表格中： | TList(6列; INDEX,PaperLengthData,PaperWidthData,PaperThicknessData) | 18 | 6 列 × 3 行：L/B/H；例 L=240.9, B=170.90, H=7.499 |
| 6 | `PaperLengthAvg` | (6) 100张纸长度L的平均值(mm)= | double | 2 | 240.9 |
| 7 | `PaperWidthAvg` | (7) 100张纸宽度B的平均值(mm)= | double | 2 | 170.90 |
| 8 | `PaperThicknessAvg` | (8) 100张纸厚度H的平均值(mm)= | double | 2 | 7.499 |
| 9 | `PaperV` | (9) 计算1张纸的体积V(mm³)= | double | 2 | 3087.32 |
| 10 | `PaperVRelativeUncertain` | (10) 计算体积的相对不确定度ΔV/V= | double | 1 | 0.00089 |
| 11 | `PaperVUncertain` | (11) 计算体积的不确定度ΔV(mm³)= | double | 1 | 2.8 |
| 12 | `PaperVExpression` | (12) 1张纸体积表达式V±ΔV： | string | 3 | 3087.3±2.8 |
| 13 | `IsMeasurePaperWidthUseYBKC` | 千分尺读数是否准确： | bool | 2 | （隐藏，不显示；由 6× 小数位自动判定） |

