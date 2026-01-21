# 📈 A股高股息现金流看板
> 专为「分红型投资者」打造的被动收入工具 —— 筛选高股息、稳分红的A股标的，构建可持续的现金流资产组合

[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://你的应用链接.streamlit.app)
[![GitHub Stars](https://img.shields.io/github/stars/KayaCCode/dividend?style=social)](https://github.com/KayaCCode/dividend)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

## 🎯 核心定位
帮助想用分红来获取被动现金流的用户，实现：
- ✅ 摆脱「靠股价涨跌赚钱」的焦虑，专注「分红现金流」
- ✅ 筛选**连续分红、高股息率、低波动**的蓝筹标的
- ✅ 实时监控自选股的股息率、分红稳定性
- ✅ 构建「躺赚」的被动收入资产组合

这个工具 用数据化方式筛选高股息标的，让分红现金流看得见、摸得着。

## 🌟 核心功能
### 1. 高股息标的精准筛选
- 📊 全市场高股息率TOP20自动排序（按股息率降序）
- 💎 千亿市值蓝筹股筛选（排除小市值高波动标的）
- 🎛️ 自定义市值门槛（0-5000亿可调），适配不同风险偏好

### 2. 现金流核心指标监控
- 📈 实时展示「股息率、总市值、最新价」核心数据
- 📋 股息率中位数/平均值统计（掌握市场整体分红水平）
- 🏆 最高股息率标的高亮（快速锁定现金流王者）

### 3. 自选股现金流管理
- ⭐ 自选股持久化保存（刷新/重启不丢失）
- 📌 自选股股息率每日更新（聚焦每个人的个性化持仓）

## 💻 本地部署
### 1. 克隆仓库
```bash
git clone https://github.com/你的用户名/你的仓库名.git
cd 你的仓库名
```
### 2. 安装依赖
运行
```bash
# 方法1：用pipreqs生成的精简依赖
pip install -r requirements.txt

# 方法2：手动安装核心依赖
pip install streamlit pandas akshare requests
```
### 3. 启动应用
运行
```bash
# 第一步：更新最新股票数据
python dividend_crawler.py

# 第二步：启动看板
streamlit run app.py
```
### 4. 访问本地服务

打开浏览器，输入：http://localhost:8501

## 📊 适用场景
- 退休投资者：筛选高股息标的，靠分红覆盖日常开支
- 定投投资者：聚焦分红稳的标的，定投 + 分红复利增长
- 低风险投资者：避开题材股，专注「现金奶牛」型企业
- 组合配置者：用高股息标的平衡组合风险，提升现金流稳定性
## 📝 数据说明
- 数据更新：每日自动抓取最新股价 / 股息率数据
- 数据来源：AKShare（开源金融数据接口）
- 风险提示：本工具仅作筛选参考，不构成投资建议，投资有风险，入市需谨慎
## 🤝 贡献指南
如果你有优化建议（比如新增「分红连续年数」「分红率」等指标），欢迎：
- Fork 本仓库
- 创建特性分支 (git checkout -b feature/AmazingFeature)
- 提交修改 (git commit -m 'Add some AmazingFeature')
- 推送到分支 (git push origin feature/AmazingFeature)
- 打开 Pull Request
## 📄 许可证
本项目基于 MIT 许可证开源 —— 你可以自由修改、分发，用于个人 / 商业用途（需保留原作者信息）
## 💬 交流与反馈
🎯 问题反馈：直接在 GitHub Issues 中提交


```
🌟 「投资的本质是认知的变现，而现金流是认知的落地」
愿这个工具帮你构建属于自己的「被动收入现金流组合」🚀
```

## ✅ TODO

* [ ] 完成在线部署（无需下载、打开浏览器即可使用）
* [ ] 页面 UI 进一步美化与信息密度优化
