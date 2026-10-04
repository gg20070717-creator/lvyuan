<template>
  <div class="welcome-page">
    <!-- 主内容 -->
    <div class="welcome-content">
      <!-- 品牌徽章 -->
      <div class="badge">
        <span class="badge-dot" />
        <span>以中国为课堂 · 以真实旅行为实践</span>
      </div>

      <!-- Logo 图标（官方 SVG 图形部分，viewBox 与官方一致） -->
      <div class="hero-logo">
        <img :src="brandLogo" alt="旅鸢飞鸟与书本图标" />
      </div>

      <!-- 标题区 -->
      <h1 class="hero-title">旅鸢</h1>
      <p class="hero-slogan">让专业生长，让旅途有温度</p>
      <p class="hero-desc">中国入境游旅行定制师多智能体协同实训平台</p>

      <!-- CTA 按钮 -->
      <div class="cta-row">
        <button class="cta-primary" @click="$router.push('/app/home')">
          开始探索
          <el-icon class="cta-icon"><ArrowRight /></el-icon>
        </button>
      </div>

      <!-- 新用户三步引导（T10：入口清晰，评审反馈 #5） -->
      <div class="onboard-guide">
        <div class="og-item">
          <span class="og-step">1</span>
          <div class="og-text">
            <b>告诉旅鸢你的情况</b>
            <span>职业背景、学习目标与能力基础，让旅鸢为你建立学情画像</span>
          </div>
        </div>
        <div class="og-item">
          <span class="og-step">2</span>
          <div class="og-text">
            <b>跟着旅鸢学</b>
            <span>老师先讲、确认你懂了、再出题，答错会换着法子重讲</span>
          </div>
        </div>
        <div class="og-item">
          <span class="og-step">3</span>
          <div class="og-text">
            <b>去训练场巩固</b>
            <span>知识练习与情景模拟相结合，把学习转化为旅行定制能力</span>
          </div>
        </div>
        <p class="og-tip">已学过？可在「个人中心 → 重置学习数据」清空后全新开始</p>
      </div>

      <!-- 数据统计栏 -->
      <div class="stats-bar">
        <div class="stats-inner">
          <div v-for="stat in stats" :key="stat.label" class="stat-item">
            <div class="stat-icon-box">
              <el-icon class="stat-icon"><component :is="stat.icon" /></el-icon>
            </div>
            <div v-if="stat.value" class="stat-value">{{ stat.value }}</div>
            <div class="stat-label">{{ stat.label }}</div>
          </div>
        </div>
      </div>

      <!-- 版权 -->
      <p class="copyright">© 2026 旅鸢 · 中国入境游旅行定制师多智能体协同实训平台</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import brandLogo from '@/assets/lvyuan-logo.jpg'
import { ArrowRight, User, OfficeBuilding, Reading, TrendCharts, CircleCheck } from '@element-plus/icons-vue'

const stats = [
  { icon: Reading,       value: '7',   label: '知识领域' },
  { icon: TrendCharts,   value: '3796', label: '技能点' },
  { icon: CircleCheck,   value: '30944', label: '考试题目' },
  { icon: User,          value: '14',  label: '多智能体' },
  { icon: OfficeBuilding, value: '6',  label: '六帽审查\n质量保障' },
]
</script>

<style lang="scss" scoped>
@use '@/styles/tokens' as *;

.welcome-page {
  height: 100vh;
  display: flex;
  flex-direction: column;
  position: relative;
  overflow: hidden;
  background: $color-bg;
}

// ── 背景装饰 ──
.bg-decoration {
  position: absolute;
  inset: 0;
  z-index: 0;
  pointer-events: none;
}

.compass-watermark {
  position: absolute;
  left: -100px;
  top: 50%;
  transform: translateY(-50%);
  width: 400px;
  height: 400px;
  opacity: 0.5;
}

.mountain-ink {
  position: absolute;
  right: 0;
  bottom: 0;
  width: 600px;
  height: 300px;
  opacity: 0.6;
}

// ─ 内容 ──
.welcome-content {
  position: relative;
  z-index: 1;
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 48px 24px 32px;
}

// ─ 品牌徽章 ──
.badge {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 8px 20px;
  border-radius: 999px;
  background: rgba(51, 143, 242, 0.08);
  border: 1px solid rgba(51, 143, 242, 0.2);
  margin-bottom: 24px;

  .badge-dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: $color-accent;
  }

  span {
    font-size: 13px;
    font-weight: 500;
    color: $color-accent;
  }
}

// ─ Logo 图标 ──
.hero-logo {
  width: 120px;
  height: 120px;
  margin-bottom: 24px;

  svg {
    width: 100%;
    height: 100%;
    filter: drop-shadow(0 4px 12px rgba(24, 58, 99, 0.15));
  }
}

// ── 标题区 ──
.hero-title {
  font-family: $font-serif;
  font-size: 48px;
  font-weight: 700;
  color: $color-primary;
  margin-bottom: 12px;
  text-align: center;
  letter-spacing: 6px;
}

.hero-slogan {
  font-family: $font-serif;
  font-size: 22px;
  font-weight: 500;
  color: $color-accent;
  margin-bottom: 12px;
  text-align: center;
}

