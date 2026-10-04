"""
Brain of Cloud -- 交互式终端
管家通过 Tool Call 自主决定调用哪些 Agent，无固定流程
"""

from __future__ import annotations

import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from brain_of_cloud.domain.models import SubmissionResult, MasteryReport
from brain_of_cloud.llm.client import LLMClient
from brain_of_cloud.plugins import InboundGuidePlugin
from brain_of_cloud.services.orchestrator import Orchestrator
from brain_of_cloud.services.training import TrainingService
from brain_of_cloud.services.agents import ProfileAgent, TrainingAnalyzerAgent
from brain_of_cloud.storage.sqlite import SQLiteStore

SEP = "-" * 60
BANNER = "=" * 60


@dataclass
class LLMCall:
    agent: str
    tokens: int
    ms: float


class Stats:
    def __init__(self) -> None:
        self.calls: list[LLMCall] = []
        self.total_tokens = 0
        self.total_ms = 0.0
        self.submissions: list[SubmissionResult] = []
        self.mastery: MasteryReport | None = None

    def record(self, agent: str, tokens: int, ms: float) -> None:
        self.calls.append(LLMCall(agent, tokens, ms))
        self.total_tokens += tokens
        self.total_ms += ms


class InstrumentedLLMClient(LLMClient):
    def __init__(self, stats: Stats, *a: Any, **kw: Any) -> None:
        super().__init__(*a, **kw)
        self._stats = stats

    def chat(self, messages=None, **kw: Any) -> Any:
        system = kw.get("system", "")[:120]
        label = self._detect_label(system)
        print(f"    [{label}] ...", end="", flush=True)
        t0 = time.time()
        resp = super().chat(messages=messages, **kw)
        elapsed = (time.time() - t0) * 1000
        tk = resp.usage_tokens.get("total_tokens", 0) if resp.usage_tokens else 0
        print(f" ({tk}tk, {elapsed:.0f}ms)")
        self._stats.record(label, tk, elapsed)
        return resp

    def _detect_label(self, system: str) -> str:
        for kw, name in [
            ("白帽", "白帽"), ("黑帽", "黑帽"), ("绿帽", "绿帽"),
            ("黄帽", "黄帽"), ("红帽", "红帽"), ("蓝帽", "蓝帽"),
            ("知识检索", "知识检索"), ("证据排序", "知识检索"),
            ("培训材料生成", "文本生成"),
            ("学习管家", "管家"),
            ("个性画像", "个性画像"), ("学习者画像", "个性画像"),
            ("训练场分析", "训练分析"),
        ]:
            if kw in system:
                return name
        return "管家"


TOOL_NAMES = {
    "search_knowledge": "知识检索",
    "generate_material": "文本生成",
    "review_material": "五帽审查",
    "quiz_user": "训练场",
    "generate_report": "训练分析",
    "update_profile": "个性画像",
}


