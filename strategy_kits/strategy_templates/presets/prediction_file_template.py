import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# ==========================================
# 1. 在这里实现你的选股逻辑
# ==========================================
def my_strategy_logic(date_str):
    """
    输入: date_str (YYYY-MM-DD)
    输出: list of dict, 每个 dict 包含 'code' 和 'weight' (可选)
    """
    print(f"正在计算 {date_str} 的选股...")
    
    # 示例：随机选择 5 只股票
    # 在实际使用中，这里应该是你的核心逻辑
    # 比如：读取当天的行情，计算指标，筛选股票
    
    # 模拟一些股票代码 (这里只是示例)
    # 注意：股票代码建议使用 6 位数字字符串
    sample_pool = ["000001", "000002", "600000", "600036", "000333", "601318", "600519"]
    
    # 模拟随机选股
    selected_codes = np.random.choice(sample_pool, size=3, replace=False)
    
    # 构建结果
    results = []
    for code in selected_codes:
        results.append({
            "code": code,
            "weight": 1.0 / len(selected_codes)  # 等权重
        })
        
    return results

# ==========================================
# 2. 生成回测数据文件
# ==========================================
def generate_prediction_file(start_date, end_date, output_file="my_strategy_predictions.csv"):
    dates = pd.date_range(start=start_date, end=end_date, freq="B") # B for business days
    
    all_records = []
    
    for date in dates:
        date_str = date.strftime("%Y-%m-%d")
        
        # 调用你的策略逻辑
        daily_picks = my_strategy_logic(date_str)
        
        for pick in daily_picks:
            all_records.append({
                "date": date_str,
                "code": pick["code"],
                "weight": pick.get("weight", 1.0)
            })
            
    # 保存为 CSV
    df = pd.DataFrame(all_records)
    df.to_csv(output_file, index=False)
    print(f"\n成功生成策略文件: {output_file}")
    print(f"包含记录数: {len(df)}")
    print(f"日期范围: {df['date'].min()} 到 {df['date'].max()}")
    
    # 显示最后几天的选股（即“最新推荐”）
    latest_date = df['date'].max()
    print(f"\n=== 最新推荐 ({latest_date}) ===")
    latest_picks = df[df['date'] == latest_date]
    print(latest_picks[['code', 'weight']])

if __name__ == "__main__":
    # 设置回测时间段
    START_DATE = "2024-01-01"
    END_DATE = datetime.now().strftime("%Y-%m-%d") # 到今天
    
    generate_prediction_file(START_DATE, END_DATE)
