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
    print("❌ 未配置 DISCORD_EMAIL 或 DISCORD_PASSWORD")
    sys.exit(1)

def update_secret(token):
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
            return

        print(f"✅ 初步获取 Token: {token[:4]}...{token[-4:]}")

        # ==========================================
        # 核心：创建纯净的 iframe 绕过 Discord 的 LocalStorage 屏蔽
        # ==========================================
        print("🔌 正在注入 Token 并进行 Gateway 握手激活 (模拟真实登录环境)...")
        
        inject_js = """
            let token = arguments[0];
            // 1. 创建一个隐藏的 iframe
            let iframe = document.createElement('iframe');
            document.body.appendChild(iframe);
            
            // 2. 利用 iframe 内部未被污染的 localStorage 写入 token (必须包裹双引号)
            iframe.contentWindow.localStorage.setItem('token', '"' + token + '"');
            
            // 3. 销毁 iframe，不留痕迹
            iframe.remove();
        """
        sb.execute_script(inject_js, token)
        
        print("🚀 访问应用主页，完成 WebSocket 激活...")
        sb.open("https://discord.com/app")
        sb.sleep(8) # 等待官方客户端完成初始化和指纹上报

        current_url = sb.get_current_url()
        if "login" in current_url:
            print("❌ Token 未能成功激活，被服务器风控踢回登录页。")
            return

        print("🎉 Token 已成功验证并激活！具备完整 OAuth2 授权能力。")

        if REPO_PAT:
            update_secret(token)
        else:
            print("⚠️ 未配置 REPO_PAT，跳过 Secrets 写入。")

if __name__ == "__main__":
    main()
