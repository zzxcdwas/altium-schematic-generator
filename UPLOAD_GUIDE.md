# 上传到 GitHub 操作手册（附界面中英文对照）

这份文档写给要亲手把本仓库传到 GitHub 的人。每一步都标注了 GitHub 网页上的**英文原文**，即使界面暂时是英文也能照着做。

---

## 第 0 步：先把 GitHub 界面改成中文（可选，推荐）

GitHub 官方原生支持简体中文，不需要装任何汉化插件。

1. 登录 GitHub，点右上角的**头像**
2. 下拉菜单里点 **Settings**（设置）
3. 左侧菜单最底部点 **Appearance**（外观）
4. 找到 **Language preferences**（语言偏好），下拉选 **简体中文 / Simplified Chinese**
5. 页面拉到最下面，点绿色 **Save**（保存）
6. 刷新页面即可

> 注意：这个设置只改 GitHub **自己的界面文字**。仓库里的 README、代码注释、Issue 内容仍然是原语言。

如果按上面改完还是英文，检查浏览器的首选语言顺序：
- Chrome：`设置 → 语言 → 添加"中文(简体)"` 并拖到最上面
- Edge：`设置 → 语言 → 添加中文 → 设为首选`

---

## 第 1 步：在 GitHub 上创建空仓库

1. 打开 https://github.com/new （或点击右上角 `+` → **New repository**）
2. **Repository name**（仓库名）填：`altium-schematic-generator`
3. **Description**（描述）可不填，也可写：`Generate native Altium Designer .SchDoc schematics from Python`
4. 选择 **Public**（公开）— 这样才能被搜到、也能加 MIT 许可起作用
5. **关键：以下三项全部不要勾选**
   - ❌ Add a README file
   - ❌ Add .gitignore
   - ❌ Choose a license

   因为本地仓库里已经有这些文件了，勾选会导致冲突、推送被拒绝。

6. 点 **Create repository**（创建仓库）

如果提示「名字已存在」，说明之前已经建过同名仓库，直接用它即可。

---

## 第 2 步：上传（二选一）

### 方式 A：命令行推送（推荐 — 保留提交历史）

在仓库目录下打开 Git Bash 或终端，依次执行（把 `zzxcdwas` 换成你的 GitHub 用户名）：

```bash
cd "C:/Users/ASUS/WorkBuddy/2026-09-17-14-45-12/altium-schematic-generator"

# 只在第一次需要：绑定远端并设置主分支名
git remote add origin https://github.com/zzxcdwas/altium-schematic-generator.git
git branch -M main

# 推送
git push -u origin main
```

首次推送会弹登录窗口，选 **Browser / Sign in with your browser**（用浏览器登录）跟着走完授权即可。

> 推送前如果想改提交署名（默认是我测试时占位的 `contributor@example.com`）：
> ```bash
> git config user.name  "你的用户名"
> git config user.email "你的邮箱"
> git commit --amend --reset-author --no-edit
> ```

### 方式 B：网页直接上传文件（不用命令行，一定能成功）

如果方式 A 因网络问题推不上去，用这个：

1. 打开刚创建的仓库页面（现在应该是空仓库，中间会提示一堆 Quick setup 文字）
2. 点蓝色按钮 **creating a new file**，或者把文件直接**拖进**这个页面
3. 拖拽的话：选中仓库根目录下所有文件（**含隐藏文件** `.gitignore`）一起拖进去
   - 更简单的方式：**不要**拖全部散文件，而是把整个 `altium-schematic-generator` 文件夹拖上去
   - **不需要**拖 `.git` 目录和 `out/` 目录
4. 页面底部 **Commit changes**（提交更改）区域：
   - 上面一行填标题：`Add Python toolkit for generating native Altium .SchDoc schematics`
   - 下一行填描述：`Verfied on Altium Designer 16`
5. 点绿色 **Commit changes** 按钮

拖拽上传单文件上限 25 MB，一次最多 100 个文件。本仓库 27 个文件、不到 300 KB，一次拖完没问题。

Windows 上显示隐藏文件（为了看到 `.gitignore`）：资源管理器 → `查看` → 勾选 `隐藏的项目`。

### 方式 C：GitHub Desktop（最省事）

1. 打开 GitHub Desktop → `File` → `Add local repository`（添加本地仓库）
2. 路径选 `C:\Users\ASUS\WorkBuddy\2026-09-17-14-45-12\altium-schematic-generator`
3. 右上角点 `Publish repository`（发布仓库）
4. Name 填 `altium-schematic-generator`，**取消**勾选 `Keep this code private`，点 `Publish repository`

---

## 第 3 步：上传完检查

在仓库主页确认这几项：

| 检查项 | 预期结果 |
|---|---|
| 文件数量 | 28 个（含 `UPLOAD_GUIDE.md`），`out/` **不应**出现 |
| `README.md` | 应在首页自动渲染展示出来 |
| 右下角 `License` | 应显示 `MIT` |
| `src/` `docs/` `examples/` `tools/` | 四个目录都在 |
| 中文文件名/内容 | 显示正常，没有乱码 |

---

## ⚠️ 安全提醒：请吊销一次凭据

在我尝试自动推送的过程中，**你的 GitHub 令牌曾短暂出现在一次命令输出里**。虽然仅在本地会话、未外泄，但出于安全习惯建议吊销它：

1. 打开 https://github.com/settings/applications （Applications 标签页下的 **Authorized OAuth Apps**）
2. 找到 **Git Credential Manager** → 点 **Revoke**（撤销）

或者打开 https://github.com/settings/tokens 检查 Tokens 标签，把不认识/不再需要的 `Revoke all`。

吊销**不影响**你已上传的仓库，只影响本机的命令行免密登录。以后再用 `git push`，重新登录一次即可。

---

## 附：本仓库包含什么

```
altium-schematic-generator/
├── README.md              # 首页说明
├── SKILL.md               # 作为 AI Agent Skill 使用时的入口
├── LICENSE                # MIT
├── UPLOAD_GUIDE.md        # 本文
├── requirements.txt
├── src/                   # 核心代码（12 个模块，零第三方依赖）
│   ├── config.py              # 库路径配置（支持环境变量 + 自动探测）
│   ├── cfb_reader.py          # OLE2 复合文档读取
│   ├── cfb_writer.py          # OLE2 复合文档写入
│   ├── sch_gen.py             # SchDoc 记录发射器
│   ├── schlib.py              # .SchLib / .IntLib 符号解析
│   ├── sch_build.py           # 网表驱动的图纸构建器
│   ├── sch_pack.py            # 打包写出
│   ├── erc.py                 # 电气规则检查
│   ├── audit.py               # 几何审计
│   ├── verify_pins.py         # 第三方交叉校验：引脚贴合
│   ├── verify_nets.py         # 第三方交叉校验：网表复算
│   └── verify_hierarchy.py    # 第三方交叉校验：层次化
├── docs/                  # 逆向出来的格式规范（最有价值的部分）
├── examples/              # 4 个可运行示例
└── tools/                 # 库探测 / 工程生成 / 辅助脚本
```
