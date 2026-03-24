# Todo App (FastAPI + JWT + OAuth2)

一个带认证能力的 Todo 应用，支持：

- GitHub OAuth2 登录
- 邮箱 + 密码登录（含邮箱格式校验）
- JWT 会话认证（HttpOnly Cookie）
- Todo 增删改查（含完成状态）
- 前端自动同步（每 30 秒拉取服务端最新数据）

## 1. 项目结构

- `index.html`：前端页面（登录、Todo 列表、自动同步）
- `server.py`：FastAPI 后端（认证、JWT、Todo API）
- `requirements.txt`：Python 依赖
- `.env.example`：环境变量模板

## 2. 环境准备

建议 Python 3.10+

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## 3. 配置环境变量

复制模板：

```powershell
copy .env.example .env
```

编辑 `.env`，至少配置：

- `GITHUB_CLIENT_ID`
- `GITHUB_CLIENT_SECRET`
- `JWT_SECRET`
- `BASE_URL`（默认 `http://localhost:8000`）

## 4. GitHub OAuth2 配置

在 GitHub Developer Settings 创建 OAuth App：

- Homepage URL: `http://localhost:8000`
- Authorization callback URL: `http://localhost:8000/auth/github/callback`

## 5. 启动服务

```powershell
python server.py
```

打开浏览器访问：

- `http://localhost:8000`

## 6. 登录方式说明

### 6.1 GitHub OAuth2

点击 `Continue with GitHub` 后跳转授权，授权成功后自动回到应用并登录。

### 6.2 邮箱 + 密码

在登录面板输入邮箱与密码：

- 邮箱必须匹配常见格式（如 `user@example.com`）
- 密码最少 6 位
- 首次使用该邮箱会自动注册
- 再次登录会校验密码

## 7. 自动同步说明

登录后前端会每 30 秒自动调用 `/api/todos` 同步数据。

- 新增 / 删除 / 完成状态变更会同步到服务端
- 页面下方会显示最近一次同步时间

## 8. 主要接口

- `POST /auth/email`：邮箱登录/注册
- `GET /auth/github`：GitHub OAuth2 发起登录
- `GET /auth/github/callback`：OAuth2 回调
- `POST /auth/logout`：退出登录
- `GET /api/me`：获取当前用户
- `GET /api/todos`：获取 Todo 列表
- `POST /api/todos`：新增 Todo
- `PATCH /api/todos/{todo_id}`：更新完成状态
- `DELETE /api/todos/{todo_id}`：删除 Todo

## 9. 常见问题

### 9.1 端口被占用

修改 `server.py` 末尾端口，或先关闭占用端口的进程。

### 9.2 GitHub 授权失败

请确认 OAuth App 的 callback URL 与 `.env` 中 `BASE_URL` 一致。

### 9.3 登录后立刻失效

请检查：

- `JWT_SECRET` 是否配置稳定
- 浏览器是否拦截 Cookie

## 10. 当前限制

当前数据存储为内存级（重启服务后数据会丢失），适用于本地开发和演示环境。
