#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import time
import subprocess
from seleniumbase import SB

# ================= 环境变量配置 =================
DISCORD_EMAIL    = os.environ.get("DISCORD_EMAIL") or os.environ.get("EMAIL") or ""
DISCORD_PASSWORD = os.environ.get("DISCORD_PASSWORD") or os.environ.get("PASSWORD") or ""
REPO_PAT         = os.environ.get("REPO_PAT") or ""              # GitHub Personal Access Token (PAT)
SECRET_NAME      = "DISCORD_TOKEN"                               # 写入 GitHub Secrets 的变量名

if not DISCORD_EMAIL or not DISCORD_PASSWORD:
    print("ℹ️ 未配置 DISCORD_EMAIL 或 DISCORD_PASSWORD，脚本终止。")
    sys.exit(1)


def update_github_secret(secret_name, new_value, proxy_server=""):
    """使用 gh cli 将提取出的 Token 写入/更新至 GitHub Secrets"""
    if not new_value:
        print(f"⚠️ 跳过更新 {secret_name}：Token 为空")
        return False
        
    masked = new_value[:4] + "..." + new_value[-4:] if len(new_value) > 8 else "***"
    print(f"🔄 正在更新 Secret: {secret_name} (新值: {masked})")
    
    try:
        env = os.environ.copy()
        if REPO_PAT:
            env["GH_TOKEN"] = REPO_PAT
        
        if proxy_server:
            env["HTTP_PROXY"] = proxy_server
            env["HTTPS_PROXY"] = proxy_server
            env["ALL_PROXY"] = proxy_server

        proc = subprocess.run(
            ["gh", "secret", "set", secret_name, "--body", new_value],
            capture_output=True, text=True, timeout=30, check=False,
            env=env
        )
        if proc.returncode == 0:
            print(f"✅ Secret {secret_name} 更新成功！")
            return True
        else:
            print(f"❌ Secret 更新失败: {proc.stderr.strip()}")
            return False
    except Exception as e:
        print(f"❌ 更新 Secret 时发生异常: {e}")
        return False


def extract_discord_token(sb) -> str:
    """登录成功后，从浏览器 Webpack 模块或 localStorage 提权获取 Token"""
    print("🔎 正在提取 Discord Token...")
    
    # 方式 1: 通过 Discord Webpack 模块读取
    webpack_script = """
        try {
            return (window.webpackChunkdiscord_app.push([
                [Symbol()],
                {},
                e => {
                    for (let m of Object.keys(e.c).map(x => e.c[x].exports)) {
                        if (m?.default?.getToken) return m.default.getToken();
                    }
                }
            ]) || null);
        } catch (e) {
            return null;
        }
    """
    token = sb.execute_script(webpack_script)
    if token:
        return token

    # 方式 2: 通过 iframe 获取 localStorage 中的 token
    iframe_script = """
        try {
            let iframe = document.createElement('iframe');
            document.body.appendChild(iframe);
            let token = iframe.contentWindow.localStorage.getItem('token');
            return token ? JSON.parse(token) : null;
        } catch (e) {
            return null;
        }
    """
    token = sb.execute_script(iframe_script)
    return token or ""


def main():
    print("#" * 40)
    print("  Discord 账号密码登录与 Token 写入 Secrets")
    print("#" * 40)

    IS_PROXY     = os.environ.get("IS_PROXY", "true").lower() == "true"
    PROXY_SERVER = os.environ.get("PROXY_SERVER", "").strip() or "socks5://127.0.0.1:1080"
    HEADLESS     = os.environ.get("HEADLESS", "true").lower() == "true" 

    sb_kwargs = {"uc": True, "headless": HEADLESS}
    if IS_PROXY:
        print(f"🔗 挂载 SOCKS5 代理: {PROXY_SERVER}")
        sb_kwargs["proxy"] = PROXY_SERVER

    with SB(**sb_kwargs) as sb:
        print("🌐 访问 Discord 官方登录页...")
        sb.uc_open_with_reconnect("https://discord.com/login", reconnect_time=4)
        sb.wait_for_ready_state_complete()
        time.sleep(2)

        print("📝 输入账号密码...")
        try:
            sb.type('input[name="email"]', DISCORD_EMAIL)
            sb.type('input[name="password"]', DISCORD_PASSWORD)
            time.sleep(1)
            
            print("🚀 点击登录按钮...")
            sb.click('button[type="submit"]')
        except Exception as e:
            print(f"❌ 填充输入框或点击按钮失败: {e}")
            sb.save_screenshot("login_fill_error.png")
            return

        print("⏳ 等待页面跳转与验证...")
        login_success = False
        for i in range(40):
            time.sleep(1)
            current_url = sb.get_current_url()
            
            if "discord.com/channels" in current_url or "discord.com/app" in current_url:
                login_success = True
                print(f"🎉 登录成功！当前 URL: {current_url}")
                break
                
            if i % 5 == 0:
                try:
                    sb.uc_gui_click_captcha()
                except Exception:
                    pass

        if not login_success:
            print(f"❌ 登录超时或遇到拦截，当前页面: {sb.get_current_url()}")
            sb.save_screenshot("discord_login_timeout.png")
            return

        time.sleep(2)
        extracted_token = extract_discord_token(sb)
        
        if extracted_token:
            masked = extracted_token[:4] + "..." + extracted_token[-4:]
            print(f"✅ 成功获取 Token: {masked}")
            
            if REPO_PAT:
                update_github_secret(SECRET_NAME, extracted_token, PROXY_SERVER if IS_PROXY else "")
            else:
                print("⚠️ 未配置 REPO_PAT，跳过更新至 GitHub Secrets。")
        else:
            print("❌ 未能在已登录页面中提取到 Discord Token。")


if __name__ == "__main__":
    main()
