# NewAPI 批量建号脚本

通过 NewAPI 后台管理接口：创建用户（`opc-2026-03-20-XXX`）、按人民币设置额度（×73529）、为该用户创建不限额 API Key，并输出用户名、API_KEY、额度。**编号由查询用户列表自动确定，只需输入金额。**

## 约定

- 用户名：`opc-2026-03-20-<编号>`，编号从 000 起自动递增（由用户列表接口判断下一个可用编号）。
- 统一密码：`sxwl66620260320!`
- 额度 = 人民币金额 × 73529（脚本内取整）。
- API Key 不设限额（`unlimited_quota: true`）。

## 环境变量

| 变量 | 必填 | 说明 |
|------|------|------|
| `NEWAPI_BASE_URL` | 是 | NewAPI 根地址，如 `https://apifox.newapi.ai` 或 `http://localhost:3000`（不含末尾 `/`） |
| `NEWAPI_ADMIN_USERNAME` | 与 PASSWORD 一起 | 管理员用户名（脚本先登录取 Session） |
| `NEWAPI_ADMIN_PASSWORD` | 与 USERNAME 一起 | 管理员密码 |
| `NEWAPI_DEBUG` | 否 | 设为非空（如 `1`）时，在 stderr 打印创建 Token 的原始 API 响应，便于确认是否返回明文 `data.key` |

管理员鉴权：提供 `NEWAPI_ADMIN_USERNAME` + `NEWAPI_ADMIN_PASSWORD`，脚本通过登录接口获取 Cookie，并用 Session 调用管理接口。

## 安装

```bash
cd scripts/newapi_batch_accounts
pip install -r requirements.txt
```

## 使用

金额**必须**通过命令行参数 `--amount` 传入，不通过环境变量。

```bash
# 使用环境变量配置 NewAPI 与管理员鉴权
export NEWAPI_BASE_URL=https://your-newapi.example.com
export NEWAPI_ADMIN_USERNAME=admin
export NEWAPI_ADMIN_PASSWORD=your-password
python create_account.py --amount 10

# 或全部用命令行参数
python create_account.py --base-url https://your-newapi.example.com --admin-username admin --admin-password your-password --amount 10
```

成功时输出示例：

```
用户名: opc-2026-03-20-003
API_KEY: sk-xxxxxxxx
额度: 735290
```

## 前提与注意

- 需要**管理员权限**（用于创建用户、设置额度）。
- 新用户若启用 2FA 或遭禁用，登录会失败，请在后台关闭 2FA 或启用该用户后再跑脚本（或使用默认未启用 2FA 的 NewAPI 配置）。