class App:
    def __init__(self) -> None:
        self.stats = Stats()
        self._llm = InstrumentedLLMClient(self.stats)
        self._store = SQLiteStore(Path(os.environ.get("BOC_DB_PATH", "brain_of_cloud.sqlite")))
        self._store.initialize()
        self._plugin = InboundGuidePlugin()
        self._orch = Orchestrator(store=self._store, plugin=self._plugin, llm_client=self._llm)
        self._training = TrainingService(self._plugin, store=self._store)
        self._profile = ProfileAgent(self._llm)
        self._analyzer = TrainingAnalyzerAgent(self._llm, self._training)
        self._user_id = "learner_1"
        self._quiz_id: str | None = None
        self._quiz_prompt: str | None = None

    def run(self) -> None:
        print(BANNER)
        print("  Brain of Cloud -- 入境游地陪导游训练系统")
        print("  deepseek-v4-flash-vision-exp | 工具驱动架构 | 无固定流程")
        print(BANNER)
        print()
        print("  [管家] 你好！我是你的学习管家，很高兴认识你。")
        print("  随便聊聊吧——可以介绍你自己，也可以直接问问题。")
        print()

        while True:
            try:
                raw = input("> ").strip()
            except (KeyboardInterrupt, EOFError):
                print("\n再见!")
                break
            if not raw:
                continue

            if raw == "/quit":
                print("再见!")
                break
            elif raw == "/quiz":
                self._cmd_quiz("")
            elif raw.startswith("/quiz "):
                self._cmd_quiz(raw[6:].strip())
            elif raw.startswith("/profile "):
                self._cmd_profile(raw[9:].strip())
            elif raw == "/profile":
                self._cmd_profile("")
            elif raw == "/report":
                self._cmd_report()
            elif raw == "/skip":
                if self._quiz_id:
                    print(f"  已跳过: {self._quiz_id}")
                    self._quiz_id = None
                    self._quiz_prompt = None
                else:
                    print("  当前无活跃题目。")
            elif raw.startswith("/"):
                print(f"  未知命令: {raw}")
            elif self._quiz_id is not None:
                self._cmd_answer(raw)
            else:
                self._cmd_chat(raw)

    def _cmd_chat(self, content: str) -> None:
        print(f"\n  [你] {content}")
        t0 = time.time()

        try:
            result = self._orch.handle_user_message(self._user_id, "session", content)
        except Exception as exc:
            print(f"  [错误] {exc}")
            return

        elapsed = (time.time() - t0) * 1000

        # Show which tools were called
        if result.tool_calls_made:
            tools_str = " -> ".join(TOOL_NAMES.get(t, t) for t in result.tool_calls_made)
            print(f"  [工具调用] {tools_str} ({elapsed:.0f}ms)")

        # Show generated content (if any)
        if result.generated_content:
            print(f"  [生成内容] ({len(result.generated_content)}字符):")
            print(f"  {SEP}")
            for line in result.generated_content[:1200].split("\n"):
                print(f"  {line[:100]}")
            if len(result.generated_content) > 1200:
                print(f"  ... (共{len(result.generated_content)}字符)")
            print(f"  {SEP}")
            if result.review_verdict:
                print(f"  [审查判定] {result.review_verdict}")

        # Show response
        print(f"\n  [管家] {result.response}")

        self._print_stats()

    def _cmd_profile(self, bg: str) -> None:
        if not bg:
            print("  用法: /profile <你的背景介绍>")
            return
        try:
            profile = self._profile.generate_profile(self._user_id, bg)
            self._store.save_learner_profile(profile)
            print(f"  [画像] 等级={profile.current_level}, 风格={profile.style_preferences}")
        except Exception as exc:
            print(f"  [错误] {exc}")
        self._print_stats()

    def _cmd_quiz(self, kp: str) -> None:
        try:
            kp_ids = [kp] if kp else []
            questions = (self._training.generate_quiz(kp_ids, "intro")
                         or self._training.generate_quiz(kp_ids, "basic")
                         or self._training.generate_quiz([], "intro"))
        except Exception as exc:
            print(f"  [错误] {exc}")
            return
        if not questions:
            print("  暂无题目。")
            return
        q = questions[0]
        self._quiz_id = q.question_id
        self._quiz_prompt = q.prompt
        print(f"  [训练场] {q.prompt}")
        print(f"  评分标准: {q.rubric}")
        print(f"  直接输入答案:")

    def _cmd_answer(self, answer: str) -> None:
        qid = self._quiz_id
        if not qid:
            return
        try:
            result = self._training.submit(self._user_id, qid, answer)
            report = self._training.get_mastery(self._user_id)
        except Exception as exc:
            print(f"  [错误] {exc}")
            self._quiz_id = None
            return

        self.stats.submissions.append(result)
        self.stats.mastery = report
        icon = "正确" if result.correct else "需改进"
        print(f"  [训练场] {icon}: {result.feedback}")
        kps = ", ".join(f"{k}={v:.0%}" for k, v in report.knowledge_point_scores.items())
        print(f"  [训练场] 掌握度: {kps}")
        if report.weak_points:
            print(f"  [训练场] 薄弱点: {', '.join(report.weak_points)}")
        self._quiz_id = None
        self._quiz_prompt = None

    def _cmd_report(self) -> None:
        try:
            report = self._analyzer.run(self._user_id)
        except Exception:
            try:
                report = self._training.get_mastery(self._user_id)
            except Exception as exc:
                print(f"  [错误] {exc}")
                return
        self.stats.mastery = report
        for kp, score in report.knowledge_point_scores.items():
            bar = "#" * int(score * 10) + "-" * (10 - int(score * 10))
            print(f"  {kp}: {bar} {score:.0%}")
        if report.weak_points:
            print(f"  薄弱: {', '.join(report.weak_points)}")
        print(f"  建议: {report.recommended_action[:200]}")
        self._print_stats()

    def _print_stats(self) -> None:
        print(SEP)
        print(f"  LLM: {len(self.stats.calls)}次 | {self.stats.total_tokens}tk | {self.stats.total_ms/1000:.1f}s")
        if self.stats.calls:
            for c in self.stats.calls[-3:]:
                print(f"  {c.agent}: {c.tokens}tk/{c.ms:.0f}ms")
        if self.stats.submissions:
            print(f"  答题: {len(self.stats.submissions)}次")
        print(SEP)


def main() -> None:
    App().run()


if __name__ == "__main__":
    main()
