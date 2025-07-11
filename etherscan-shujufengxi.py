import requests
import pandas as pd
import plotly.express as px
from datetime import datetime

# =================================================
# 1. 配置交易参数
# =================================================
ETHERSCAN_API_KEY = "Your Etherscan API Key" # Etherscan API Key
WALLET_ADDRESS = "0xdac17f958d2ee523a2206206994597c13d831ec7" # 分析的Etherscan上erc20的token地址
OUTPUT_EXCEL = "etherscan_analysis.xlsx" # 输出的 Excel 文件名

# ================================
# 2. 获取ERC20交易数据
# ================================
def get_erc20_transactions(api_key, wallet_address, pages=1, per_page=1000):
    base_url = "https://api.etherscan.io/api"
    all_transactions = [] # 存储所有交易数据

    for page in range(1, pages + 1):
        params = {
            "module": "account",
            "action": "tokentx", # 获取ERC20代币交易
            "address": wallet_address,
            "sort": "desc",
            "page": page,
            "offset": per_page,
            "apikey": api_key
        }

        try:
            response = requests.get(base_url, params=params, timeout=10).json()
        except Exception as e:
            print(f"X 网络错误: {e}")
            continue

         # 校验返回数据合法性
        if response.get('status') != '1' or not isinstance(response.get('result'), list):
            print(f"▲ API返回错误: Page {page}: {response.get('message', '未知错误')}")
            continue

        # 遍历交易记录提取需要的字段
        for tx in response['result']:
            try:
                timestamp_key = 'timeStamp' if 'timeStamp' in tx else 'timestamp'
                timestamp = int(tx.get(timestamp_key, 0))
                gas_used = int(tx.get('gasUsed', tx.get('gas', 0)))
                token_decimal = int(tx.get('tokenDecimal', 18)) # 获取代币精度
                all_transactions.append({
                    "tx_hash": tx.get('hash', ''),
                    "timestamp": timestamp,
                    "datetime": datetime.fromtimestamp(timestamp) if timestamp > 0 else None,
                    "gas_used": gas_used,
                    "gas_price": int(tx.get('gasPrice', 0)) / 1e18, # wei 转 ETH
                    "value": float(tx.get('value', 0)) / (10 ** token_decimal),
                    "contract_address": tx.get('contractAddress', ''),
                    "from_address": tx.get('from', ''),
                    "to_address": tx.get('to', ''),
                    "token_symbol": tx.get('tokenSymbol', '')
                })
            except Exception as e:
                print(f"▲ 解析交易时出错: {e}")
                continue

        print(f"✔ 第 {page} 页已完成，累计交易数: {len(all_transactions)}")

    return pd.DataFrame(all_transactions)

# 3. 数据清洗
def clean_data(df):
    df = df.drop_duplicates('tx_hash')  # 去除重复交易
    df = df[df['gas_used'] > 21000]  # 过滤掉可能的无效交易
    df = df[df['value'] > 0]  # 排除零交易金额
    df['tx_fee_eth'] = df['gas_used'] * df['gas_price']  # 手续费计算
    df['hour_of_day'] = df['datetime'].dt.hour  # 提取交易小时
    df['day_of_week'] = df['datetime'].dt.dayofweek  # 提取交易星期几
    # 按交易金额分段（用于图表展示）
    df['value_category'] = pd.cut(
        df['value'],
        bins=[0, 0.001, 0.01, 0.1, 1, 10, 100, float('inf')],
        labels=['nano', 'micro', 'small', 'medium', 'large', 'xlarge', 'huge']
    )
    return df

# 4. 生成雷达图
def generate_radar_chart(df):
    daily_tx = df.groupby(df['datetime'].dt.date).size()
    stats = pd.DataFrame({
        "Metric": [
            "平均交易金额(ETH)",
            "最大单笔交易(ETH)",
            "日均交易次数",
            "交易时间集中度",
            "平均手续费(ETH)",
            "合约集中度"
        ],
        "Value": [
            df['value'].mean(),
            df['value'].max(),
            daily_tx.mean(),
            1 - (daily_tx.std() / daily_tx.mean()), # 标准差越小，集中度越高
            df['tx_fee_eth'].mean(),
            1 - len(df['contract_address'].unique()) / len(df) # 越接近1越集中
        ],
        "Description": [
            "所有交易的平均金额",
            "最大单笔交易金额",
            "每天平均交易次数",
            "值越大表示交易时间越集中",
            "每笔交易平均支付的手续费",
            "值越大表示交易对象越集中"
        ]
    })

    # 部分指标进行归一化处理（0~1）
    normalize_cols = ['平均交易金额(ETH)', '最大单笔交易(ETH)', '平均手续费(ETH)']
    for col in normalize_cols:
        if col in stats['Metric'].values:
            mask = stats['Metric'] == col
            stats.loc[mask, 'Value'] = stats.loc[mask, 'Value'] / stats.loc[mask, 'Value'].max()

    # 使用 plotly 画雷达图
    fig = px.line_polar(
        stats,
        r="Value",
        theta="Metric",
        line_close=True,
        title="ERC20交易特征雷达图 (标准化指标)",
        template="plotly_dark",
        hover_data=["Description"]
    )
    fig.update_traces(
        fill='toself',
        hovertemplate="<b>%{theta}</b><br>值: %{r:.3f}<br>%{customdata[0]}<extra></extra>"
    )
    fig.update_layout(
        polar=dict(
            radialaxis=dict(
                visible=True,
                range=[0, 1.1],
                tickvals=[0, 0.5, 1],
                ticktext=["低", "中", "高"]
            )
        ),
        margin=dict(t=50, b=50, l=50, r=50),
        hoverlabel=dict(
            bgcolor="white",
            font_size=12,
            font_family="Arial"
        )
    )

    # 打印解释性分析
    print("\n📌 雷达图分析解读：")
    for _, row in stats.iterrows():
        level = "高" if row["Value"] > 0.66 else "中" if row["Value"] > 0.33 else "低"
        print(f"- {row['Metric']}（{row['Description']}）：{level} ({row['Value']:.2f})")

    return fig

