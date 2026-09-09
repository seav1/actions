#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import json
import subprocess
from seleniumbase import SB

# ================= 环境变量配置 =================
EMAIL       = os.environ.get("DISCORD_EMAIL") or os.environ.get("EMAIL") or ""
PASSWORD    = os.environ.get("DISCORD_PASSWORD") or os.environ.get("PASSWORD") or ""
REPO_PAT    = os.environ.get("REPO_PAT") or ""
PROXY       = os.environ.get("PROXY_SERVER") or "socks5://127.0.0.1:1080"
SECRET_NAME = "DISCORD_TOKEN"

if not EMAIL or not PASSWORD:
    print("❌ 未配置 DISCORD_EMAIL 或 DISCORD_PASSWORD，脚本终止。")
    sys.exit(1)

def update_secret(token):
    """使用 gh cli 将激活后的 Token 写入至 GitHub Secrets"""
    token = token.strip()
    print(f"🔄 正在更新 Secret: {SECRET_NAME}")
    env = os.environ.copy()
    
    if REPO_PAT:
        env["GH_TOKEN"] = REPO_PAT
        
    if PROXY:
        env["HTTP_PROXY"] = env["HTTPS_PROXY"] = env["ALL_PROXY"] = PROXY

    proc = subprocess.run(
        ["gh", "secret", "set", SECRET_NAME, "--body", token],
        capture_output=True, text=True, env=env
    )
    
    if proc.returncode == 0:
        print(f"✅ Secret {SECRET_NAME} 更新成功！")
    else:
        print(f"❌ Secret 更新失败: {proc.stderr.strip()}")

def main():
    print("#" * 40)
    print("  Discord API 登录与 Token 自动激活")
    print("#" * 40)

    # 启动 SeleniumBase (UC 模式过盾，无头模式运行)
    with SB(uc=True, headless=True, proxy=PROXY) as sb:
        print("🌐 访问 Discord 登录页（建立安全上下文）...")
        sb.uc_open_with_reconnect("https://discord.com/login", reconnect_time=4)
        sb.sleep(3)

        print("🔑 调用 API 获取 Token...")
        async_fetch = """
            const done = arguments[arguments.length - 1];
            fetch('https://discord.com/api/v9/auth/login', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ login: %s, password: %s })
            })
            .then(r => r.json())
            .then(data => done(data))
            .catch(err => done({ error: err.toString() }));
        """ % (json.dumps(EMAIL), json.dumps(PASSWORD))

        res = sb.execute_async_script(async_fetch)
        token = res.get("token")

        if not token:
            print(f"❌ 登录失败，API 返回: {res}")
            sb.save_screenshot("login_failed.png")
            return

        print(f"✅ 初步获取 Token: {token[:4]}...{token[-4:]}")

        # ==========================================
        # 核心：切回主文档并安全注入 Token，防止 iframe 报错
        # ==========================================
        print("🔌 正在注入 Token 并进行 Gateway 握手激活 (模拟真实登录环境)...")
        
        # 1. 强制切回主干页面（防止停留在 CAPTCHA 等 iframe 内导致报错）
        sb.driver.switch_to.default_content()
        
        # 2. 使用 arguments[0] 注入，完全规避单双引号转义问题，并自动包裹 JSON 格式
        sb.execute_script("window.localStorage.setItem('token', JSON.stringify(arguments[0]));", token)
        
        # 3. 访问应用主页，触发 Discord 官方 JS 进行 WebSocket (Gateway) 长链接握手
        print("🚀 访问应用主页，激活 Token...")
        sb.open("https://discord.com/app")
        sb.sleep(8) # 等待官方客户端完成初始化和指纹上报

        current_url = sb.get_current_url()
        if "login" in current_url:
            print("❌ Token 未能成功激活，可能需验证码或触发风险拦截。")
            sb.save_screenshot("token_rejected.png")
            return

        print("🎉 Token 已成功验证并激活！具备完整 OAuth2 授权能力。")

        # 写入 GitHub Secrets
        if REPO_PAT:
            update_secret(token)
        else:
            print("⚠️ 未配置 REPO_PAT，跳过 Secrets 写入。")

if __name__ == "__main__":
    main()
