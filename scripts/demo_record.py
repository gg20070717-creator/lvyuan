#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""司南礼客 · 演示视频全自动录屏脚本（Playwright）

用途：比赛演示视频自动走流程。把浏览器画面录下来即可（也可 --video 让 Playwright 直接产出 webm）。

前置：
  1) 启动 start-dev（后端 http://127.0.0.1:8000，前端 http://127.0.0.1:5173）
  2) python -m pip install playwright && python -m playwright install chromium
用法：
  python scripts/demo_record.py                                   # 有头窗口 + 人工录屏
  python scripts/demo_record.py --video D:/demo_video             # 自动产出 video.webm（无音频）
  python scripts/demo_record.py --base http://127.0.0.1:5173 --headless --max-scenes 5   # 校验/试跑
"""
import argparse
import asyncio
import json
import sys
import time

from playwright.async_api import async_playwright

DEFAULT_BASE = "http://127.0.0.1:5173"
PROFILE_LABEL = "在职导游 · 回岗转入境"
SHOT_DIR = None  # 运行时设置

# 演示主角：老导游回岗 → 入境定制（最贴比赛叙事）
GREETING = "Good morning! Welcome to Shanghai. I am your local guide for this custom trip."
GREETING2 = "Could you tell me a bit more about the water town we are visiting today?"


async def pause(page, sec=2.2):
    await page.wait_for_timeout(sec * 1000)


async def shot(page, name):
    try:
        if SHOT_DIR:
            await page.screenshot(path=f"{SHOT_DIR}/{name}.png", full_page=False)
    except Exception as e:  # noqa: BLE001
        print("  [shot fail]", name, e)


async def goto(page, path, wait=2500):
    await page.goto(f"{page.url.split('#')[0]}#{path}", wait_until="networkidle", timeout=60000)
    await page.wait_for_timeout(wait)
    await pause(page, 1.0)


async def click_text(page, text, timeout=12000):
    await page.get_by_text(text, exact=False).first.click(timeout=timeout)


def _banner(step, title):
    print(f"\n===== {step}. {title} =====", flush=True)


async def scene_reset(base):
    """清空本地账户，回到干净的账户1（可先补拍‘欢迎页’）"""
    page = await new_page_ctx()
    await page.goto(base, wait_until="domcontentloaded")
    await page.evaluate("localStorage.clear()")
    await page.goto(f"{base}#/app/home", wait_until="networkidle", timeout=60000)
    await pause(page, 2.5)
    _banner(0, "欢迎页/新首页")
    await shot(page, "00_home")
    return page


async def scene_hero(page):
    """用测试画像新建主角账户（省去逐题向导，但保留‘从0开始’入口可另拍）"""
    await page.wait_for_selector(".acm-user", timeout=30000)
    await page.click(".acm-user", timeout=12000)
    await pause(page, 0.5)
    await click_text(page, "新建用户")
    await pause(page, 0.6)
    await click_text(page, PROFILE_LABEL)
    await page.wait_for_timeout(1200)
    # 等待 reload 完成、账户名出现
    await page.wait_for_selector(f"text=测试·{PROFILE_LABEL}", timeout=20000)
    await pause(page, 1.2)
    _banner(1, "新建用户 · 选择测试画像")
    await shot(page, "01_profile_created")


async def scene_profile(page):
    await goto(page, "/app/profile", 2600)
    _banner(2, "学情中心 · 画像/盲区/记忆")
    await pause(page, 1.5)
    await shot(page, "02_profile")


async def scene_path(page):
    await goto(page, "/app/path", 2600)
    _banner(3, "学习路线规划")
    await pause(page, 1.5)
    await shot(page, "03_path")


async def scene_tree(page):
    await goto(page, "/app/knowledge-tree", 2600)
    _banner(4, "知识技能树（7 大领域）")
    await pause(page, 1.5)
    await shot(page, "04_tree")


async def scene_knowledge(page):
    await goto(page, "/app/knowledge", 2600)
    _banner(5, "定制学习资源 · 课本/技能点")
    await pause(page, 1.5)
    await shot(page, "05_knowledge")


async def scene_toolbox(page):
    await goto(page, "/app/toolbox", 2600)
    _banner(6, "工具箱（8 件套）")
    await pause(page, 1.5)
    await shot(page, "06_toolbox")


async def scene_sandbox(page):
    """入境定制游全流程 · 实时语音沙盒；语音链不稳时自动回退到情景模拟文字沙盒"""
    await goto(page, "/app/training", 4000)
    _banner(7, "训练场 · 入境定制游全流程（实时语音）")
    await page.wait_for_selector(".train-tab", timeout=30000)
    # 确保选中第一个 tab（入境定制游全流程实战）
    await page.locator(".train-tab").first.click(timeout=10000)
    await page.wait_for_selector(".scene-card:visible", timeout=40000)
    await pause(page, 1.0)
    # 选第一张可见卡（未锁定的「行前第1课 · 需求挖掘访谈」等），锁定大卡点开无效
    card = page.locator(".scene-card:visible").first
    await card.click(timeout=12000)
    await pause(page, 1.2)
    # 尝试语言弹窗 → 开始语音实战
    started = False
    try:
        lm = page.locator(".lm-mask:visible")
        if await lm.count():
            await page.get_by_text("开始语音实战").first.click(timeout=10000)
            started = True
    except Exception:  # noqa: BLE001
        pass
    if started:
        try:
            await page.wait_for_selector(".rvc-input", timeout=30000)
            await shot(page, "07_sandbox_ready")
            try:
                await page.get_by_text("接通游客语音").first.click(timeout=8000)
                await pause(page, 0.6)
                try:
                    await page.get_by_text("确认我已佩戴").first.click(timeout=5000)
                except Exception:  # noqa: BLE001
                    pass
                await page.wait_for_selector(".rvc-btn.stop", timeout=45000)
                await pause(page, 1.0)
                await page.fill(".rvc-input", GREETING)
                await page.click(".rvc-send")
                await page.wait_for_timeout(8000)
                await shot(page, "07_sandbox_voice_reply")
            except Exception as e:  # noqa: BLE001
                print("  [voice detail skip]", e)
        except Exception:  # noqa: BLE001
            print("  [voice session not ready -> fallback scenario]")
    else:
        print("  [no language modal -> fallback scenario]")
    # 回退/补充：情景模拟文字沙盒（保证能展示对话与游客回应）
    try:
        back = page.get_by_text("返回", exact=True)
        if await back.count():
            await back.first.click(timeout=5000)
            await pause(page, 0.8)
        tab = page.get_by_text("情景模拟训练", exact=False)
        if await tab.count():
            await tab.first.click(timeout=8000)
            await pause(page, 0.8)
        await page.wait_for_selector(".scene-card", timeout=30000)
        scen = page.locator(".scene-card", has_text="机场接机 · 突发延误")
        if await scen.count():
            await scen.first.click(timeout=10000)
        else:
            await page.locator(".scene-card").first.click(timeout=10000)
        await pause(page, 1.5)
        ta = page.locator("textarea[placeholder*='以导游身份']")
        await ta.wait_for(timeout=60000)
        await shot(page, "07_scenario_ready")
        await ta.fill("您好，欢迎来到中国！我是本次接机导游。航班延误让大家久等，我先同步最新安排并尽快协助大家。")
        await ta.press("Enter")
        await page.wait_for_timeout(10000)
        await shot(page, "07_scenario_reply")
    except Exception as e:  # noqa: BLE001
        print("  [scenario fallback skip]", e)

async def scene_home(page):
    """回到首页收尾定格（学情已就绪，主页展示个性化看板）"""
    await goto(page, "/app/home", 3000)
    _banner(8, "回到首页 · 个性化学情看板")
    await pause(page, 2.0)
    await shot(page, "08_home")

async def new_page_ctx(pw, base, video_dir=None, headless=True, slow_mo=120):
    browser = await pw.chromium.launch(headless=headless, slow_mo=slow_mo, args=["--mute-audio"])
    ctx = await browser.new_context(
        viewport={"width": 1600, "height": 900},
        record_video_dir=video_dir,
        record_video_size={"width": 1600, "height": 900},
    )
    page = await ctx.new_page()
    return ctx, page, browser


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default=DEFAULT_BASE)
    ap.add_argument("--headless", action="store_true")
    ap.add_argument("--video", default=None, help="输出目录（Playwright 自动产出 video.webm）")
    ap.add_argument("--shots", default="omni_realtime_poc/_demo_shots", help="截图目录")
    ap.add_argument("--max-scenes", type=int, default=99)
    args = ap.parse_args()

    global SHOT_DIR
    SHOT_DIR = args.shots
    import os
    os.makedirs(SHOT_DIR, exist_ok=True)

    async with async_playwright() as pw:
        ctx, page, _browser = await new_page_ctx(pw, args.base, video_dir=args.video,
                                                  headless=args.headless, slow_mo=0 if args.headless else 120)
        try:
            await page.goto(args.base, wait_until="domcontentloaded", timeout=60000)
            await page.evaluate("localStorage.clear()")
            await page.goto(args.base + "#/app/home", wait_until="networkidle", timeout=60000)
            await page.wait_for_selector(".acm-user", timeout=30000)
            await pause(page, 2.0)
            await shot(page, "00_home")
            scenes = [
                (scene_hero, "新建用户·测试画像"),
                (scene_profile, "学情中心"),
                (scene_path, "学习路线"),
                (scene_tree, "知识技能树"),
                (scene_knowledge, "定制学习资源"),
                (scene_toolbox, "工具箱"),
                (scene_sandbox, "入境全流程·语音沙盒"),
                (scene_home, "回首页"),
            ]
            for idx, (fn, label) in enumerate(scenes, 1):
                if idx > args.max_scenes:
                    break
                print(f"[{idx}/{len(scenes)}] {label}", flush=True)
                try:
                    await fn(page)
                except Exception as e:  # noqa: BLE001
                    print("  !! scene error:", type(e).__name__, str(e)[:200], flush=True)
                    await shot(page, f"ERR_{idx}")
            await pause(page, 2.0)
        finally:
            await ctx.close()
            await _browser.close()
    print("\n演示自动走场完成。截图在", SHOT_DIR, ("；视频目录 " + args.video) if args.video else "")


if __name__ == "__main__":
    asyncio.run(main())