.hero-desc {
  font-size: 15px;
  color: $color-text-secondary;
  margin-bottom: 32px;
  text-align: center;
}

// ── CTA ──
.cta-row {
  margin-bottom: 36px;
}

// ── 新用户三步引导（T10） ──
.onboard-guide {
  max-width: 560px;
  margin: 0 auto 36px;
  display: flex;
  flex-direction: column;
  gap: 14px;
  padding: 20px 24px;
  border-radius: $radius-lg;
  background: rgba(24, 58, 99, 0.04);
  border: 1px solid rgba(24, 58, 99, 0.1);

  .og-item {
    display: flex;
    align-items: flex-start;
    gap: 12px;
    text-align: left;
  }

  .og-step {
    flex-shrink: 0;
    width: 24px;
    height: 24px;
    border-radius: 50%;
    background: $color-primary;
    color: #fff;
    font-size: 13px;
    font-weight: 700;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    margin-top: 1px;
  }

  .og-text {
    display: flex;
    flex-direction: column;
    gap: 2px;

    b { font-size: 14px; color: $color-text; }
    span { font-size: 12.5px; color: $color-text-secondary; line-height: 1.5; }
  }

  .og-tip {
    margin-top: 4px;
    font-size: 12px;
    color: $color-accent;
    text-align: center;
  }
}

.cta-primary {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 14px 36px;
  border-radius: $radius-xl;
  border: none;
  font-size: 16px;
  font-weight: 600;
  color: #FFFFFF;
  background: $color-primary;
  box-shadow: 0 4px 16px rgba(24, 58, 99, 0.25);
  cursor: pointer;
  transition: all 0.2s;

  &:hover {
    transform: translateY(-2px);
    box-shadow: 0 6px 20px rgba(24, 58, 99, 0.35);
    background: $color-primary-light;
  }

  .cta-icon {
    font-size: 18px;
  }
}

// ── 数据统计 ──
.stats-bar {
  width: 100%;
  max-width: 900px;
  margin-bottom: 20px;
}

.stats-inner {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 16px;
  padding: 28px 24px;
  border-radius: $radius-xl;
  background: rgba(255, 255, 255, 0.7);
  backdrop-filter: blur(10px);
  border: 1px solid rgba(233, 229, 222, 0.8);
  box-shadow: 0 2px 12px rgba(24, 58, 99, 0.04);
}

.stat-item {
  text-align: center;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
}

.stat-icon-box {
  width: 44px;
  height: 44px;
  border-radius: $radius-md;
  background: rgba(51, 143, 242, 0.1);
  border: 1px solid rgba(51, 143, 242, 0.15);
  display: flex;
  align-items: center;
  justify-content: center;

  .stat-icon {
    font-size: 20px;
    color: $color-accent;
  }
}

.stat-value {
  font-family: $font-serif;
  font-size: 26px;
  font-weight: 700;
  color: $color-primary;
}

.stat-label {
  font-size: 13px;
  color: $color-text-secondary;
  white-space: pre-line;
  line-height: 1.5;
}

// ── 版权 ──
.copyright {
  font-size: 12px;
  color: rgba(111, 111, 111, 0.5);
  margin-top: auto;
  padding-top: 16px;
}

// ── 响应式 ──
@media (max-width: 768px) {
  .hero-title {
    font-size: 36px;
    letter-spacing: 4px;
  }

  .hero-slogan {
    font-size: 18px;
  }

  .hero-logo {
    width: 100px;
    height: 100px;
  }

  .stats-inner {
    grid-template-columns: repeat(3, 1fr);
    gap: 12px;
    padding: 20px 16px;
  }

  .compass-watermark {
    display: none;
  }

  .mountain-ink {
    width: 100%;
    opacity: 0.3;
  }
}

@media (max-width: 480px) {
  .welcome-content {
    padding: 32px 16px 24px;
  }

  .hero-title {
    font-size: 28px;
    letter-spacing: 3px;
  }

  .hero-slogan {
    font-size: 16px;
  }

  .hero-desc {
    font-size: 13px;
  }

  .stats-inner {
    grid-template-columns: repeat(2, 1fr);
  }
}

.hero-logo { width: 150px; height: 150px; margin-bottom: 18px; }
.hero-logo img { width: 100%; height: 100%; object-fit: contain; mix-blend-mode: multiply; }
.welcome-page { background: #f7fbff; }
.welcome-content { padding-top: 36px; }
.hero-title { color: #338ff2; font-size: 44px; font-weight: 600; margin-bottom: 14px; }
.hero-slogan { color: #2a5278; letter-spacing: 2px; font-size: 25px; }
.hero-desc { letter-spacing: 1px; font-size: 13px; }
.badge { background: #eef6ff; border-color: #d8e9fb; }
.onboard-guide { background: rgba(255,255,255,.85); border: 1px solid #dceaf7; border-radius: 22px 6px 22px 6px; gap: 16px; }
.stats-inner { background: rgba(255,255,255,.7); border: 1px solid #deebf8; border-radius: 22px 6px 22px 6px; box-shadow: none; }
.stat-icon-box { background: #eef6ff; border-color: #deebf8; }
.copyright { color: #8da2b6; }
</style>
