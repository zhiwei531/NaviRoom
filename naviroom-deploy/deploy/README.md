# NaviRoom Deploy Runbook

这份文档是当前 `naviroom-deploy/deploy` 的全套部署说明，覆盖：

- 数据处理环境
- MySQL
- Recommendation API（FastAPI + systemd）
- 前端静态资源构建发布（可选）
- Nginx HTTPS 反向代理（可选）

---

## 1. 当前 Ansible 架构

`playbook.yml` 现在按顺序执行：

1. `common`：系统基础依赖（python3、venv、pip、git、rsync）
2. `mysql`：安装并配置 MySQL，创建数据库和应用账号
3. `app`：部署 `Data_processing` + `recommendation`，安装 Python 依赖，渲染 `.env`，可选启动 API service
4. `frontend`（可选）：构建前端并发布到 `/var/www/naviroom`
5. `nginx`（可选）：部署 HTTPS 站点配置，代理 `/api/` 到本机 API

---

## 2. 关键文件与作用

- `group_vars/all.yml`：所有部署变量（数据库、API、LLM、前端、域名证书）
- `playbook.yml`：主部署入口
- `seed_data.yml`：执行数据流水线并写入 MySQL
- `verify.yml`：部署后健康检查
- `roles/app/templates/naviroom-api.service.j2`：systemd 服务模板
- `roles/nginx/templates/naviroom.conf.j2`：Nginx 站点模板

---

## 3. 部署前准备（必做）

### 3.1 控制机（你本地）

在 `naviroom-deploy/deploy` 目录执行：

```bash
ansible-galaxy collection install -r collections/requirements.yml
ansible all -i hosts.ini -m ping
```

### 3.2 变量检查：`group_vars/all.yml`

至少确认这些变量：

- 数据库：
  - `naviroom_db_name`
  - `naviroom_db_user`
  - `naviroom_db_password`
- API：
  - `naviroom_enable_api_service: true`
  - `naviroom_api_module: recommendation.server:app`
- Recommendation：
  - `naviroom_reco_semantic_mode: lexical`（或 `llm`）
  - `naviroom_reco_requirements_mode: manual`（或 `llm`）
  - `naviroom_llm_api_key`（仅 llm 模式需要）

如果要部署前端和 nginx，再打开：

- `naviroom_enable_frontend_deploy: true`
- `naviroom_enable_nginx: true`
- `naviroom_domain` / `naviroom_domain_www`
- `naviroom_tls_cert_path` / `naviroom_tls_key_path`

### 3.3 前端源码目录与打包

- 默认从仓库根目录下的 **`NaviRoom Homepage Upload Interface Version2`** 拷贝并构建（含 **`/signin`** 登录与注册切换、`AuthContext`、localStorage 会话）。
- 变量 **`naviroom_frontend_bundle_name`** 可改目录名；必须与 **Ansible 控制机上的解压路径** 一致。
- 从主机打包传到 VM 时，**必须带上该文件夹**（与 `naviroom-deploy`、`recommendation` 同级），例如：

```bash
cd /path/to/NaviRoom
tar -czf naviroom-bundle.tar.gz naviroom-deploy recommendation "NaviRoom Homepage Upload Interface Version2"
```

说明：当前已接入后端账号系统和用户数据接口。Nginx 需要转发 **`/auth/`**、**`/data/`**、**`/recommend/`**、**`/api/`** 到 Recommendation/FastAPI 服务。

---

## 4. 标准部署流程（推荐按这个顺序）

### Step 1：基础环境 + API 服务部署

```bash
ansible-playbook -i hosts.ini playbook.yml
```

这一步会完成：

- MySQL 安装与建库建用户
- 上传 `Data_processing` 与 `recommendation`
- 创建 Python 虚拟环境并安装依赖
- 渲染 `/opt/naviroom/.env`
- 若开启 API 开关，启动 `naviroom-api` systemd 服务
- 若开启前端/Nginx 开关，构建前端并下发 Nginx 配置

### Step 2：写入业务数据

```bash
ansible-playbook -i hosts.ini seed_data.yml
```

会把：

- `dku` 数据写入 `dku_rooms`
- `kaggle` 数据写入 `kaggle_rooms` + `kaggle_reservations`

### Step 3：执行健康检查

```bash
ansible-playbook -i hosts.ini verify.yml
```

检查项：

- venv 和 `.env`
- MySQL 运行状态 + 目标数据库是否存在
- API service 状态（开启时）
- 前端首页是否发布（开启时）
- Nginx 服务状态（开启时）

---

## 5. 部署完成后的手动验收

在服务器上建议执行：

```bash
sudo systemctl status naviroom-api
curl http://127.0.0.1:8000/healthz
curl -X POST http://127.0.0.1:8000/recommend/dataset \
  -H "Content-Type: application/json" \
  -d '{"user_query":"study room with screen","requirements":{"capacity":4}}'
sudo mysql -e "USE navi_room_db; SHOW TABLES;"
```

如果启用了 Nginx，对外验证：

```bash
curl -I https://{{your-domain}}/
curl -I https://{{your-domain}}/api/healthz
```

---

## 6. 生产建议

1. **LLM key 管理**  
   `naviroom_llm_api_key` 建议改用 Ansible Vault，不要明文。

2. **API 进程权限**  
   目前 systemd 用 `root` 运行，可后续改为专用用户（例如 `naviroom`）。

3. **前端构建稳定性**  
   如远端构建慢，可改成本地 CI 构建后只上传 `dist`。

4. **证书续期**  
   如果使用自动签发证书（如 certbot），请统一更新 `naviroom_tls_*` 路径与续期脚本。

---

## 7. 常见问题

1. `ansible-playbook` 卡在 SSH  
   检查 `hosts.ini` 中 `ansible_user`、密钥和安全组入站规则。

2. API 服务启动失败  
   执行：`sudo journalctl -u naviroom-api -n 200 --no-pager`

3. `/api/` 返回 502  
   先本机测 `curl 127.0.0.1:8000/healthz`，再看 `nginx -t` 和错误日志。

4. 数据库没有业务表  
   通常是漏跑 `seed_data.yml` 或 pipeline 输入文件路径不正确。

