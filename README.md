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

## 10. 部署注意点

### 10.1 安全配置

- **必须更换 `JWT_SECRET`**：使用 `python -c "import secrets; print(secrets.token_hex(32))"` 生成随机密钥，切勿使用默认值
- **切勿将 `.env` 文件提交到 Git**：确保 `.gitignore` 中包含 `.env`
- **生产环境启用 HTTPS**：JWT Cookie 应设置 `secure=True`，需在 `server.py` 中修改 `set_cookie` 调用
- **GitHub OAuth App 回调地址**：生产环境需更新为实际域名（如 `https://yourdomain.com/auth/github/callback`）

### 10.2 数据持久化

- 当前为内存存储，**服务重启后数据丢失**
- 生产部署建议接入数据库（PostgreSQL / SQLite），替换 `users`、`todos`、`email_users` 字典
- 密码哈希使用 bcrypt，迁移数据库后可直接复用

### 10.3 部署方式

#### 直接运行

```bash
pip install -r requirements.txt
uvicorn server:app --host 0.0.0.0 --port 8000 --workers 4
```

> 注意：多 worker 模式下内存存储不共享，必须先接入外部数据库

#### Docker 部署

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8000
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000"]
```

```bash
docker build -t todo-app .
docker run -d -p 8000:8000 --env-file .env todo-app
```

### 10.4 反向代理（Nginx 示例）

```nginx
server {
    listen 443 ssl;
    server_name yourdomain.com;

    ssl_certificate     /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### 10.5 环境变量清单

| 变量 | 必填 | 说明 |
|------|------|------|
| `GITHUB_CLIENT_ID` | 是 | GitHub OAuth App Client ID |
| `GITHUB_CLIENT_SECRET` | 是 | GitHub OAuth App Client Secret |
| `JWT_SECRET` | 是 | JWT 签名密钥（生产环境必须自定义） |
| `BASE_URL` | 否 | 应用根 URL，默认 `http://localhost:8000` |

### 10.6 其他注意事项

- CORS：当前未启用，如果前后端分离部署需添加 `CORSMiddleware`
- 日志：建议生产环境配置 `uvicorn` 的 `--log-level info` 并接入日志收集
- 监控：可通过 FastAPI 内置 `/docs` 端点验证 API 状态（生产环境建议关闭）

## 11. 当前限制

当前数据存储为内存级（重启服务后数据会丢失），适用于本地开发和演示环境。