# 5. 生成文本分析报告
def generate_analysis_report(df):
    report = []
    total_tx = len(df)
    unique_contracts = len(df['contract_address'].unique())
    time_span = (df['datetime'].max() - df['datetime'].min()).days
    avg_daily_tx = total_tx / time_span if time_span > 0 else total_tx

    # 基本统计
    report.append("📊 ERC20交易数据分析报告")
    report.append("="*50)
    report.append(f"📅 分析时间范围: {df['datetime'].min().date()} 至 {df['datetime'].max().date()}")
    report.append(f"🔢 总交易量: {total_tx} 笔")
    report.append(f"🏷️ 交互合约数量: {unique_contracts} 个")
    report.append(f"📈 日均交易量: {avg_daily_tx:.1f} 笔/天")

    # 交易金额分析
    value_stats = df['value'].describe()
    report.append("\n💰 交易金额分析:")
    report.append(f"- 平均交易金额: {value_stats['mean']:.4f} ETH")
    report.append(f"- 最大单笔交易: {value_stats['max']:.4f} ETH")
    report.append(f"- 75%交易小于: {value_stats['75%']:.4f} ETH")

    # 手续费分析
    fee_stats = df['tx_fee_eth'].describe()
    report.append("\n⛽ 交易费用分析:")
    report.append(f"- 平均交易费: {fee_stats['mean']:.6f} ETH")
    report.append(f"- 最高交易费: {fee_stats['max']:.6f} ETH")
    report.append(f"- 总交易费用: {df['tx_fee_eth'].sum():.6f} ETH")

    # 交易活跃时间
    hour_dist = df['hour_of_day'].value_counts().nlargest(3)
    report.append("\n🕒 交易时间模式:")
    report.append("- 最活跃交易时段(UTC):")
    for hour, count in hour_dist.items():
        report.append(f"  - {hour}:00-{hour+1}:00 ({count}笔, {count/total_tx:.1%})")

    # 合约地址
    top_contracts = df['contract_address'].value_counts().nlargest(3)
    report.append("\n📌 主要交互合约:")
    for addr, count in top_contracts.items():
        symbol = df[df['contract_address']==addr]['token_symbol'].iloc[0]
        report.append(f"  - {symbol} ({addr[:6]}...{addr[-4:]}) - {count}笔 ({count/total_tx:.1%})")

    # 异常检测提示
    if value_stats['max'] > 10 * value_stats['75%']:
        report.append("\n⚠️ 异常检测: 存在显著大额交易")
    if fee_stats['max'] > 10 * fee_stats['75%']:
        report.append("⚠️ 异常检测: 存在高gas费交易")
    return "\n".join(report)

# 主流程
if __name__ == "__main__":
    print("正在获取ERC20交易数据...")
    df_raw = get_erc20_transactions(ETHERSCAN_API_KEY, WALLET_ADDRESS, pages=1)

    if df_raw.empty:
        print("未获取到有效数据，请检查API Key和地址是否正确。")
    else:
        print("正在清洗数据...")
        df_clean = clean_data(df_raw)

        # 保存数据到 Excel
        print("正在保存为Excel文件...")
        with pd.ExcelWriter(OUTPUT_EXCEL) as writer:
            df_raw.to_excel(writer, sheet_name='Raw_Data', index=False)
            df_clean.to_excel(writer, sheet_name='Cleaned_Data', index=False)
            pd.DataFrame({
                "统计项": ["总交易数", "唯一合约数", "时间范围", "平均Gas费用(ETH)"],
                "值": [
                    len(df_clean),
                    len(df_clean['contract_address'].unique()),
                    f"{df_clean['datetime'].min()} 到 {df_clean['datetime'].max()}",
                    df_clean['tx_fee_eth'].mean()
                ]
            }).to_excel(writer, sheet_name='Summary', index=False)

        print(f"✔ 数据已保存至 {OUTPUT_EXCEL}")

        print("正在生成雷达图...")
        fig = generate_radar_chart(df_clean)
        fig.show()

        print("\n正在生成详细分析报告...")
        analysis_report = generate_analysis_report(df_clean)
        print("\n" + analysis_report)
