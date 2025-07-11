# 📊 Etherscan ERC20交易数据分析工具

本项目是一个基于 Python 的以太坊 ERC20 交易数据分析脚本，使用 Etherscan API 获取指定地址的交易记录，进行数据清洗、雷达图可视化与文本报告生成。

---

## 🚀 功能特色

- 自动抓取指定地址的 ERC20 交易数据
- 清洗无效数据，计算 gas 费、交易时间等统计维度
- 生成标准化雷达图（使用 Plotly）
- 输出详细的交易行为分析报告
- 支持导出为 Excel 文件

---

## 🔧 使用方式
1.进入etherscan官网，找到API看板，新建API
https://github.com/anbai123456/etherscan-data-analysis/blob/main/etherscan-analysis%20-1.png

2.替换etherscan-analysis.py文件中的API key部分即可
