# 01 · 登录鉴权 Auth

> 原型页面：page-login。基础简单但关键，所有受保护路由的入口。

## 1. 目标

实现登录页（账号密码）、JWT 管理、路由守卫、登录态持久化、自动刷新。

## 2. 接口（来自设计文档 7.3）

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /auth/login | 账号密码 → access_token(2h) + refresh_token(7d) |
| POST | /auth/refresh | refresh_token → 新 access_token |

## 3. 组件清单

| 组件 | 路径 | 职责 |
|------|------|------|
| LoginView | views/login/LoginView.vue | 登录页容器，BlankLayout 下，左品牌区 + 右表单卡 |
| LoginForm | views/login/components/LoginForm.vue | el-form 账号/密码 + 记住我 + 登录按钮；校验 + loading |

LoginView 布局：左侧蓝渐变品牌插画区（系统名 + 副标题），右侧白卡片登录表单（参考站 `#409eff` 主按钮）。响应式：窄屏只显示表单卡。

## 4. Store（stores/auth.ts）

```ts
state: { token, refreshToken, user: {id,name,avatar,roles} }  // localStorage 持久化
getters: { isAuthenticated }
actions: {
  login({username, password}) -> 调 api/login -> 存 token
  refresh()                    -> 调 api/refresh
  logout()                     -> 清空 + 跳 /login
  getUserInfo()                -> Mock 用户信息
}
```

## 5. Mock 数据

```jsonc
// POST /auth/login
{ "code":0, "data": { "access_token":"mock-access-xxx",
  "refresh_token":"mock-refresh-xxx", "expires_in":7200,
  "user": { "id":"u1","name":"系统管理员","avatar":"","roles":["admin"] } } }
// POST /auth/refresh
{ "code":0, "data": { "access_token":"mock-access-yyy","expires_in":7200 } }
```

## 6. 路由守卫（router/guard.ts）

- 白名单：`['/login']`。
- `beforeEach`：`!isAuthenticated && !白名单` → redirect `/login`；已登录访问 `/login` → redirect `/chat`。
- 登录成功后回跳 `redirect` query。

## 7. 实现步骤

1. LoginForm 表单 + 校验（非空/最小长度）。
2. authStore.login + 持久化。
3. guard 守卫。
4. 顶栏用户下拉：个人信息 / 退出登录（调 logout）。
5. token 即将过期（剩余 <5min）时静默 refresh（可在 request 拦截器内触发）。

## 8. 验收

- [ ] 账号 admin / 密码（任意）登录成功，跳 /chat。
- [ ] 刷新页面保持登录态。
- [ ] 退出登录 → 跳 /login，受保护页不可直访。
- [ ] 401 时自动刷新一次并重试。