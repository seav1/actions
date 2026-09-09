#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os, sys, json, subprocess
from seleniumbase import SB

EMAIL       = os.environ.get("DISCORD_EMAIL") or os.environ.get("EMAIL") or ""
PASSWORD    = os.environ.get("DISCORD_PASSWORD") or os.environ.get("PASSWORD") or ""
REPO_PAT    = os.environ.get("REPO_PAT") or ""
PROXY       = os.environ.get("PROXY_SERVER") or "socks5://127.0.0.1:1080"
SECRET_NAME = "DISCORD_TOKEN"

if not EMAIL or not PASSWORD:
    print("❌ 未配置 DISCORD_EMAIL 或 DISCORD_PASSWORD")
    sys.exit(1)

def update_secret(token):
    print(f"🔄 更新 Secret: {SECRET_NAME}")
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
        print(f"✅ Secret {SECRET_NAME} 更新成功")
    else:
        print(f"❌ Secrets 更新失败: {proc.stderr.strip()}")

def main():
    with SB(uc=True, headless=True, proxy=PROXY) as sb:
        print("🌐 访问 Discord 登录页...")
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

        if token:
            print(f"✅ 成功获取 Token: {token[:4]}...{token[-4:]}")
            if REPO_PAT:
                update_secret(token)
            else:
                print("⚠️ 未配置 REPO_PAT，跳过 Secrets 写入")
        else:
            print(f"❌ 登录失败，API 返回: {res}")
            sb.save_screenshot("login_failed.png")

if __name__ == "__main__":
    main()
