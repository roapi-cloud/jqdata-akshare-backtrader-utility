# Signal Pipeline - 通用量化信号流水线

> 基于缠论、RSRS、MESA、圆弧底、趋与势等多指标融合的 A 股量化交易系统。支持回测、实盘模拟、策略自动优选。

## 快速开始

```bash
# 1. 安装依赖
pip install numpy pandas akshare pyyaml backtrader statsmodels scipy

# 2. 验证安装
cd signal_pipeline
python validate.py

# 3. 运行回测
python main.py --mode backtest --symbol sh600000 --config config.yaml

# 4. 实盘模拟 (轮询模式)
python main.py --mode live --symbol sh600000 --config config.yaml --interval 60
```

## 项目结构

```
signal_pipeline/
├── config.yaml              # 主配置文件
├── main.py                  # 入口 CLI
├── validate.py              # 快速验证脚本
└── src/
    ├── core/                # 核心数据模型
    │   ├── models.py        # Signal, MarketData, FusedSignal
    │   ├── config.py        # 配置加载
    │   └── exceptions.py    # 自定义异常
    ├── data/                # 数据层
    │   ├── loader.py        # AkShare 数据获取 + 缓存
    │   └── preprocessor.py  # 清洗、对齐、特征工程
    ├── indicators/          # 指标生成器
    │   ├── base.py          # 抽象基类
    │   ├── registry.py      # 注册表 + 自动发现
    │   ├── strength_normalizer.py  # 动态强度归一化
    │   ├── chan_theory.py   # 缠论 (笔/线段/中枢/背驰)
    │   ├── patterns.py      # 圆弧底 + RSRS
    │   └── spectral.py      # MESA + 趋与势
    ├── fusion/              # 信号融合
    │   └── engine.py        # 加权融合 + 冲突消解
    ├── selector/            # 策略优选
    │   └── auto_router.py   # 动态权重 + 自动路由
    └── backtest/            # 回测引擎
        └── bt_wrapper.py    # Backtrader 适配器
```

## 核心设计

### 1. 动态强度归一化
解决牛市/熊市量纲差异问题：
```python
# 旧: strength = bi_length / ATR (牛市全1, 熊市全0)
# 新: 滚动分位数归一化
normalizer = StrengthNormalizer(history_window=250)
strength = normalizer.normalize(raw_value)  # 始终映射到 [0, 1]
```

### 2. 信号融合引擎
- **加权投票**: 各指标按权重贡献买卖分数
- **环境自适应**: 趋势市提升缠论/RSRS权重，震荡市提升MESA/圆弧底权重
- **冲突消解**: 买卖分数接近时自动降仓50%
- **共识奖励**: 3个以上指标同向时置信度+20%

### 3. 策略自动优选
```python
evaluator = StrategyEvaluator(window=60)
scores = evaluator.evaluate(signals_history, price_history)
# 输出: {'chan_theory': 0.85, 'rsrs': 0.72, 'mesa': 0.65, ...}

router = AutoRouter(evaluator)
weights = router.get_dynamic_weights(scores, base_weights)
# 自动融合历史表现与基础权重
```

### 4. 异常降级机制
任一指标计算失败时：
- 不中断流水线
- 生成 NEUTRAL 信号并标记 `fallback=True`
- 日志记录错误详情

## 配置说明 (config.yaml)

```yaml
pipeline:
  indicators:
    - name: chan_theory
      weight: 0.25
      params: {min_bi_kbars: 4, use_macd_div: true}
    - name: rsrs
      weight: 0.25
      params: {N: 18, M: 600}
    - name: mesa
      weight: 0.20
    - name: trend_momentum
      weight: 0.20
    - name: rounding_bottom
      weight: 0.10
  fusion:
    buy_threshold: 0.5
    sell_threshold: -0.5
    conflict_tolerance: 0.2
backtest:
  start: 2020-01-01
  end: 2023-12-31
  cash: 1000000
  commission: 0.001
```

## 扩展新指标

1. 继承 `BaseSignalGenerator`
2. 实现 `generate(self, data: MarketData) -> List[Signal]`
3. 设置 `name` 和 `min_history` 属性
4. 放入 `src/indicators/` 目录，自动发现注册

```python
class MyIndicator(BaseSignalGenerator):
    name = "my_indicator"
    min_history = 100
    
    def generate(self, data: MarketData) -> List[Signal]:
        # 你的算法
        return [Signal(...)]
```

## 注意事项

- **NumPy 版本**: 建议使用 `numpy<2` 避免 pandas 兼容警告
- **缓存**: 数据默认缓存在 `./cache/`，24小时过期
- **实盘**: 需配置券商 API (目前支持模拟盘)
- **性能**: 缠论为 O(N²)，大数据集建议启用增量更新模式

## License

MIT
