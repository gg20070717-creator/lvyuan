<template>
  <div class="home-page">
    <!-- 历史对话面板（仪表盘与对话页共用，fixed 定位） -->
    <div v-if="historyOpen" class="history-mask" @click="historyOpen = false"></div>
    <div v-if="historyOpen" class="history-panel" @click.stop>
      <div class="hist-head">
        <span>历史对话（点击切换）</span>
        <button class="hist-close" @click="historyOpen = false"><SIcon name="x" :size="11" /></button>
      </div>
      <div class="hist-body">
        <div v-if="historyList.length === 0" class="hist-empty">还没有历史对话，先和旅鸢聊起来吧</div>
        <button v-for="s in historyList" :key="s.session_id"
          class="hist-item" :class="{ active: s.session_id === store.sessionId }"
          @click="switchSession(s)">
          <span class="hist-t">{{ s.title }}</span>
          <span class="hist-meta">{{ s.message_count }} 条 · {{ formatSessionTime(s.updated_at) }}</span>
        </button>
      </div>
      <div class="hist-foot">
        <button class="hist-new" @click="handleNewSession"><SIcon name="plus" :size="11" /> 新建对话</button>
      </div>
    </div>
    <!-- ══════════════ 仪表盘（无消息） ══════════════ -->
    <div v-if="!inChat" class="dash-scroll">
      <div class="home-content">
        <div class="lvyuan-page-intro">
          <div class="intro-copy"><span class="intro-eyebrow"><span class="guofeng-seal" aria-hidden="true">游学</span>旅鸢 · 智能实训</span><h1>从了解中国，到定制一次好旅行</h1><p>在知识学习与真实场景之间，找到你的下一步。</p></div>
          <span class="intro-status"><i :class="{ online: store.backendOnline }"></i>{{ store.backendOnline ? '实训服务已连接' : '等待服务连接' }}</span>
        </div>
        <!-- 后端状态提示 -->
        <div v-if="!store.backendOnline" class="backend-offline-banner">
          <el-icon><WarningFilled /></el-icon>
          <span>后端服务未连接，部分功能不可用</span>
          <el-button size="small" text @click="store.checkHealth()">重试</el-button>
        </div>

        <!-- AI 对话卡 -->
        <div class="ai-card">
          <div class="ai-card-header">
            <GuofengLandscape class="header-landscape" />
            <div class="header-top">
              <p class="header-title">与旅鸢开启一段新学习</p>
              <div class="header-actions">
                <!-- 起始界面历史对话入口 -->
                <div class="history-wrap dash">
                  <button class="ph-history" :class="{ open: historyOpen }" @click="toggleHistory">
                    <SIcon name="clock" :size="12" /> 历史对话
                    <span v-if="historyList.length" class="hist-count">{{ historyList.length }}</span>
                  </button>
                </div>
                <el-button size="small" round class="new-session-btn" @click="handleNewSession">
                  新对话
                </el-button>
              </div>
            </div>
            <p class="header-sub">输入问题，AI 结合你的画像与学习进度定制内容</p>
          </div>
          <div class="ai-card-body">
            <textarea
              v-model="inputText"
              ref="dashTaRef"
              placeholder="例如：为首次来华的法国游客设计三天上海行程；讲解中国古典园林；练习跨文化客诉处理。"
              rows="3"
              class="ai-input"
              :disabled="sending"
              @keydown.enter.exact="handleSend"
            />
            <div class="ai-toolbar">
              <div class="toolbar-left">
                <button class="tool-btn" disabled><el-icon><Microphone /></el-icon><span>语音</span></button>
                <button class="tool-btn" disabled><el-icon><Link /></el-icon><span>附件</span></button>
                <button class="tool-btn" disabled><el-icon><Picture /></el-icon><span>图片</span></button>
              </div>
              <button class="send-btn" :class="{ active: inputText && !sending }" :disabled="sending || !inputText.trim()" @click="handleSend">
                <el-icon v-if="sending"><Loading /></el-icon>
                <el-icon v-else><Promotion /></el-icon>
                <span>{{ sending ? '思考中...' : '发送' }}</span>
              </button>
            </div>
          </div>
        </div>

        <template v-if="!onboardingActive">
        <!-- 快捷问题 -->
        <section class="section">
          <div class="section-header">
            <h2 class="section-title">快捷提问</h2>
          </div>
          <div class="quick-chips">
            <button v-for="q in quickQuestions" :key="q" class="chip" @click="sendQuick(q)">
              <span class="chip-dot" />
              {{ q }}
            </button>
          </div>
        </section>

        <!-- 统计卡片 -->
        <div class="stats-row">
          <div class="stat-card dark">
            <el-icon class="stat-card-icon flame"><Collection /></el-icon>
            <div class="stat-card-value">{{ userStats.attempted_skills }}</div>
            <div class="stat-card-label">已练技能点</div>
            <div class="stat-card-unit">/ {{ userStats.total_skills }} 个</div>
          </div>
          <div class="stat-card light">
            <el-icon class="stat-card-icon"><CircleCheckFilled /></el-icon>
            <div class="stat-card-value ok">{{ userStats.mastered_skills }}</div>
            <div class="stat-card-label">已掌握</div>
            <div class="stat-card-unit">≥70%</div>
          </div>
          <div class="stat-card light">
            <div class="circular-progress">
              <svg viewBox="0 0 52 52" class="cp-svg">
                <circle cx="26" cy="26" r="22" stroke="#DCEAF7" stroke-width="4" fill="none" />
                <circle cx="26" cy="26" r="22" stroke="#338FF2" stroke-width="4" fill="none"
                        stroke-dasharray="138.2" :stroke-dashoffset="138.2 - 138.2 * completionRate / 100" stroke-linecap="round" />
              </svg>
              <span class="cp-text">{{ completionRate }}%</span>
            </div>
            <div class="stat-card-label">完成率</div>
          </div>
        </div>

        <!-- 学习进度 -->
        <section class="section">
          <div class="section-header">
            <h2 class="section-title">学习进度</h2>
            <button class="section-more" @click="$router.push('/app/training')">去训练场 <el-icon><ArrowRight /></el-icon></button>
          </div>
          <div v-if="masteryEntries.length" class="task-list">
            <div v-for="item in masteryEntries" :key="item.id" class="task-item" @click="goKnowledge">
              <div class="task-status" :class="{ done: item.score >= 80, started: item.score > 0 }">
                <el-icon v-if="item.score >= 80"><CircleCheckFilled /></el-icon>
                <el-icon v-else><Reading /></el-icon>
              </div>
              <div class="task-info">
                <div class="task-title-row">
                  <span class="task-title">{{ item.title }}</span>
                  <span class="task-category">{{ levelLabel(item.score) }}</span>
                </div>
                <div class="task-progress-bar">
                  <div class="progress-track"><div class="progress-fill" :style="{ width: item.score + '%' }" /></div>
                  <span class="progress-pct">{{ item.score }}%</span>
                </div>
              </div>
            </div>
          </div>
          <div v-else-if="weakTitles.length" class="task-list">
            <div v-for="w in weakTitles" :key="w" class="task-item">
              <div class="task-status started"><el-icon><WarningFilled /></el-icon></div>
              <div class="task-info">
                <div class="task-title-row">
                  <span class="task-title">待复习：{{ w }}</span>
                  <span class="task-category">薄弱</span>
                </div>
              </div>
              <div class="task-action">
                <button class="task-go" @click="goTraining">去练习 <el-icon><ArrowRight /></el-icon></button>
              </div>
            </div>
          </div>
          <el-empty v-else description="暂无学习记录 — 先在训练场做几道题，或让 AI 给你制定学习计划" :image-size="60" />
        </section>

        <!-- 推荐条 -->
        <div class="recommend-bar">
          <InkMountain class="rec-ink" />
          <div class="rec-info">
            <span class="rec-tag">下一步建议</span>
            <span class="rec-title">{{ recommendText }}</span>
            <span class="rec-desc">基于你的学习画像与掌握度自动生成</span>
          </div>
          <button class="rec-btn" @click="goRecommend">{{ recommendAction }} <el-icon><ArrowRight /></el-icon></button>
        </div>
        </template>

        <!-- 先验画像 · 身份题在真实对话里由管家完成 -->
        <div v-if="onboardingActive && !onb.identityDone" class="onb-start">
          <div class="os-ic"><SIcon name="sparkle" :size="18" /></div>
          <div class="os-main">
            <div class="os-t">认识你，让实训更适合你</div>
            <div class="os-d">管家会像平时出题一样，在对话里用题卡问你 6 个身份问题（点选项即可）。</div>
          </div>
          <button class="os-btn" @click="startIdentity"><SIcon name="msg" :size="13" />开始画像</button>
        </div>
        <!-- 身份题答完 → 能力自评（7 域 / 84 组） -->
        <OnboardingWizard v-if="onboardingActive && onb.identityDone" @done="onOnboardingDone" />
      </div>
    </div>

    <!-- ══════════════ 纯对话页（有消息） ══════════════ -->
    <div v-else class="hp-page">
      <!-- 页头 -->
      <header class="ph">
        <div class="ph-left">
          <h2 class="ph-title">首页</h2>
          <!-- 历史对话入口（面板在根级共用） -->
          <div class="history-wrap">
            <button class="ph-history" :class="{ open: historyOpen }" @click="toggleHistory">
              <SIcon name="clock" :size="12" /> 历史对话
              <span v-if="historyList.length" class="hist-count">{{ historyList.length }}</span>
            </button>
          </div>
        </div>
        <div class="ph-right">
          <button class="ph-new" @click="handleNewSession">
            <SIcon name="plus" :size="13" /> 新对话
          </button>
          <span class="pill" :class="{ offline: !store.backendOnline }">
            <span class="conn-dot" :class="{ on: store.backendOnline }"></span>
            {{ store.backendOnline ? 'AI 服务在线' : '离线 · 演示模式' }}
          </span>
        </div>
      </header>

      <!-- 教学状态条（一对一教学闭环：当前主题 + 阶段 + 难度 + 连对/连错） -->
      <div v-if="teachingBarVisible" class="teach-bar">
        <span class="tb-label"><SIcon name="book" :size="13" :stroke-width="2" />教学中</span>
        <span class="tb-topic">{{ teachingBarTopics }}</span>
        <span class="tb-stage">{{ teachingStageLabel }}</span>
        <span v-if="teachingDepthLabel" class="tb-depth">{{ teachingDepthLabel }}</span>
        <span v-if="currentTeaching" class="tb-count">
          <template v-if="currentTeaching.consecutive_incorrect > 0">连错 {{ currentTeaching.consecutive_incorrect }}</template>
          <template v-else-if="currentTeaching.consecutive_correct > 0">连对 {{ currentTeaching.consecutive_correct }}</template>
        </span>
        <span v-if="topicMastery" class="tb-mastery" :title="'当前技能点综合掌握度 ' + topicMastery.mastery + '%'">
          掌握 <b>{{ topicMastery.mastery }}%</b><i class="tb-mbar"><u :style="{ width: (topicMastery.mastery || 0) + '%' }"></u></i>
        </span>
        <button class="curve-btn" title="查看动态难度曲线（随答题实时变化）" @click="openCurve"><SIcon name="trend" :size="13" :stroke-width="2" />动态难度曲线</button>
      </div>

      <!-- 升星瞬时提示（难度动态调整） -->
      <transition name="fade">
        <div v-if="bumpTip" class="bump-tip">{{ bumpTip }}</div>
      </transition>

      <div class="hp-body">
        <div class="hp-inner">
          <!-- 对话消息流 -->
          <div class="hp-chat" ref="chatRef">
            <div v-for="(msg, i) in messages" :key="i" class="chat-row" :class="msg.role">
              <div class="chat-av" v-if="msg.role === 'assistant'">
                <img :src="logoMark" alt="旅鸢" />
              </div>
              <div class="chat-main">
                <div class="chat-bubble" v-html="formatContent(msg.content)"></div>
                <!-- 旅鸢讲解：多语种翻译 + 朗读 -->
                <LearnTranslate v-if="msg.role === 'assistant' && msg.content && msg.content.trim() && !(msg.teaching?.stage === 'practicing' && msg.teaching?.last_quiz)" :text="msg.content" />
                <!-- 教学反馈徽标（答错 → 纠错讲解中） -->
                <div v-if="msg.role === 'assistant' && msg.teaching?.stage === 'feedback'" class="chat-msg-teach-badge" :class="{ reteach: (msg.teaching.consecutive_incorrect || 0) > 0 }">
                  <SIcon :name="(msg.teaching.consecutive_incorrect || 0) > 0 ? 'shield' : 'check'" :size="11" />
                  <span>{{ (msg.teaching.consecutive_incorrect || 0) > 0 ? '纠错讲解中 · 老师正在给你重讲' : '学习反馈' }}</span>
                </div>
                <!-- 做题卡片（练习阶段 → 选择题窗口 / 简答题窗口，参考 DSH「让用户选择的窗口」） -->
                <div v-if="msg.role === 'assistant' && msg.teaching?.stage === 'practicing' && msg.teaching?.last_quiz" class="quiz-card">
                  <div class="quiz-card-head">
                    <span class="quiz-type-badge" :class="isEssayQuiz(msg.teaching.last_quiz) ? 'essay' : 'choice'">
                      {{ isEssayQuiz(msg.teaching.last_quiz) ? '进阶 · 简答题' : '基础 · 选择题' }}
                    </span>
                    <span v-if="msg.teaching.last_quiz.difficulty_level" class="quiz-diff" :title="'难度 ' + msg.teaching.last_quiz.difficulty_level + '/5'">
                      <i v-for="n in 5" :key="n" class="qstar" :class="{ on: n <= msg.teaching.last_quiz.difficulty_level }">★</i>
                    </span>
                    <span class="quiz-kp-title">{{ msg.teaching.last_quiz.knowledge_point_title }}</span>
                    <span v-if="msg.teaching.last_quiz.progress && !msg.teaching.last_quiz.progress.exhausted" class="quiz-progress-badge">
                      已做 {{ msg.teaching.last_quiz.progress.done }}/{{ msg.teaching.last_quiz.progress.total }}
                    </span>
                    <span v-else-if="msg.teaching.last_quiz.progress?.exhausted" class="quiz-progress-badge done">
                      本主题选择题已完成 ✅
                    </span>
                  </div>
                  <!-- 选择题窗口：选项按钮卡片，点击即答 -->
                  <div v-if="!isEssayQuiz(msg.teaching.last_quiz) && msg.teaching.last_quiz.options?.length" class="quiz-choice-body">
                    <p class="quiz-prompt">{{ msg.teaching.last_quiz.prompt }}</p>
                    <div class="quiz-options">
                      <button
                        v-for="(opt, oi) in (msg.teaching.last_quiz.options || [])"
                        :key="opt"
                        class="quiz-opt"
                        :class="{ selected: selectedChoice === letterOf(opt, oi) }"
                        :disabled="quizPending || sending"
                        @click="sendAnswer(opt, oi)"
                      >
                        <span class="opt-letter">{{ letterOf(opt, oi) }}</span>
                        <span class="opt-text">{{ stripOptionPrefix(opt) }}</span>
                      </button>
                    </div>
                  </div>
                  <!-- 简答题窗口：题目 + 输入框 + 提交 -->
                  <div v-else class="quiz-essay-body">
                    <p class="quiz-prompt essay">{{ msg.teaching.last_quiz.prompt }}</p>
                    <template v-if="msg.teaching.last_quiz.rubric">
                      <button class="quiz-rubric-toggle" @click="rubricOpen = !rubricOpen">
                        答题后可与参考答案要点对照
                      </button>
                      <p v-if="rubricOpen" class="quiz-rubric">{{ msg.teaching.last_quiz.rubric }}</p>
                    </template>
                    <div class="quiz-essay-input-row">
                      <textarea
                        v-model="essayAnswer"
                        class="quiz-essay-input"
                        rows="2"
                        placeholder="用一两句话写下你的回答"
                        :disabled="quizPending || sending"
                      ></textarea>
                      <button
                        class="quiz-essay-submit"
                        :disabled="quizPending || sending || !essayAnswer.trim()"
                        @click="submitEssayAnswer"
                      >
                        {{ quizPending ? '判分中…' : '提交回答' }}
                      </button>
                    </div>
                  </div>
                </div>
                <!-- 多智能体协同时间轴 -->
                <div v-if="msg.role === 'assistant' && chainOf(msg.tool_calls).length" class="chat-msg-chain">
                  <div class="cc-header">
                    <span class="cc-label">多智能体协同</span>
                    <span v-if="reviewVerdict(msg.review) === 'pass'" class="cc-badge pass">
                      <SIcon name="check" :size="11" />审查通过
                    </span>
                    <span v-else-if="reviewVerdict(msg.review) === 'revised'" class="cc-badge revised">
                      <SIcon name="sparkle" :size="11" />已修订
                    </span>
                    <span v-else-if="msg.review" class="cc-verdict">{{ msg.review }}</span>
                    <button class="cc-toggle" @click="toggleChain(i)">
                      {{ isChainOpen(i) ? '收起' : '展开' }}
                      <SIcon :name="isChainOpen(i) ? 'up' : 'right'" :size="10" />
                    </button>
                  </div>
                  <div v-show="isChainOpen(i)" class="cc-timeline">
                    <div v-for="(step, si) in chainOf(msg.tool_calls)" :key="step.tool" class="cc-node">
                      <div class="cc-node-marker">
                        <span class="cc-node-dot" :class="{ current: si === chainOf(msg.tool_calls).length - 1 }">{{ si + 1 }}</span>
                        <span v-if="si < chainOf(msg.tool_calls).length - 1" class="cc-node-stem"></span>
                      </div>
                      <div class="cc-node-body">
                        <span class="cc-step"><SIcon :name="stepIcon(step.tool)" :size="12" />{{ step.agent }}</span>
                        <span class="cc-step-label">{{ step.label }}</span>
                      </div>
                    </div>
                  </div>
                </div>
                <!-- 资产卡片 -->
                <div v-if="msg.assets?.length" class="chat-msg-assets">
                  <span class="ca-text">📁 已生成 {{ msg.assets.length }} 份文件资产，已保存到学习中心</span>
                  <el-button size="small" type="primary" round @click="$router.push('/app/knowledge-tree')">前往查看</el-button>
                </div>
              </div>
            </div>
            <!-- 多智能体协同实时直播：每个 Agent 一行，点开看分工，再看思考 -->
            <div class="chat-row assistant" v-if="sending">
              <div class="chat-av">
                <img :src="logoMark" alt="旅鸢" />
              </div>
              <div class="chat-main" :class="{ 'ma-wide': liveTrace.length > 0 }">
                <div v-if="liveTrace.length === 0" class="chat-bubble thinking">
                  <span class="think-spin"></span>
                  <span class="t-text">{{ thinkingText }}</span>
                </div>
                <div v-else class="ma-panel">
                  <div class="ma-head">
                    <span class="ma-title"><i class="ma-live-dot"></i>多智能体协同</span>
                    <span class="ma-badge live">实时</span>
                    <span class="ma-count"><b>{{ liveDone }}</b>/{{ liveTrace.length }}</span>
                    <button class="ma-fold" @click="toggleAllAgents">
                      <SIcon :name="allAgentsOpen ? 'up' : 'right'" :size="11" />{{ allAgentsOpen ? '全部收起' : '全部展开' }}
                    </button>
                  </div>
                  <div class="ma-topo" v-if="liveStages.length">
                    <template v-for="(a, ai) in liveStages" :key="a.agent">
                      <div class="ma-actor" :class="a.status">
                        <span class="ma-actor-ico"><SIcon :name="a.icon" :size="13" /></span>
                        <span class="ma-actor-name">{{ a.short }}</span>
                        <i v-if="a.status === 'busy'" class="ma-actor-spin"><span></span></i>
                        <i v-else-if="a.status === 'done'" class="ma-actor-ok"><SIcon name="check" :size="8" /></i>
                      </div>
                      <span v-if="ai < liveStages.length - 1" class="ma-topo-arrow"><SIcon name="right" :size="10" /></span>
                    </template>
                  </div>
                  <div class="ma-stream" ref="maStreamRef">
                    <div v-for="ag in liveAgents" :key="ag.agent" class="ma-agent" :class="[ag.status, ag.agent]">
                      <button class="ma-agent-row" @click="toggleAgent(ag.agent)">
                        <SIcon class="ma-agent-chev" :name="isAgentOpen(ag.agent) ? 'up' : 'right'" :size="12" />
                        <span class="ma-agent-ico"><SIcon :name="ag.icon" :size="17" /></span>
                        <span class="ma-agent-txt">
                          <span class="ma-agent-name">{{ ag.name }}</span>
                          <span class="ma-agent-role">{{ ag.lastRole }}<i v-if="ag.count > 1"> · {{ ag.count }} 次</i></span>
                        </span>
                        <span class="ma-agent-st">
                          <span v-if="ag.status === 'busy'" class="ma-spin"></span>
                          <span v-else-if="ag.status === 'done'" class="ma-ok"><SIcon name="check" :size="13" /></span>
                          <span v-else-if="ag.status === 'fail'" class="ma-ng"><SIcon name="warn" :size="13" /></span>
                        </span>
                      </button>
                      <div v-if="isAgentOpen(ag.agent)" class="ma-agent-body">
                        <div v-for="(ev, ei) in ag.events" :key="ei" class="ma-ev" :class="ev.status">
                          <div class="ma-ev-bar">
                            <span class="ma-ev-idx">{{ ei + 1 }}</span>
                            <span class="ma-ev-role">{{ ev.role }}</span>
                            <span class="ma-ev-st">
                              <span v-if="ev.status === 'working'" class="ma-spin sm"></span>
                              <SIcon v-else-if="ev.status === 'done'" name="check" :size="12" />
                              <SIcon v-else-if="ev.status === 'failed'" name="warn" :size="12" />
                            </span>
                          </div>
                          <button v-if="ev.detail" class="ma-think" @click.stop="toggleNote(ag.agent, ei)">
                            <SIcon :name="noteOpen(ag.agent, ei) ? 'up' : 'eye'" :size="11" />
                            {{ noteOpen(ag.agent, ei) ? '收起思考' : '查看思考' }}
                          </button>
                          <div v-if="noteOpen(ag.agent, ei)" class="ma-note">{{ ev.detail }}</div>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <!-- 快捷提问 chips -->
          <div class="hp-chips">
            <button v-for="q in quickQuestions" :key="q" class="chip" @click="sendQuick(q)" :disabled="sending">
              {{ q }}
            </button>
          </div>

          <OnboardingWizard v-if="inChat && onb.identityDone && !onb.done" class="onb-in-chat" @done="onOnboardingDone" />
          <!-- 任务阶段提示条（轮询期间展示） -->
          <div v-if="sending && taskPhase && liveTrace.length === 0" class="task-phase-bar">
            <span class="ma-spin sm"></span>
            <span class="tpb-text">{{ phaseText }}</span>
            <span v-if="taskPhase === 'failed'" class="tpb-status fail">任务失败</span>
          </div>

          <!-- 输入栏 -->
          <!-- ══ 主题完成 → 选择去向（三选卡片） ══ -->
          <div v-if="showDone" class="done-panel">
            <div class="done-title">本主题题目已全部答完</div>
            <div class="done-sub">接下来想做什么？</div>
            <div v-if="topicMastery" class="done-mastery">
              <span class="dm-k">Agent 学情评估</span><b class="dm-v">{{ topicMastery.concierge ?? 0 }}%</b>
              <span class="dm-k">综合掌握度</span><b class="dm-v">{{ topicMastery.mastery ?? 0 }}%</b>
            </div>
            <div class="done-actions">
              <button class="done-btn" @click="router.push('/app/knowledge-tree')">
                <SIcon name="target" :size="14" />再学一个技能点<SIcon name="right" :size="12" />
              </button>
              <button class="done-btn sandbox" @click="goSandboxChallenge">
                <SIcon name="swords" :size="14" />去沙盒挑战 5★ 实战<SIcon name="right" :size="12" />
              </button>
              <button class="done-btn chat" @click="startFreeChat">
                <SIcon name="msg" :size="14" />自由问答<SIcon name="right" :size="12" />
              </button>
            </div>
          </div>

          <div class="hp-input">
            <div class="input-box">
              <textarea
                v-model="inputText"
                ref="taRef"
                class="input-ta"
                :placeholder="inputPlaceholder"
                rows="2"
                :disabled="sending"
                @keydown.enter.exact.prevent="handleSend"
              ></textarea>
              <div class="input-actions">
                <button class="ia-btn" :class="{ on: voiceRecOn }"
                        :disabled="sending || voiceTranscribing"
                        :title="voiceRecOn ? '停止录音' : voiceTranscribing ? '语音识别中…' : '语音输入'"
                        @click="toggleVoiceRec">
                  <SIcon name="mic" :size="15" :color="voiceRecOn ? '#338FF2' : ''" />
                </button>
                <span v-if="voiceRecLabel" class="home-mic-tag">{{ voiceRecLabel }}</span>
                <div class="ia-attach">
                  <button class="ia-btn" :class="{ on: attachOpen }" :disabled="sending" @click="attachOpen = !attachOpen" title="附件">
                    <SIcon name="clip" :size="15" />
                  </button>
                  <div class="attach-menu" :class="{ open: attachOpen }">
                    <div class="attach-item" v-for="a in attachItems" :key="a.label" @click="attachAction(a.label)">
                      <SIcon :name="a.icon" :size="15" color="#6B7280" />
                      <div><div class="t">{{ a.label }}</div><div class="d">{{ a.desc }}</div></div>
                    </div>
                  </div>
                </div>
                <button class="send-btn" :class="{ active: canSend }" :disabled="!canSend" @click="handleSend">
                  <SIcon name="up" :size="15" color="#fff" :stroke-width="2.5" />
                </button>
              </div>
            </div>
            <div class="input-hint">回车发送 · Shift+回车换行 · AI 生成内容仅供参考</div>
          </div>
        </div>
      </div>
    </div>
  </div>

  <!-- ══ 动态难度曲线弹窗 ══ -->
  <el-dialog v-model="curveOpen" title="📈 动态难度曲线" width="580px" append-to-body class="curve-dialog">
    <div v-if="curveLoading" class="curve-loading">加载中…</div>
    <template v-else>
      <div v-if="curve && curve.points.length" class="curve-wrap">
        <svg :viewBox="`0 0 ${chartW} ${chartH}`" class="curve-svg">
          <!-- 网格 + 难度刻度 1-5 -->
          <template v-for="lv in 5" :key="lv">
            <line :x1="padL" :y1="yOf(lv)" :x2="chartW - padR" :y2="yOf(lv)" class="grid-line" />
            <text :x="padL - 8" :y="yOf(lv) + 4" class="grid-label" text-anchor="end">{{ lv }}★</text>
          </template>
          <!-- 连线（只连相邻难度点，直观展示走向） -->
          <!-- 圆润曲线（贝塞尔） -->
          <path v-if="smoothPath" :d="smoothPath" class="curve-line" fill="none" />
          <!-- 各作答点：绿=答对 红=答错 -->
          <circle v-for="p in curve.points" :key="p.seq" :cx="xOf(p.seq)" :cy="yOf(p.difficulty_level)" r="5"
                  :class="p.correct ? 'pt-correct' : 'pt-wrong'" />
          <!-- 当前题目的难度点（高亮） -->
          <g v-if="curve.current && curve.current.difficulty_level">
            <circle :cx="currentX" :cy="yOf(curve.current.difficulty_level)" r="8" class="pt-current" />
            <text :x="currentX" :y="yOf(curve.current.difficulty_level) - 12" text-anchor="middle" class="cur-label">当前</text>
          </g>
        </svg>
        <div class="curve-legend">
          <span><i class="dot pt-correct"></i>答对</span>
          <span><i class="dot pt-wrong"></i>答错</span>
          <span><i class="dot pt-current"></i>当前难度</span>
        </div>
      </div>
      <el-empty v-else description="还没有作答记录，先去练几道题吧" :image-size="64" />

      <div v-if="curve" class="curve-status">
        <div class="curve-status-text">{{ curve.status.text || '完成题目后这里会给出难度状态提示' }}</div>
        <el-button v-if="curve.status.can_sandbox" type="primary" round @click="goSandboxChallenge">
          去 5★ 沙盒挑战 →
        </el-button>
      </div>
    </template>
  </el-dialog>

</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  Microphone, Link, Picture, Promotion, ArrowRight, Collection,
  Reading, CircleCheckFilled, WarningFilled, Loading,
} from '@element-plus/icons-vue'
import SIcon from '@/components/SIcon.vue'
import InkMountain from '@/components/InkMountain.vue'
import GuofengLandscape from '@/components/GuofengLandscape.vue'
import LearnTranslate from '@/components/LearnTranslate.vue'
import logoMark from '@/assets/lvyuan-logo.jpg'
import { sendMessageWithPhase } from '@/api/messages'
import { transcribeAudio } from '@/api/voice'
import type { AgentTrace, TaskPhase, TeachingQuiz, TeachingSnapshot } from '@/api/messages'
import { getTeachingState, getDifficultyCurve, getMasteryState } from '@/api/teaching'
import type { DifficultyCurve, MasteryState } from '@/api/teaching'
import { listSessions, getSessionMessages } from '@/api/sessions'
import type { SessionItem } from '@/api/sessions'
import { getUserState } from '@/api/profile'
import { getKnowledgeTree, getSkillDetail } from '@/api/knowledge'
import { nextStepFromTree } from '@/utils/nextStep'
import type { SkillNode } from '@/api/knowledge'
import { useAppStore } from '@/stores/app'
import { useOnboardingStore } from '@/stores/onboarding'
import OnboardingWizard from '@/components/OnboardingWizard.vue'
import { classifyError, ApiErrorType } from '@/api/client'
import { ElMessage } from 'element-plus'

const store = useAppStore()
const router = useRouter()
const route = useRoute()
const onb = useOnboardingStore()
const onboardingActive = computed(() => !onb.done && !onb.loading)

function onOnboardingDone() {
  // 完成引导：刷新画像状态与仪表盘数据
  onb.load(store.userId)
  loadState()
}

// ── 对话状态 ──
const inputText = ref('')
const sending = ref(false)
const attachOpen = ref(false)

// ── 语音输入（录音 -> /voice/transcribe -> 填入输入框，同训练场） ──
const voiceRecOn = ref(false)
const voiceTranscribing = ref(false)
const voiceRecLabel = ref('')
let voiceRec: MediaRecorder | null = null
let voiceChunks: BlobPart[] = []
let voiceRecTimer: ReturnType<typeof setInterval> | null = null
let voiceRecSec = 0

function toggleVoiceRec() {
  if (voiceTranscribing.value) return
  if (voiceRecOn.value) stopVoiceRec()
  else void startVoiceRec()
}
async function startVoiceRec() {
  if (!navigator.mediaDevices || !window.MediaRecorder) {
    ElMessage.warning('当前环境不支持录音，请用 Chrome / Edge')
    return
  }
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
    voiceChunks = []
    voiceRec = new MediaRecorder(stream)
    voiceRec.ondataavailable = (e) => { if (e.data.size) voiceChunks.push(e.data) }
    voiceRec.onstop = () => { stream.getTracks().forEach((t) => t.stop()); void uploadVoiceRec() }
    voiceRec.start()
    voiceRecOn.value = true
    voiceRecSec = 0
    voiceRecLabel.value = '正在录音…'
    voiceRecTimer = setInterval(() => { voiceRecSec++; voiceRecLabel.value = `正在录音 ${voiceRecSec}s` }, 1000)
  } catch (e: any) {
    ElMessage.error('无法使用麦克风：' + e.message)
  }
}
function stopVoiceRec() {
  if (!voiceRecOn.value || !voiceRec) return
  if (voiceRecTimer) { clearInterval(voiceRecTimer); voiceRecTimer = null }
  voiceRec.stop()
  voiceRecOn.value = false
  voiceTranscribing.value = true
  voiceRecLabel.value = '语音识别中…'
}
async function uploadVoiceRec() {
  try {
    if (!voiceChunks.length) {
      voiceTranscribing.value = false
      voiceRecLabel.value = ''
      return
    }
    const blob = new Blob(voiceChunks, { type: 'audio/webm' })
    const r = await transcribeAudio(blob)
    voiceTranscribing.value = false
    voiceRecLabel.value = ''
    if (r.text && r.text.trim()) {
      inputText.value = (inputText.value ? inputText.value + ' ' : '') + r.text.trim()
      ElMessage.success('已识别，可编辑后发送')
      await nextTick()
      taRef.value?.focus()
    } else {
      ElMessage.info('未识别到内容，请重录')
    }
  } catch (e: any) {
    voiceTranscribing.value = false
    voiceRecLabel.value = ''
    ElMessage.error('语音识别失败：' + (e?.message || String(e)))
  } finally {
    voiceRec = null
  }
}
function cleanupVoiceRec() {
  if (voiceRecTimer) { clearInterval(voiceRecTimer); voiceRecTimer = null }
  if (voiceRec && voiceRec.state !== 'inactive') { try { voiceRec.stop() } catch (e) { /* noop */ } }
  voiceRecOn.value = false
}
onUnmounted(() => cleanupVoiceRec())
const chatRef = ref<HTMLElement | null>(null)
const taRef = ref<HTMLTextAreaElement | null>(null)
const dashTaRef = ref<HTMLTextAreaElement | null>(null)
const messages = ref<{ role: 'user' | 'assistant'; content: string; tool_calls?: string[]; review?: string; assets?: Array<{ asset_id: string; title: string; asset_type: string }>; trace?: AgentTrace[]; teaching?: TeachingSnapshot | null }[]>([])

// 教学状态（一对一教学闭环）：取最近一条助手消息的快照；进入对话页时从后端恢复
const currentTeaching = ref<TeachingSnapshot | null>(null)
const TEACH_STAGE_LABEL: Record<string, string> = {
  goal_setting: '定目标',
  teaching: '讲解中',
  checking: '确认理解',
  practicing: '练习中',
  feedback: '反馈',
  closing: '小结',
  idle: '空闲',
}
const teachingBarVisible = computed(() =>
  !!currentTeaching.value && (currentTeaching.value.topics.length > 0 || currentTeaching.value.stage !== 'goal_setting'),
)
const teachingBarTopics = computed(() =>
  (currentTeaching.value?.topics || []).map((t) => t.title).join('、'),
)
const teachingStageLabel = computed(() =>
  currentTeaching.value ? (TEACH_STAGE_LABEL[currentTeaching.value.stage] || currentTeaching.value.stage) : '',
)
// T6：难度档位 + 输入框衔接提示（上下文可见：让学员清楚课讲到哪、什么难度）
const TEACH_DEPTH_LABEL: Record<string, string> = {
  intro: '入门难度',
  basic: '基础难度',
  advanced: '进阶难度',
  comprehensive: '综合难度',
}
const teachingDepthLabel = computed(() =>
  currentTeaching.value ? (TEACH_DEPTH_LABEL[currentTeaching.value.depth] || '') : '',
)
const inputPlaceholder = computed(() => {
  if (sending.value) return '旅鸢老师思考中……'
  if (currentTeaching.value && currentTeaching.value.topics.length > 0) {
    return `接着说……（我们正在讲${teachingBarTopics.value}）`
  }
  return '问旅鸢老师任何备考问题……'
})

// 状态：无消息 → 仪表盘；有消息 → 纯对话页

// ── 动态难度曲线（弹窗） ──
const freeChatMode = ref(false)  // 自由问答模式：题目做完后选择「自由问答」进入
const lastQuizLevel = ref<number | null>(null)
const bumpTip = ref('')  // 升星瞬时提示
const topicMastery = ref<MasteryState | null>(null)  // 当前技能点综合掌握度
const curveOpen = ref(false)
const curveLoading = ref(false)
const curve = ref<DifficultyCurve | null>(null)
const chartW = 520
const chartH = 240
const padL = 42
const padR = 16

function yOf(level: number): number {
  const top = 28
  const bottom = chartH - 30
  const lv = Math.min(5, Math.max(1, level))
  return top + ((5 - lv) / 4) * (bottom - top)
}

function xOf(seq: number): number {
  const n = Math.max(curve.value?.points.length || 1, 1)
  if (n === 1) return padL + (chartW - padL - padR) / 2
  return padL + ((seq - 1) / (n - 1)) * (chartW - padL - padR)
}

const linePoints = computed(() =>
  (curve.value?.points || []).map((p) => `${xOf(p.seq)},${yOf(p.difficulty_level)}`).join(' '),
)

const currentX = computed(() => {
  const pts = curve.value?.points || []
  const seq = pts.length ? pts[pts.length - 1].seq + 1 : 1
  return xOf(seq)
})

async function openCurve() {
  curveOpen.value = true
  if (curve.value) return
  curveLoading.value = true
  try {
    curve.value = await getDifficultyCurve(store.sessionId, store.userId)
  } catch {
    curve.value = null
  topicMastery.value = null
  } finally {
    curveLoading.value = false
  }
}

async function refreshCurve() {
  try { curve.value = await getDifficultyCurve(store.sessionId, store.userId) } catch { /* ignore */ }
}

function goSandboxChallenge() {
  curveOpen.value = false
  router.push('/app/training')
}

// 圆润贝塞尔曲线（Catmull-Rom → 三次贝塞尔），难度变化连贯不折线
const smoothPath = computed(() => {
  const pts = curve.value?.points || []
  if (pts.length < 2) return ''
  const xs = pts.map((p) => xOf(p.seq))
  const ys = pts.map((p) => yOf(p.difficulty_level))
  let d = `M ${xs[0]},${ys[0]}`
  for (let i = 0; i < pts.length - 1; i++) {
    const p0 = pts[i - 1] || pts[i]
    const p1 = pts[i]
    const p2 = pts[i + 1]
    const p3 = pts[i + 2] || p2
    const p0x = xOf(p0.seq), p0y = yOf(p0.difficulty_level)
    const p1x = xOf(p1.seq), p1y = yOf(p1.difficulty_level)
    const p2x = xOf(p2.seq), p2y = yOf(p2.difficulty_level)
    const p3x = xOf(p3.seq), p3y = yOf(p3.difficulty_level)
    const c1x = p1x + (p2x - p0x) / 6
    const c1y = p1y + (p2y - p0y) / 6
    const c2x = p2x - (p3x - p1x) / 6
    const c2y = p2y - (p3y - p1y) / 6
    d += ` C ${c1x},${c1y} ${c2x},${c2y} ${p2x},${p2y}`
  }
  return d
})


// 主题完成判定：教学快照 topic_done 或难度曲线 all_done（任一为真即弹三选卡，兜底防漏）
const showDone = computed(() =>
  !freeChatMode.value && (!!currentTeaching.value?.topic_done || !!currentTeaching.value?.topic_finished || !!curve.value?.all_done),
)

async function refreshTopicMastery() {
  const nid = currentTeaching.value?.topics?.[0]?.id
  if (!nid) { topicMastery.value = null; return }
  try { topicMastery.value = await getMasteryState(store.userId, nid) }
  catch { /* 后端不可用 */ }
}

function startFreeChat() {
  freeChatMode.value = true
  inputText.value = '（进入自由问答模式：接下来请只做日常答疑聊天，不要出题、不要判分、不要调用任何工具，也不要再总结题目进度。）'
  nextTick().then(() => handleSend())
}


const inChat = computed(() => messages.value.length > 0)

const canSend = computed(() => inputText.value.trim().length > 0 && !sending.value)

// 多智能体协同链路：工具名 → Agent 角色
const AGENT_CHAIN: Record<string, { agent: string; label: string }> = {
  search_knowledge: { agent: '知识检索', label: '检索知识库' },
  generate_material: { agent: '内容生成', label: '生成材料' },
  review_material: { agent: '六帽审查', label: '质量审查' },
  quiz_user: { agent: '训练场', label: '抽题测验' },
  submit_answer: { agent: '训练场', label: '判分' },
  generate_report: { agent: '学习分析', label: '生成报告' },
  generate_plan: { agent: '计划制定', label: '生成计划' },
  update_profile: { agent: '画像更新', label: '更新画像' },
  generate_essay_question: { agent: '简答出题', label: '进阶出题' },
}

// 工具调用顺序去重 → 协同链路（如 检索→生成→审查），tool 保留工具名供图标映射
function chainOf(toolCalls: string[] | undefined): { tool: string; agent: string; label: string }[] {
  if (!toolCalls?.length) return []
  const seen = new Set<string>()
  const chain: { tool: string; agent: string; label: string }[] = []
  for (const t of toolCalls) {
    if (seen.has(t)) continue
    seen.add(t)
    const meta = AGENT_CHAIN[t]
    if (meta) chain.push({ tool: t, agent: meta.agent, label: meta.label })
  }
  return chain
}

// 时间轴步骤图标：工具名 → SIcon 名称（拿不准的兜底 sparkle）
const AGENT_ICONS: Record<string, string> = {
  search_knowledge: 'search',
  generate_material: 'filetext',
  review_material: 'shield',
  quiz_user: 'check',
  submit_answer: 'check',
  generate_report: 'bookcheck',
  generate_plan: 'target',
  update_profile: 'user',
  generate_essay_question: 'target',
}
function stepIcon(tool: string): string {
  return AGENT_ICONS[tool] || 'sparkle'
}

// 审查里程碑：含「合格」→ 绿勾「审查通过」；含「需修改」→ 黄标「已修订」；其余原样展示
function reviewVerdict(review: string | undefined): 'pass' | 'revised' | '' {
  if (!review) return ''
  if (review.includes('合格')) return 'pass'
  if (review.includes('需修改')) return 'revised'
  return ''
}

// 时间轴折叠状态：默认展开，记录已折叠的消息下标
const chainCollapsed = ref<Set<number>>(new Set())
function isChainOpen(i: number): boolean {
  return !chainCollapsed.value.has(i)
}
function toggleChain(i: number) {
  const next = new Set(chainCollapsed.value)
  if (next.has(i)) next.delete(i)
  else next.add(i)
  chainCollapsed.value = next
}

// ── 任务阶段提示条（T15） ──
const PHASE_TEXT: Record<TaskPhase, string> = {
  queued: '排队中…',
  working: '旅鸢正在处理（检索/生成材料）…',
  reviewing: '六帽审查中…',
  done: '完成',
  failed: '失败',
}
const taskPhase = ref<TaskPhase | null>(null)
const phaseText = computed(() => (taskPhase.value ? PHASE_TEXT[taskPhase.value] : ''))

// ── 多 Agent 实时协同直播：每个 Agent 一行，可展开分工详情 / 思考内容 ──
const liveTrace = ref<AgentTrace[]>([])
const maStreamRef = ref<HTMLElement | null>(null)
// agent 键 → 顶部拓扑阶段（六帽并入“审查”一个节点）
const STAGE_MAP: Record<string, { key: string; short: string; icon: string }> = {
  concierge: { key: 'concierge', short: '旅鸢', icon: 'sparkle' },
  retrieval: { key: 'retrieval', short: '检索', icon: 'search' },
  draft: { key: 'draft', short: '起草', icon: 'filetext' },
  review: { key: 'review', short: '审查', icon: 'shield' },
  white_hat: { key: 'review', short: '审查', icon: 'shield' },
  black_hat: { key: 'review', short: '审查', icon: 'shield' },
  green_hat: { key: 'review', short: '审查', icon: 'shield' },
  yellow_hat: { key: 'review', short: '审查', icon: 'shield' },
  red_hat: { key: 'review', short: '审查', icon: 'shield' },
  blue_hat: { key: 'review', short: '审查', icon: 'shield' },
  trainer: { key: 'trainer', short: '测评', icon: 'check' },
  essay: { key: 'essay', short: '出题', icon: 'target' },
  analyzer: { key: 'analyzer', short: '分析', icon: 'bookcheck' },
  planner: { key: 'planner', short: '计划', icon: 'clock' },
  profile: { key: 'profile', short: '画像', icon: 'user' },
}
const TRACE_ICONS: Record<string, string> = {
  concierge: 'sparkle', retrieval: 'search', draft: 'filetext', review: 'shield',
  white_hat: 'shield', black_hat: 'shield', green_hat: 'shield',
  yellow_hat: 'shield', red_hat: 'shield', blue_hat: 'shield',
  trainer: 'check', essay: 'target', analyzer: 'bookcheck', planner: 'clock', profile: 'user',
}
function traceIcon(agent: string): string {
  return TRACE_ICONS[agent] || 'sparkle'
}
const _statusOf = (s: string) => s === 'failed' ? 'fail' : s === 'working' ? 'busy' : 'done'
// 顶部拓扑：按阶段聚合（六帽一个“审查”节点）
const liveStages = computed(() => {
  const order: string[] = []
  const last: Record<string, string> = {}
  for (const ev of liveTrace.value) {
    const meta = STAGE_MAP[ev.agent]
    const key = meta ? meta.key : ev.agent
    if (!(key in last)) order.push(key)
    last[key] = ev.status
  }
  return order.map((key) => {
    const meta = STAGE_MAP[key] || { key, short: key, icon: 'sparkle' }
    return { agent: key, short: meta.short, icon: meta.icon, status: _statusOf(last[key]) }
  })
})
// 主体列表：每个 Agent 聚合为一行（含该 Agent 的全部事件，展开可见）
const liveAgents = computed(() => {
  const grouped: Record<string, { agent: string; name: string; icon: string; events: AgentTrace[] }> = {}
  const order: string[] = []
  for (const ev of liveTrace.value) {
    if (!grouped[ev.agent]) {
      grouped[ev.agent] = { agent: ev.agent, name: ev.name, icon: traceIcon(ev.agent), events: [] }
      order.push(ev.agent)
    }
    grouped[ev.agent].events.push(ev)
  }
  return order.map((k) => {
    const g = grouped[k]
    const last = g.events[g.events.length - 1]
    return {
      agent: g.agent,
      name: g.name,
      icon: g.icon,
      count: g.events.length,
      status: _statusOf(last.status),
      lastRole: last.role,
      events: g.events,
    }
  })
})
const liveDone = computed(() =>
  liveTrace.value.filter((e) => e.status === 'done' || e.status === 'failed').length,
)
// 展开/折叠：默认展开，可单 Agent 折叠，也可一键全部收起
const collapsedAgents = ref<Set<string>>(new Set())
const allAgentsOpen = computed(() => liveAgents.value.length > 0 && collapsedAgents.value.size === 0)
function isAgentOpen(agent: string): boolean {
  return !collapsedAgents.value.has(agent)
}
function toggleAgent(agent: string) {
  const next = new Set(collapsedAgents.value)
  if (next.has(agent)) next.delete(agent)
  else next.add(agent)
  collapsedAgents.value = next
}
function toggleAllAgents() {
  if (allAgentsOpen.value) collapsedAgents.value = new Set(liveAgents.value.map((a) => a.agent))
  else collapsedAgents.value = new Set()
}
// 每条事件可再点开“思考内容”
const openNotes = ref<Set<string>>(new Set())
function noteKey(agent: string, ei: number): string {
  return `${agent}#${ei}`
}
function noteOpen(agent: string, ei: number): boolean {
  return openNotes.value.has(noteKey(agent, ei))
}
function toggleNote(agent: string, ei: number) {
  const key = noteKey(agent, ei)
  const next = new Set(openNotes.value)
  if (next.has(key)) next.delete(key)
  else next.add(key)
  openNotes.value = next
}
// trace 更新 → 自动滚到面板底部（看最新一步）
watch(liveTrace, async () => {
  await nextTick()
  const el = maStreamRef.value
  if (el) el.scrollTop = el.scrollHeight
})

// 简易 markdown 渲染：转义 + 换行 + 加粗
function formatContent(text: string): string {
  return text
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/\*\*(.+?)\*\*/g, '<b>$1</b>')
    .replace(/\n/g, '<br>')
}

// ── 思考动画 ──
const thinkingTexts = ['正在思考…', '正在检索知识库…', '正在组织回答…']
const thinkingIdx = ref(0)
let thinkingTimer: ReturnType<typeof setInterval> | null = null

function startThinkingAnim() {
  thinkingIdx.value = 0
  thinkingTimer = setInterval(() => {
    thinkingIdx.value = (thinkingIdx.value + 1) % thinkingTexts.length
  }, 1600)
}
function stopThinkingAnim() {
  if (thinkingTimer) { clearInterval(thinkingTimer); thinkingTimer = null }
}
const thinkingText = computed(() => thinkingTexts[thinkingIdx.value])

async function scrollToBottom() {
  await nextTick()
  const el = chatRef.value
  if (el) el.scrollTop = el.scrollHeight
}

function handleNewSession() {
  stopThinkingAnim()
  attachOpen.value = false
  store.newSession()
  messages.value = []
  currentTeaching.value = null
  curve.value = null
  topicMastery.value = null
  freeChatMode.value = false
  historyOpen.value = false
  quizPending.value = false
  selectedChoice.value = ''
  essayAnswer.value = ''
  rubricOpen.value = false
  refreshHistory()  // 刷新列表（新会话尚未产生消息，列表不变）
  ElMessage.success('已开启新对话')
}

// ── 历史对话列表（可切换会话） ──
const historyOpen = ref(false)
const historyList = ref<SessionItem[]>([])

function toggleHistory() {
  historyOpen.value = !historyOpen.value
  if (historyOpen.value && !historyList.value.length) refreshHistory()
}

async function refreshHistory() {
  try {
    const res = await listSessions(store.userId)
    historyList.value = res.sessions || []
  } catch { /* 后端不可用时静默 */ }
}

function formatSessionTime(t: string | null): string {
  if (!t) return ''
  const d = new Date(t)
  const now = new Date()
  const sameDay = d.toDateString() === now.toDateString()
  if (sameDay) return d.toTimeString().slice(0, 5)
  return `${d.getMonth() + 1}/${d.getDate()}`
}

async function switchSession(s: SessionItem) {
  if (s.session_id === store.sessionId) { historyOpen.value = false; return }
  stopThinkingAnim()
  attachOpen.value = false
  historyOpen.value = false
  store.sessionId = s.session_id
  localStorage.setItem('boc_session_id', s.session_id)
  messages.value = []
  currentTeaching.value = null
  quizPending.value = false
  selectedChoice.value = ''
  essayAnswer.value = ''
  rubricOpen.value = false
  sending.value = true
  try {
    const res = await getSessionMessages(s.session_id)
    messages.value = (res.messages || []).map((m) => ({
      role: m.role === 'assistant' ? 'assistant' : 'user',
      content: m.content,
    }))
    // 恢复该会话的教学状态（主题/阶段/难度）
    try {
      const state = await getTeachingState(s.session_id, store.userId)
      if (state) currentTeaching.value = state
    } catch { /* 无教学状态 */ }
    ElMessage.success(`已切换到「${s.title}」`)
  } catch (e: any) {
    ElMessage.error('加载历史对话失败：' + classifyError(e).message)
  } finally {
    sending.value = false
    scrollToBottom()
  }
}

// ── 做题卡片状态（练习阶段：选择题窗口 / 简答题窗口） ──
const quizPending = ref(false)          // 答题 pending：点击选项 / 提交简答后置 true，收到下一条 assistant 消息清除
const selectedChoice = ref('')          // 选择题本地选中字母（选中按钮金色填充 + 全部按钮 disabled）
const essayAnswer = ref('')             // 简答题 textarea 输入
const rubricOpen = ref(false)           // 简答参考答案要点展开/收起

/** 解析选项字母：优先解析选项自带字母前缀（A./B、/C．），否则按位置回退生成 A-D 字母 */
function letterOf(opt: string, index = 0): string {
  const m = opt.trim().match(/^([A-Da-d])[.、．]/)
  return m ? m[1].toUpperCase() : String.fromCharCode(65 + index)
}

/** 剥离选项文本的字母前缀（A. / B、 / C．），仅显示文字部分 */
function stripOptionPrefix(opt: string): string {
  return opt.trim().replace(/^[A-Da-d][.、．]\s*/, '')
}

/** 题型判断：缺省视为选择题 */
function isEssayQuiz(quiz: TeachingQuiz): boolean {
  return quiz.type === 'essay'
}

/** 点击选择题选项 → 本地选中 + 以「我选 X」发送（管家收到后调 submit_answer 判分） */
function sendAnswer(option: string, index = 0) {
  if (quizPending.value || sending.value) return
  const letter = letterOf(option, index)
  if (!letter) return
  selectedChoice.value = letter
  quizPending.value = true
  inputText.value = `我选 ${letter}`
  handleSend()
}

/** 提交简答题回答 → 以「我的回答：xxx」发送（管家收到后判分），发送中禁用 */
function submitEssayAnswer() {
  const content = essayAnswer.value.trim()
  if (!content || quizPending.value || sending.value) return
  quizPending.value = true
  inputText.value = `我的回答：${content}`
  essayAnswer.value = ''
  handleSend()
}

async function handleSend() {
  const content = inputText.value.trim()
  if (!content || sending.value) return
  const focus = hardFocus.value
  hardFocus.value = null
  messages.value.push({ role: 'user', content })
  inputText.value = ''
  sending.value = true
  taskPhase.value = 'queued'
  liveTrace.value = []
  startThinkingAnim()
  scrollToBottom()
  try {
    const result = await sendMessageWithPhase(
      { user_id: store.userId, session_id: store.sessionId, content, knowledge_point_id: focus || undefined },
      (phase) => { taskPhase.value = phase },
      (trace) => { liveTrace.value = trace },
    )
    messages.value.push({
      role: 'assistant',
      content: result.content || '(无响应)',
      tool_calls: result.tool_calls || [],
      review: result.review || '',
      assets: result.assets || [],
      trace: result.trace || [],
      teaching: result.teaching ?? null,
    })
    if (result.teaching) currentTeaching.value = result.teaching
    onb.loadQa(store.userId) // 管家可能在对话中推进了身份题
    refreshCurve() // 对话变化后刷新难度曲线缓存
    refreshTopicMastery() // 同步当前技能点掌握度进度条
    // ── 升星瞬时提示：新题难度 > 上一题 → 顶部闪过“已动态调整难度” ──
    const _tq = result.teaching?.last_quiz
    if (result.teaching?.stage === 'practicing' && _tq?.difficulty_level) {
      const _lv = _tq.difficulty_level
      if (lastQuizLevel.value && _lv > lastQuizLevel.value) {
        bumpTip.value = `★${lastQuizLevel.value} → ★${_lv} · 已根据掌握情况动态调整难度`
        setTimeout(() => { bumpTip.value = '' }, 2600)
      }
      lastQuizLevel.value = _lv
    }
    loadState() // 对话可能改变掌握度/记忆，刷新
  } catch (e: any) {
    const apiErr = e?._apiError || classifyError(e)
    if (apiErr.type === ApiErrorType.TIMEOUT) {
      messages.value.push({ role: 'assistant', content: '⏳ 请求超时 — AI 正在处理你的需求但耗时较长（生成训练材料需要多轮 LLM 审查），请稍后重试或简化需求。' })
    } else if (apiErr.type === ApiErrorType.NETWORK) {
      messages.value.push({ role: 'assistant', content: '🔌 后端服务未连接 — 请确认已通过 start-dev.bat 启动服务，或检查 http://127.0.0.1:18000 是否可访问。' })
    } else if (apiErr.type === ApiErrorType.TASK_LOST) {
      messages.value.push({ role: 'assistant', content: `⚠️ 刚才那条请求被后端重启打断了（后端若用 --reload 热重载，重启会清空正在执行的任务）。请把「${content}」再发一次；若频繁出现，建议关闭后端热重载后重启服务。` })
    } else if (apiErr.type === ApiErrorType.SERVER_ERROR) {
      const detail = e?.response?.data?.detail || apiErr.message
      messages.value.push({ role: 'assistant', content: `⚠️ 服务器内部错误 (${apiErr.statusCode}): ${detail}。请查看后端终端日志。` })
    } else {
      messages.value.push({ role: 'assistant', content: `❌ 请求失败: ${apiErr.message}。请检查网络和后端状态。` })
    }
  } finally {
    sending.value = false
    taskPhase.value = null
    liveTrace.value = []
    // 已收到下一条 assistant 消息（成功或失败提示）→ 清除答题 pending / 本地选中态（新题到达时重置）
    quizPending.value = false
    selectedChoice.value = ''
    rubricOpen.value = false
    stopThinkingAnim()
    scrollToBottom()
  }
}

function startIdentity() {
  if (sending.value) return
  inputText.value = '开始先验学情画像'
  handleSend()
}

function sendQuick(q: string) {
  if (sending.value) return
  inputText.value = q
  handleSend()
}

// ── 附件菜单 ──
const attachItems = [
  { label: '上传图片', desc: '拍照识别景点 / 文物', icon: 'image' },
  { label: '上传 PDF', desc: '导游手册 / 培训资料', icon: 'filetext' },
  { label: '上传文件', desc: 'Word / Excel / PPT', icon: 'clip' },
  { label: '拍照识别', desc: 'AI 即时识别标识牌', icon: 'camera' },
  { label: '发送位置', desc: '共享当前带团位置', icon: 'pin' },
]

function attachAction(label: string) {
  attachOpen.value = false
  messages.value.push({ role: 'assistant', content: `「${label}」功能即将上线，敬请期待。当前版本请先直接输入文字提问。` })
  scrollToBottom()
}

// ── 用户状态 ──
const userStats = ref({ total_skills: 3796, attempted_skills: 0, mastered_skills: 0, weak_skills: 0 })
const masteryEntries = ref<{ id: string; title: string; score: number }[]>([])
const weakTitles = ref<string[]>([])
const masteryScores = ref<Record<string, number>>({})
const catalogTree = ref<SkillNode[]>([])
const planNext = ref<{ bookTitle: string; chapterTitle: string; mastery: number } | null>(null)

function syncPlanNext() {
  planNext.value = (catalogTree.value.length && Object.keys(masteryScores.value).length)
    ? nextStepFromTree(catalogTree.value, masteryScores.value)
    : null
}
const skillTitles = ref<Record<string, string>>({})
const completionRate = ref(0)

function levelLabel(score: number): string {
  if (score >= 80) return '已掌握'
  if (score >= 50) return '学习中'
  if (score > 0) return '入门'
  return '未开始'
}

const recommendText = computed(() => {
  if (planNext.value) return `建议下一步：${planNext.value.bookTitle} · ${planNext.value.chapterTitle}（先让旅鸢讲一遍，再做真题）`
  if (weakTitles.value.length) return `重点攻克薄弱知识点：${weakTitles.value[0]}`
  if (userStats.value.attempted_skills === 0) return '还没有答题记录，先来一套摸底测试吧'
  return '掌握度不错！继续巩固，挑战更高难度'
})
const recommendAction = computed(() => {
  if (planNext.value) return '去学习'
  if (weakTitles.value.length) return '去复习'
  if (userStats.value.attempted_skills === 0) return '去测试'
  return '去训练场'
})

function goRecommend() {
  if (planNext.value) router.push('/app/knowledge')
  else if (weakTitles.value.length) router.push('/app/knowledge')
  else if (userStats.value.attempted_skills === 0) router.push('/app/training')
  else router.push('/app/training')
}
function goTraining() { router.push('/app/training') }
function goKnowledge() { router.push('/app/knowledge') }

async function loadState() {
  try {
    const state = await getUserState(store.userId)
    userStats.value = state.stats || userStats.value
    weakTitles.value = state.weak_point_titles || []
    const scores = state.mastery?.knowledge_point_scores || {}
    masteryScores.value = (scores as Record<string, number>) || {}
    masteryEntries.value = Object.entries(scores)
      .map(([id, score]) => ({
        id,
        title: skillTitles.value[id] || id,
        score: Math.round((score as number) * 100),
      }))
      .sort((a, b) => b.score - a.score)
      .slice(0, 6)
    if (userStats.value.total_skills) {
      completionRate.value = Math.round((userStats.value.mastered_skills / userStats.value.total_skills) * 100)
    }
    syncPlanNext()
  } catch { /* 后端未连接 */ }
}

async function loadSkillTitles() {
  try {
    const { tree } = await getKnowledgeTree()
    const titles: Record<string, string> = {}
    const walk = (nodes: SkillNode[]) => {
      for (const n of nodes) {
        if (n.type === 'skill') titles[n.id] = n.title
        if (n.children) walk(n.children)
      }
    }
    walk(tree)
    catalogTree.value = tree || []
    skillTitles.value = titles
    syncPlanNext()
  } catch { /* ignore */ }
}

const quickQuestions = [
  '帮我制定一个导游证备考计划', '一五计划的背景和影响',
  '中国古典园林的构景手法', '突发事件应急处理流程',
  '日本游客的文化礼仪', '出几道题考考我',
]

onMounted(() => {
  store.ensureFreshSession()  // 打开应用默认新窗口对话（刷新保持；历史会话可切换）
  onb.load(store.userId)      // 首登引导状态（决定是否展示先验画像流程 / 模块锁）
  onb.loadQa(store.userId)     // 身份问答是否完成（决定对话中出题卡还是能力自评）
  loadSkillTitles()
  loadState()
  loadTeachingState()
  refreshHistory()
  handlePendingTeach()
  handlePendingSandbox()
  applyLearnQuery()
})

// 技能树「去首页学习」跳转：?learn=节点id → 输入框注入「我想学XX」
watch(() => route.query.learn, () => applyLearnQuery())

const hardFocus = ref<string | null>(null)

// ── 技能点专属会话：进入某技能点时切换到它的独立对话（首次自动开课；再进来直接接着） ──
async function loadChatSession(sid: string) {
  store.activateSession(sid)
  stopThinkingAnim()
  attachOpen.value = false
  messages.value = []
  currentTeaching.value = null
  quizPending.value = false
  selectedChoice.value = ''
  essayAnswer.value = ''
  rubricOpen.value = false
  sending.value = true
  curve.value = null
  topicMastery.value = null
  freeChatMode.value = false
  try {
    const res = await getSessionMessages(sid)
    messages.value = (res.messages || []).map((m) => ({
      role: m.role === 'assistant' ? 'assistant' : 'user',
      content: m.content,
    }))
    try {
      const state = await getTeachingState(sid, store.userId)
      if (state) currentTeaching.value = state
    } catch { /* 无教学状态 */ }
  } catch (e: any) {
    ElMessage.error('加载对话失败：' + classifyError(e).message)
  } finally {
    sending.value = false
    scrollToBottom()
  }
}

async function applyLearnQuery() {
  const learn = route.query.learn as string | undefined
  if (!learn) return
  router.replace({ query: {} })
  // 硬挂钩：知识技能点 id → 进入该技能点的专属会话，Agent 上下文锁定该技能点
  try {
    const detail = await getSkillDetail(learn)
    const sid = store.sessionForSkill(learn)
    await loadChatSession(sid)
    if (messages.value.length === 0) {
      // 首次进入该技能点 → 自动开课并出题巩固
      hardFocus.value = learn
      inputText.value = `请围绕技能点「${detail.title}」讲解，讲清楚后出题巩固`
      await nextTick()
      handleSend()
    } else {
      // 之前学过 → 恢复上次对话继续
      ElMessage.success(`已回到「${detail.title}」的对话，继续上次学习`)
    }
  } catch {
    ElMessage.warning('未找到该技能点，请稍后重试')
  }
}


/** 从后端恢复教学状态（刷新页面后教学条不丢） */
async function loadTeachingState() {
  const state = await getTeachingState(store.sessionId, store.userId)
  if (state) currentTeaching.value = state
  refreshTopicMastery()
}

/** 训练场「让旅鸢讲讲」跳转：带主题自动开课 */
function handlePendingTeach() {
  const pending = localStorage.getItem('boc_pending_teach')
  if (!pending) return
  localStorage.removeItem('boc_pending_teach')
  inputText.value = `给我讲讲${pending}`
  handleSend()
}

/** 沙盒「让旅鸢讲讲怎么提升」跳转：读评价摘要 → 自动发送复盘请求（仿 handlePendingTeach） */
async function handlePendingSandbox() {
  const raw = localStorage.getItem('boc_pending_sandbox')
  if (!raw) return
  localStorage.removeItem('boc_pending_sandbox')
  let p: {
    score?: number
    dims?: Record<string, number> | [string, number][]
    strengths?: string[]
    weaknesses?: string[]
    suggestions?: string[]
    scene_title?: string
  }
  try {
    p = JSON.parse(raw)
  } catch {
    return
  }
  if (!p || typeof p !== 'object') return
  const dimEntries = Array.isArray(p.dims)
    ? (p.dims as [string, number][])
    : Object.entries(p.dims ?? {})
  const dimText = dimEntries.map(([k, v]) => `${k} ${v}`).join('、')
  const list = (a?: string[]) => (a && a.length ? a.slice(0, 2).join('；') : '无')
  const text = [
    '请根据我刚刚的沙盒模拟表现给我讲解提升点。',
    `场景：${p.scene_title ?? '沙盒模拟'}，得分：${p.score ?? 0}/100`,
    dimText ? `五维：${dimText}` : '',
    `亮点：${list(p.strengths)}`,
    `不足：${list(p.weaknesses)}`,
    `建议：${list(p.suggestions)}`,
  ].filter(Boolean).join('\n')
  inputText.value = text
  await nextTick()
  if (taRef.value) taRef.value.focus()
  else if (dashTaRef.value) dashTaRef.value.focus()
  handleSend()
}
</script>

<style lang="scss" scoped>
@use '@/styles/tokens' as *;

.home-page { height: 100%; display: flex; flex-direction: column; overflow: hidden; }
.dash-scroll { flex: 1; min-height: 0; overflow-y: auto; }
.home-content { max-width: 720px; margin: 0 auto; padding: 24px 16px; display: flex; flex-direction: column; gap: 24px; }

.backend-offline-banner { display: flex; align-items: center; gap: 8px; padding: 10px 16px; border-radius: $radius-md; background: #fef3e2; border: 1px solid #f5d9a0; color: #a06315; font-size: 13px; }

.ai-card { border-radius: $radius-xl; overflow: hidden; background: $color-surface; border: 1px solid $color-border; box-shadow: $shadow-card-hover; }
.ai-card-header { position: relative; padding: 20px 24px 16px; background: linear-gradient(135deg, $color-primary, $color-primary-light); overflow: hidden;
  .header-ink { position: absolute; bottom: 0; right: 0; width: 66%; opacity: 0.4; }
}
.header-top { display: flex; justify-content: space-between; align-items: center; position: relative; }
.header-actions { display: flex; align-items: center; gap: 8px; }
.header-actions .ph-history { background: rgba(255,255,255,.08); border-color: rgba(255,255,255,.28); color: $color-text-on-dark;
  &:hover, &.open { border-color: $color-accent; color: $color-accent; background: rgba(51,143,242,.14); } }
.header-actions .hist-count { color: #fff; background: rgba(51,143,242,.35); }
.header-title { font-family: $font-serif; font-size: 17px; font-weight: 500; color: $color-text-on-dark; }
.new-session-btn { border-color: rgba(255,255,255,.3); color: $color-text-on-dark; background: rgba(255,255,255,.08); &:hover { border-color: $color-accent; color: $color-accent; } }
.header-sub { font-size: 12px; color: rgba(51, 143, 242, 0.8); margin-top: 4px; position: relative; }
.ai-card-body { padding: 20px 24px; }
.ai-input { width: 100%; border: none; outline: none; resize: none; font-size: 15px; font-family: $font-sans; color: $color-text; background: transparent; line-height: 1.7;
  &::placeholder { color: #aaa; }
  &:disabled { opacity: 0.5; cursor: not-allowed; }
}
.ai-toolbar { display: flex; align-items: center; justify-content: space-between; margin-top: 16px; padding-top: 16px; border-top: 1px solid $color-border;
  .toolbar-left { display: flex; gap: 4px; }
  .tool-btn { display: flex; align-items: center; gap: 4px; padding: 6px 12px; border-radius: $radius-sm; border: none; background: $color-secondary-bg; color: $color-text-secondary; font-size: 13px; cursor: pointer;
    &:hover:not(:disabled) { background: $color-muted-bg; }
    &:disabled { opacity: 0.5; cursor: not-allowed; }
  }
  .send-btn { display: flex; align-items: center; gap: 6px; padding: 10px 20px; border-radius: $radius-md; border: none; font-size: 14px; font-weight: 500; color: #FFFFFF; cursor: pointer; background: $color-accent; box-shadow: 0 2px 8px rgba(24, 58, 99, 0.25); transition: all 0.2s;
    &.active { background: linear-gradient(135deg, $color-primary, $color-primary-light); }
    &:disabled { opacity: 0.6; cursor: not-allowed; }
  }
}

.section { .section-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px; }
  .section-title { font-family: $font-serif; font-size: 16px; font-weight: 600; color: $color-primary; }
  .section-more { display: flex; align-items: center; gap: 2px; border: none; background: none; font-size: 13px; color: $color-accent; cursor: pointer; }
}
.quick-chips { display: flex; flex-wrap: wrap; gap: 8px;
  .chip { display: flex; align-items: center; gap: 8px; padding: 8px 16px; border-radius: $radius-md; border: 1px solid $color-border; background: $color-surface; color: $color-text; font-size: 14px; cursor: pointer; box-shadow: 0 1px 4px rgba(24, 58, 99, 0.05); transition: all 0.2s;
    &:hover { border-color: $color-accent; color: $color-primary; }
    .chip-dot { width: 6px; height: 6px; border-radius: 50%; background: $color-accent; flex-shrink: 0; }
  }
}

.stats-row { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; }
.stat-card { border-radius: $radius-xl; padding: 20px 12px; display: flex; flex-direction: column; align-items: center; text-align: center;
  &.dark { background: $color-primary; position: relative; overflow: hidden; }
  &.light { background: $color-surface; border: 1px solid $color-border; box-shadow: $shadow-card; }
  .stat-card-icon { font-size: 22px; margin-bottom: 6px; color: $color-accent; &.flame { color: $color-accent; } }
  .stat-card-value { font-size: 28px; font-weight: 700; color: $color-primary; .dark & { color: #FFFFFF; }
    &.ok { color: #2d8a2d; } }
  .stat-card-label { font-size: 12px; color: $color-text-secondary; margin-top: 2px; .dark & { color: rgba(51, 143, 242, 0.9); } }
  .stat-card-unit { font-size: 11px; color: $color-text-secondary; .dark & { color: rgba(255, 255, 255, 0.45); } }
}
.circular-progress { position: relative; display: inline-flex; align-items: center; justify-content: center; margin-bottom: 4px;
  .cp-svg { width: 52px; height: 52px; transform: rotate(-90deg); }
  .cp-text { position: absolute; font-size: 12px; font-weight: 700; color: $color-primary; }
}

.task-list { display: flex; flex-direction: column; gap: 8px; }
.task-item { display: flex; align-items: center; gap: 16px; padding: 16px 20px; border-radius: $radius-lg; background: $color-surface; border: 1px solid $color-border; box-shadow: $shadow-card; cursor: pointer; transition: box-shadow 0.2s;
  &:hover { box-shadow: $shadow-card-hover; }
}
.task-status { width: 40px; height: 40px; border-radius: $radius-md; display: flex; align-items: center; justify-content: center; flex-shrink: 0; background: $color-secondary-bg; color: $color-primary;
  &.started { background: rgba(24, 58, 99, 0.08); }
  &.done { background: $color-accent-light; color: $color-accent; }
}
.task-info { flex: 1; min-width: 0; }
.task-title-row { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; }
.task-title { font-size: 14px; font-weight: 500; color: $color-text; }
.task-category { font-size: 11px; padding: 2px 8px; border-radius: 999px; background: $color-secondary-bg; color: $color-text-secondary; }
.task-progress-bar { display: flex; align-items: center; gap: 8px; }
.progress-track { flex: 1; height: 6px; border-radius: 3px; background: $color-muted-bg; overflow: hidden; }
.progress-fill { height: 100%; border-radius: 3px; background: $color-accent; transition: width 0.3s; }
.progress-pct { font-size: 12px; color: $color-text-secondary; flex-shrink: 0; }
.task-action { text-align: right; flex-shrink: 0; }
.task-go { display: inline-flex; align-items: center; gap: 2px; border: none; background: none; font-size: 13px; font-weight: 500; color: $color-primary; cursor: pointer; }

.recommend-bar { position: relative; display: flex; align-items: center; justify-content: space-between; padding: 20px 24px; border-radius: $radius-xl; background: linear-gradient(135deg, $color-primary-d3, $color-primary, $color-primary-d10); overflow: hidden;
  .rec-ink { position: absolute; bottom: 0; right: 0; width: 50%; opacity: 0.5; }
}
.rec-info { position: relative; display: flex; flex-direction: column; gap: 4px; }
.rec-tag { font-size: 12px; font-weight: 500; color: rgba(51, 143, 242, 0.9); }
.rec-title { font-family: $font-serif; font-size: 15px; font-weight: 600; color: #FFFFFF; }
.rec-desc { font-size: 12px; color: rgba(255, 255, 255, 0.55); }
.rec-btn { position: relative; display: flex; align-items: center; gap: 4px; padding: 10px 20px; border-radius: $radius-md; border: none; background: $color-accent; color: #FFFFFF; font-size: 14px; font-weight: 500; cursor: pointer; flex-shrink: 0; }

/* ══════════════ 纯对话页 ══════════════ */

// ── 页头 ──
.ph {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 28px 12px;
  flex-shrink: 0;
}
.ph-title {
  font-family: $font-serif;
  font-size: 20px;
  font-weight: 700;
  color: $color-primary;
}
.ph-right { display: flex; align-items: center; gap: 10px; }

// ── 历史对话列表（切换会话，仪表盘与对话页共用） ──
.history-wrap { position: relative; }
.history-wrap.dash .ph-history { border-color: rgba(24, 58, 99, 0.22); }
.ph-history {
  display: inline-flex; align-items: center; gap: 5px; font-size: 12px; font-family: $font-sans;
  padding: 5px 14px; border-radius: 20px; border: 1px solid rgba(24, 58, 99, 0.18);
  background: rgba(255, 255, 255, 0.7); color: $color-text-secondary; cursor: pointer; transition: all 0.15s;
  &:hover, &.open { border-color: $color-accent; color: $color-primary; background: rgba(51, 143, 242, 0.08); }
  .hist-count { font-size: 10px; font-weight: 700; color: #256CA7; background: rgba(51, 143, 242, 0.2);
    padding: 0 6px; border-radius: 999px; }
}
.history-mask { position: fixed; inset: 0; z-index: 49; background: rgba(15, 39, 69, 0.18); }
.history-panel {
  position: fixed; left: 50%; top: 74px; transform: translateX(-50%); z-index: 50; width: 360px; max-height: 420px;
  display: flex; flex-direction: column; background: #fff; border: 1px solid $color-border;
  border-radius: 14px; box-shadow: 0 10px 34px rgba(24, 58, 99, 0.16); overflow: hidden;
  .hist-head { display: flex; align-items: center; justify-content: space-between; padding: 10px 14px;
    font-size: 12px; font-weight: 700; color: $color-primary; border-bottom: 1px solid $color-border; }
  .hist-close { border: none; background: none; color: $color-text-secondary; cursor: pointer; padding: 2px; }
  .hist-body { overflow-y: auto; padding: 6px; flex: 1; }
  .hist-empty { padding: 26px 12px; text-align: center; font-size: 12.5px; color: $color-text-secondary; }
  .hist-item { display: flex; flex-direction: column; gap: 3px; width: 100%; text-align: left; padding: 9px 12px;
    border: none; background: none; border-radius: 10px; cursor: pointer; transition: background 0.12s;
    &:hover { background: rgba(24, 58, 99, 0.05); }
    &.active { background: rgba(51, 143, 242, 0.14); }
    .hist-t { font-size: 13px; font-weight: 600; color: $color-text; white-space: nowrap;
      overflow: hidden; text-overflow: ellipsis; }
    .hist-meta { font-size: 11px; color: $color-text-secondary; }
  }
  .hist-foot { padding: 8px 12px; border-top: 1px solid $color-border; }
  .hist-new { width: 100%; padding: 7px 0; border-radius: 10px; border: 1px dashed rgba(51, 143, 242, 0.5);
    background: rgba(51, 143, 242, 0.06); color: #256CA7; font-size: 12px; font-weight: 600; cursor: pointer;
    &:hover { background: rgba(51, 143, 242, 0.14); } }
}

.ph-new {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-size: 12px;
  font-family: $font-sans;
  padding: 5px 14px;
  border-radius: 20px;
  border: 1px solid rgba(24, 58, 99, 0.18);
  background: #fff;
  color: $color-primary;
  cursor: pointer;
  transition: all 0.15s;

  &:hover {
    border-color: $color-accent;
    color: $color-accent;
    background: rgba(51, 143, 242, 0.06);
  }
}
.pill {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  padding: 5px 14px;
  border-radius: 20px;
  background: rgba(51, 143, 242, 0.12);
  color: #256CA7;
  border: 1px solid rgba(51, 143, 242, 0.3);

  &.offline {
    background: rgba(107, 114, 128, 0.08);
    color: $color-text-secondary;
    border-color: rgba(107, 114, 128, 0.2);
  }
}
.conn-dot {
  width: 7px; height: 7px; border-radius: 50%;
  background: #9CA3AF;
  &.on { background: #34D399; box-shadow: 0 0 5px rgba(52, 211, 153, 0.6); }
}

// ── 主体 ──
.hp-page {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background: $color-bg;
}
.hp-body {
  flex: 1;
  min-height: 0;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}
.hp-inner {
  width: min(760px, 100%);
  margin: 0 auto;
  padding: 8px 24px 24px;
  display: flex;
  flex-direction: column;
  flex: 1;
  min-height: 0;
}

// ── 对话流 ──
.hp-chat {
  display: flex;
  flex-direction: column;
  gap: 14px;
  padding: 12px 0 8px;
  flex: 1;
  min-height: 0;
  overflow-y: auto;
}
.chat-row {
  display: flex;
  gap: 10px;
  align-items: flex-start;

  &.user { justify-content: flex-end; }
}
.chat-av {
  width: 34px; height: 34px;
  border-radius: 50%;
  background: #338FF2;
  display: flex; align-items: center; justify-content: center;
  flex-shrink: 0;

  img { width: 25px; height: 24px; display: block; }
}
.chat-main {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 8px;
  max-width: 78%;
  min-width: 0;

  .chat-row.user & { align-items: flex-end; }
}
.chat-bubble {
  max-width: 100%;
  padding: 11px 15px;
  border-radius: 14px;
  font-size: 13.5px;
  line-height: 1.75;
  color: $color-text;
  white-space: normal;
  word-break: break-word;

  .user & {
    background: $color-primary;
    color: #fff;
    border-bottom-right-radius: 4px;
  }
  .assistant & {
    background: #fff;
    border: 1px solid $color-border;
    border-bottom-left-radius: 4px;
  }
}

// 思考动画
.chat-bubble.thinking {
  display: flex;
  align-items: center;
  gap: 8px;

  .tdot {
    width: 6px; height: 6px;
    border-radius: 50%;
    background: $color-accent;
    animation: tdot 1.2s ease infinite;
    &:nth-child(2) { animation-delay: 0.2s; }
    &:nth-child(3) { animation-delay: 0.4s; }
  }
  .t-text { font-size: 12px; color: $color-text-secondary; margin-left: 4px; }
}
@keyframes tdot {
  0%, 100% { opacity: 0.25; transform: translateY(0); }
  50% { opacity: 1; transform: translateY(-3px); }
}

// ── 多智能体协同时间轴 ──
.chat-msg-chain {
  width: 100%;
  padding: 10px 14px 4px;
  border-radius: $radius-md;
  background: rgba(255, 255, 255, 0.6);
  border: 1px dashed $color-border;

  .cc-header {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 6px;

    .cc-label { font-size: 11px; font-weight: 600; letter-spacing: 0.5px; color: $color-primary; flex-shrink: 0; }
    .cc-badge {
      display: inline-flex;
      align-items: center;
      gap: 3px;
      font-size: 11px;
      font-weight: 500;
      padding: 2px 8px;
      border-radius: 999px;

      &.pass { background: rgba(45, 138, 45, 0.1); color: #2d8a2d; border: 1px solid rgba(45, 138, 45, 0.25); }
      &.revised { background: rgba(51, 143, 242, 0.18); color: #256CA7; border: 1px solid rgba(51, 143, 242, 0.4); }
    }
    .cc-verdict {
      font-size: 11px;
      padding: 2px 8px;
      border-radius: 999px;
      background: $color-secondary-bg;
      color: $color-text-secondary;
      max-width: 180px;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
    .cc-toggle {
      margin-left: auto;
      display: inline-flex;
      align-items: center;
      gap: 3px;
      padding: 2px 8px;
      border: none;
      border-radius: 999px;
      background: none;
      font-size: 11px;
      color: $color-text-secondary;
      cursor: pointer;
      flex-shrink: 0;
      transition: all 0.15s;

      &:hover { color: $color-accent; background: $color-accent-light; }
    }
  }

  .cc-timeline { display: flex; flex-direction: column; }

  .cc-node {
    display: flex;
    gap: 10px;

    &:last-child .cc-node-body { padding-bottom: 6px; }
  }
  .cc-node-marker {
    display: flex;
    flex-direction: column;
    align-items: center;
    flex-shrink: 0;
  }
  .cc-node-dot {
    width: 20px;
    height: 20px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 11px;
    font-weight: 600;
    background: $color-primary;
    color: #fff;
    flex-shrink: 0;

    &.current {
      background: $color-accent;
      box-shadow: 0 0 0 3px $color-accent-light;
    }
  }
  .cc-node-stem {
    flex: 1;
    width: 2px;
    min-height: 16px;
    margin: 3px 0;
    background: $color-border-d10;
    opacity: 0.65;
  }
  .cc-node-body {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 8px;
    padding-bottom: 12px;

    .cc-step {
      display: inline-flex;
      align-items: center;
      gap: 5px;
      font-size: 12px;
      padding: 3px 12px;
      border-radius: 999px;
      background: $color-primary;
      color: #fff;
    }
    .cc-step-label { font-size: 11px; color: $color-text-secondary; }
  }
}

// ── 多 Agent 实时协同直播面板（思考动画的升级版） ──
.ma-panel {
  width: 100%;
  max-width: 560px;
  padding: 10px 12px;
  border-radius: $radius-md;
  background: #fff;
  border: 1px solid $color-border;
  box-shadow: $shadow-card;

  .ma-head {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 8px;

    .ma-title {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      font-size: 12px;
      font-weight: 600;
      letter-spacing: 0.5px;
      color: $color-primary;

      .ma-live-dot {
        width: 7px; height: 7px;
        border-radius: 50%;
        background: $color-accent;
        box-shadow: 0 0 0 0 rgba(51, 143, 242, 0.5);
        animation: maPing 1.6s ease-out infinite;
      }
    }
    .ma-badge.live {
      font-size: 10px;
      font-weight: 500;
      padding: 1px 7px;
      border-radius: 999px;
      color: #fff;
      background: $color-accent;
    }
    .ma-count {
      margin-left: auto;
      font-size: 11px;
      color: $color-text-secondary;

      b { color: $color-primary; font-weight: 600; }
    }
  }

  // B档轻量拓扑：已参与的角色节点按顺序点亮
  .ma-topo {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 4px 2px;
    padding: 7px 9px;
    margin-bottom: 8px;
    border-radius: $radius-sm;
    background: $color-secondary-bg;

    .ma-actor {
      position: relative;
      display: inline-flex;
      align-items: center;
      gap: 4px;
      padding: 3px 8px;
      border-radius: 999px;
      border: 1px solid $color-border;
      background: #fff;
      color: $color-text-secondary;
      font-size: 11px;
      transition: all 0.2s;

      .ma-actor-ico { display: inline-flex; color: $color-text-secondary; }

      &.busy {
        border-color: $color-accent;
        color: $color-primary;
        background: #F8FBFF;
        box-shadow: 0 0 0 2px rgba(51, 143, 242, 0.18);

        .ma-actor-ico { color: $color-accent; }
      }
      &.done {
        border-color: $color-primary;
        background: $color-primary;
        color: #fff;

        .ma-actor-ico { color: #fff; }
        .ma-actor-ok {
          position: absolute;
          top: -4px; right: -4px;
          width: 11px; height: 11px;
          border-radius: 50%;
          background: #2d8a45;
          display: flex; align-items: center; justify-content: center;
          color: #fff;
        }
      }
      .ma-actor-pulse {
        position: absolute;
        top: -3px; right: -3px;
        width: 8px; height: 8px;
        border-radius: 50%;
        background: $color-accent;
        animation: maPing 1.2s ease-out infinite;
      }
    }
    .ma-topo-arrow { color: $color-border-d10; display: inline-flex; }
  }

  // A档实时时间轨
  .ma-stream {
    display: flex;
    flex-direction: column;
    max-height: 168px;
    overflow-y: auto;

    .ma-item {
      display: flex;
      align-items: center;
      gap: 6px;
      padding: 4px 6px;
      border-radius: 6px;
      font-size: 11.5px;
      line-height: 1.4;

      .ma-item-ico {
        display: inline-flex;
        flex-shrink: 0;
        color: $color-primary;
        opacity: 0.75;
      }
      .ma-item-name { font-weight: 600; color: $color-text; flex-shrink: 0; }
      .ma-item-role { color: $color-text-secondary; flex-shrink: 0; }
      .ma-item-detail {
        color: $color-text-secondary;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
        max-width: 170px;
      }
      .ma-item-st { margin-left: auto; display: inline-flex; flex-shrink: 0; color: #2d8a45; }
      .ma-item-wait {
        display: inline-flex;
        gap: 2px;
        align-items: center;
        i {
          width: 3px; height: 3px;
          border-radius: 50%;
          background: $color-accent;
          animation: tdot 1.2s ease infinite;
          &:nth-child(2) { animation-delay: 0.2s; }
          &:nth-child(3) { animation-delay: 0.4s; }
        }
      }

      // 帽子色调：通过 agent 类名识别
      &.white_hat .ma-item-ico { color: #7a8794; }
      &.black_hat .ma-item-ico { color: #333b47; }
      &.green_hat .ma-item-ico { color: #2d8a45; }
      &.yellow_hat .ma-item-ico { color: #b8953a; }
      &.red_hat .ma-item-ico { color: #c0504d; }
      &.blue_hat .ma-item-ico { color: #3468c9; }
      &.concierge .ma-item-ico { color: $color-accent; opacity: 1; }

      &.working {
        background: rgba(51, 143, 242, 0.08);
      }
      &.failed .ma-item-st { color: #c0504d; }
    }
  }
}
@keyframes maPing {
  0% { box-shadow: 0 0 0 0 rgba(51, 143, 242, 0.45); }
  70% { box-shadow: 0 0 0 6px rgba(51, 143, 242, 0); }
  100% { box-shadow: 0 0 0 0 rgba(51, 143, 242, 0); }
}

// ── 多 Agent 实时协同直播面板 v2：转圈 + 加宽 + 每 Agent 一行可展开 ──
.chat-main.ma-wide {
  width: min(680px, 96%);
  max-width: min(680px, 96%);
}
.ma-spin {
  display: inline-block;
  width: 15px; height: 15px;
  border-radius: 50%;
  border: 2px solid rgba(51, 143, 242, 0.3);
  border-top-color: $color-accent;
  animation: maSpin 0.7s linear infinite;
  flex-shrink: 0;
  &.sm { width: 11px; height: 11px; border-width: 2px; }
}
.think-spin {
  display: inline-block;
  width: 15px; height: 15px;
  border-radius: 50%;
  border: 2px solid rgba(51, 143, 242, 0.3);
  border-top-color: $color-accent;
  animation: maSpin 0.7s linear infinite;
}
@keyframes maSpin { to { transform: rotate(360deg); } }
@keyframes maPing {
  0% { box-shadow: 0 0 0 0 rgba(51, 143, 242, 0.45); }
  70% { box-shadow: 0 0 0 6px rgba(51, 143, 242, 0); }
  100% { box-shadow: 0 0 0 0 rgba(51, 143, 242, 0); }
}

.ma-panel {
  width: 100%;
  min-width: 0;
  border-radius: 14px;
  background: #fff;
  border: 1px solid $color-border;
  box-shadow: $shadow-card-hover;
  overflow: hidden;

  .ma-head {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 11px 14px;
    background: linear-gradient(120deg, $color-primary, $color-primary-light);

    .ma-title {
      display: inline-flex;
      align-items: center;
      gap: 7px;
      font-size: 13.5px;
      font-weight: 700;
      letter-spacing: 1px;
      color: #fff;
      .ma-live-dot {
        width: 8px; height: 8px;
        border-radius: 50%;
        background: $color-accent;
        animation: maPing 1.6s ease-out infinite;
      }
    }
    .ma-badge.live {
      font-size: 10.5px;
      font-weight: 600;
      letter-spacing: 1px;
      padding: 2px 9px;
      border-radius: 999px;
      color: #fff;
      background: $color-accent;
    }
    .ma-count {
      font-size: 12px;
      color: rgba(255, 255, 255, 0.85);
      b { color: #fff; font-weight: 700; }
    }
    .ma-fold {
      margin-left: auto;
      display: inline-flex;
      align-items: center;
      gap: 5px;
      font-size: 12px;
      color: #fff;
      background: rgba(255, 255, 255, 0.14);
      border: 1px solid rgba(255, 255, 255, 0.28);
      padding: 3px 10px;
      border-radius: 999px;
      cursor: pointer;
      transition: all 0.15s;
      &:hover { background: rgba(255, 255, 255, 0.26); }
    }
  }

  .ma-topo {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 5px 3px;
    padding: 9px 12px;
    border-bottom: 1px solid $color-border;
    background: $color-secondary-bg;

    .ma-actor {
      position: relative;
      display: inline-flex;
      align-items: center;
      gap: 5px;
      padding: 4px 11px;
      border-radius: 999px;
      border: 1px solid $color-border;
      background: #fff;
      color: $color-text-secondary;
      font-size: 12px;
      font-weight: 500;
      transition: all 0.2s;

      .ma-actor-ico { display: inline-flex; color: $color-text-secondary; }
      &.busy {
        border-color: $color-accent;
        color: $color-primary;
        background: #F8FBFF;
        box-shadow: 0 0 0 2px rgba(51, 143, 242, 0.18);
        .ma-actor-ico { color: $color-accent; }
      }
      &.done {
        border-color: $color-primary;
        background: $color-primary;
        color: #fff;
        .ma-actor-ico { color: #fff; }
        .ma-actor-ok {
          position: absolute;
          top: -4px; right: -4px;
          width: 13px; height: 13px;
          border-radius: 50%;
          background: #2d8a45;
          display: flex; align-items: center; justify-content: center;
          color: #fff;
        }
      }
      &.fail { border-color: rgba(192, 80, 77, 0.6); color: #c0504d; }
      .ma-actor-spin {
        position: absolute;
        top: -3px; right: -3px;
        span {
          display: block;
          width: 9px; height: 9px;
          border-radius: 50%;
          border: 1.5px solid rgba(51, 143, 242, 0.35);
          border-top-color: $color-accent;
          animation: maSpin 0.7s linear infinite;
        }
      }
    }
    .ma-topo-arrow { color: $color-border-d10; display: inline-flex; }
  }

  .ma-stream {
    display: flex;
    flex-direction: column;
    max-height: 330px;
    overflow-y: auto;
    padding: 6px 8px;
  }

  .ma-agent {
    border-bottom: 1px solid $color-border;
    &:last-child { border-bottom: none; }

    .ma-agent-row {
      width: 100%;
      display: flex;
      align-items: center;
      gap: 10px;
      padding: 9px 8px;
      border: none;
      background: none;
      text-align: left;
      cursor: pointer;
      border-radius: 8px;
      transition: background 0.15s;
      &:hover { background: $color-accent-light; }
    }
    .ma-agent-chev { color: $color-text-secondary; flex-shrink: 0; }
    .ma-agent-ico {
      width: 32px; height: 32px;
      border-radius: 10px;
      display: flex; align-items: center; justify-content: center;
      background: $color-primary;
      color: #fff;
      flex-shrink: 0;
    }
    .ma-agent-txt {
      display: flex;
      flex-direction: column;
      gap: 2px;
      min-width: 0;
      .ma-agent-name { font-size: 13.5px; font-weight: 700; color: $color-text; }
      .ma-agent-role {
        font-size: 12px;
        color: $color-text-secondary;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
        i { font-style: normal; color: $color-accent-d10; font-weight: 600; }
      }
    }
    .ma-agent-st { margin-left: auto; display: inline-flex; flex-shrink: 0; }
    .ma-ok { display: inline-flex; color: #2d8a45; }
    .ma-ng { display: inline-flex; color: #c0504d; }

    &.white_hat .ma-agent-ico { background: #7a8794; }
    &.black_hat .ma-agent-ico { background: #333b47; }
    &.green_hat .ma-agent-ico { background: #2d8a45; }
    &.yellow_hat .ma-agent-ico { background: #b8953a; }
    &.red_hat .ma-agent-ico { background: #c0504d; }
    &.blue_hat .ma-agent-ico { background: #3468c9; }
    &.retrieval .ma-agent-ico { background: $color-primary-light; }
    &.draft .ma-agent-ico { background: #7d5ba6; }
    &.trainer .ma-agent-ico { background: #2d8a45; }
    &.essay .ma-agent-ico { background: #b07b3a; }
    &.analyzer .ma-agent-ico { background: #3468c9; }
    &.planner .ma-agent-ico { background: #256CA7; }
    &.profile .ma-agent-ico { background: #5a7a8f; }

    &.busy .ma-agent-row { background: rgba(51, 143, 242, 0.07); }
    &.fail .ma-agent-role { color: #c0504d; }

    .ma-agent-body {
      padding: 2px 8px 9px 50px;
      display: flex;
      flex-direction: column;
      gap: 5px;
    }
    .ma-ev {
      display: flex;
      flex-direction: column;
      gap: 5px;
      padding: 7px 10px;
      border-radius: 8px;
      background: $color-secondary-bg;
      border: 1px solid transparent;

      &.working { border-color: rgba(51, 143, 242, 0.5); background: #F8FBFF; }
      &.failed { border-color: rgba(192, 80, 77, 0.35); }

      .ma-ev-bar {
        display: flex;
        align-items: center;
        gap: 8px;
        min-width: 0;
        .ma-ev-idx {
          width: 17px; height: 17px;
          border-radius: 50%;
          background: $color-border-d10;
          color: #fff;
          font-size: 10px;
          font-weight: 700;
          display: inline-flex; align-items: center; justify-content: center;
          flex-shrink: 0;
        }
        .ma-ev-role {
          font-size: 12.5px;
          font-weight: 600;
          color: $color-text;
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
        }
        .ma-ev-st { margin-left: auto; display: inline-flex; flex-shrink: 0; color: #2d8a45; }
      }
      &.failed .ma-ev-st { color: #c0504d; }

      .ma-think {
        align-self: flex-start;
        display: inline-flex;
        align-items: center;
        gap: 4px;
        font-size: 11.5px;
        color: $color-primary;
        background: $color-accent-light;
        border: none;
        padding: 2px 9px;
        border-radius: 999px;
        cursor: pointer;
        transition: all 0.15s;
        &:hover { background: rgba(51, 143, 242, 0.28); }
      }
      .ma-note {
        font-size: 12px;
        line-height: 1.75;
        color: $color-text-secondary;
        background: #fff;
        border: 1px dashed $color-border-d10;
        border-radius: 8px;
        padding: 8px 10px;
        white-space: pre-wrap;
        word-break: break-word;
        max-height: 140px;
        overflow-y: auto;
      }
    }
  }
}

// ── 资产卡片 ──
.chat-msg-assets {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  border-radius: $radius-md;
  background: $color-surface;
  border: 1px solid $color-border;

  .ca-text { font-size: 12px; color: $color-text-secondary; }
}

.onb-start { display: flex; align-items: center; gap: 14px; padding: 16px 18px; border-radius: 14px; background: linear-gradient(120deg, $color-primary, $color-primary-light); color: #fff;
  .os-ic { width: 42px; height: 42px; border-radius: 50%; background: rgba(255,255,255,.15); display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
  .os-main { flex: 1; .os-t { font-size: 15px; font-weight: 800; } .os-d { font-size: 12px; color: rgba(255,255,255,.75); margin-top: 3px; } }
  .os-btn { background: $color-accent; color: #fff; border: none; border-radius: 999px; padding: 9px 18px; font-size: 13px; cursor: pointer; display: inline-flex; align-items: center; gap: 6px; flex-shrink: 0; } }
.onb-in-chat { margin: 12px 0; }

// ── 教学状态条（一对一教学闭环） ──
.teach-bar {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  width: min(760px, calc(100% - 48px));
  margin: 0 auto 10px;
  padding: 8px 16px;
  border-radius: 999px;
  background: linear-gradient(135deg, rgba(24, 58, 99, 0.06), rgba(51, 143, 242, 0.1));
  border: 1px solid rgba(24, 58, 99, 0.14);
  font-size: 12.5px;
  flex-shrink: 0;

  .tb-label { font-weight: 700; color: $color-primary; letter-spacing: 0.5px; }
  .tb-topic { font-weight: 600; color: $color-text; }
  .tb-stage { color: $color-accent; background: rgba(51, 143, 242, 0.16); padding: 2px 10px; border-radius: 999px; }
  .tb-depth { color: $color-primary; background: rgba(24, 58, 99, 0.08); padding: 2px 10px; border-radius: 999px; }
  .tb-count { color: $color-text-secondary; margin-left: auto; }
}

// ── 教学反馈徽标 ──
.chat-msg-teach-badge {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 11px;
  font-weight: 500;
  padding: 3px 10px;
  border-radius: 999px;
  background: rgba(45, 138, 45, 0.08);
  color: #2d8a2d;
  border: 1px solid rgba(45, 138, 45, 0.25);

  &.reteach {
    background: rgba(201, 138, 44, 0.12);
    color: #9a6b1f;
    border-color: rgba(201, 138, 44, 0.35);
  }
}

// ── 做题卡片（练习阶段：选择题窗口 / 简答题窗口，仿 DSH「让用户选择的窗口」） ──
.quiz-card {
  width: 100%;
  border-radius: 14px;
  border: 1px solid rgba(24, 58, 99, 0.18);
  background: #fff;
  box-shadow: 0 2px 12px rgba(24, 58, 99, 0.08);
  overflow: hidden;

  .quiz-card-head {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 8px;
    padding: 9px 14px;
    border-bottom: 1px solid rgba(24, 58, 99, 0.08);
    background: linear-gradient(135deg, rgba(24, 58, 99, 0.05), rgba(51, 143, 242, 0.1));

.quiz-diff { display: inline-flex; align-items: center; gap: 1px; margin-left: 8px; }
.qstar { color: #B8D8F5; font-size: 13px; line-height: 1; }
.qstar.on { color: #338FF2; }

    .quiz-type-badge {
      font-size: 11px;
      font-weight: 600;
      padding: 2px 10px;
      border-radius: 999px;
      flex-shrink: 0;

      &.choice { background: rgba(24, 58, 99, 0.1); color: $color-primary; border: 1px solid rgba(24, 58, 99, 0.22); }
      &.essay { background: rgba(51, 143, 242, 0.18); color: #256CA7; border: 1px solid rgba(51, 143, 242, 0.42); }
    }
    .quiz-kp-title {
      font-size: 12.5px;
      font-weight: 600;
      color: $color-text;
      min-width: 0;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
    .quiz-progress-badge {
      margin-left: auto;
      font-size: 11px;
      font-weight: 500;
      padding: 2px 10px;
      border-radius: 999px;
      background: rgba(24, 58, 99, 0.06);
      color: $color-text-secondary;
      border: 1px solid rgba(24, 58, 99, 0.12);
      flex-shrink: 0;

      &.done { background: rgba(45, 138, 45, 0.1); color: #2d8a2d; border-color: rgba(45, 138, 45, 0.25); }
    }
  }

  // 选择题窗口
  .quiz-choice-body {
    padding: 14px;
    display: flex;
    flex-direction: column;
    gap: 12px;

    .quiz-prompt { margin: 0; font-size: 14px; line-height: 1.7; color: $color-text; }
  }
  .quiz-options {
    display: flex;
    flex-direction: column;
    gap: 8px;

    .quiz-opt {
      display: flex;
      align-items: center;
      gap: 10px;
      width: 100%;
      padding: 10px 14px;
      border-radius: 12px;
      border: 1px solid rgba(24, 58, 99, 0.18);
      background: #fff;
      color: $color-text;
      font-size: 13.5px;
      text-align: left;
      cursor: pointer;
      transition: all 0.15s;

      .opt-letter {
        width: 24px; height: 24px;
        border-radius: 8px;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        font-size: 12px;
        font-weight: 700;
        background: rgba(24, 58, 99, 0.08);
        color: $color-primary;
        flex-shrink: 0;
        transition: all 0.15s;
      }
      .opt-text { flex: 1; min-width: 0; }

      &:hover:not(:disabled) {
        border-color: $color-accent;
        background: rgba(51, 143, 242, 0.08);
        transform: translateY(-1px);
        box-shadow: 0 2px 8px rgba(24, 58, 99, 0.08);
      }
      &:disabled { opacity: 0.55; cursor: not-allowed; }

      // 本地选中 → 金色填充
      &.selected {
        border-color: $color-accent;
        background: linear-gradient(135deg, #338FF2, #277CCF);
        color: #fff;
        box-shadow: 0 2px 10px rgba(51, 143, 242, 0.45);

        .opt-letter { background: rgba(255, 255, 255, 0.25); color: #fff; }
      }
    }
  }

  // 简答题窗口
  .quiz-essay-body {
    padding: 14px;
    display: flex;
    flex-direction: column;
    gap: 10px;

    .quiz-prompt.essay { margin: 0; font-size: 15px; font-weight: 500; line-height: 1.7; color: $color-text; }
    .quiz-rubric-toggle {
      align-self: flex-start;
      border: none;
      background: none;
      padding: 0;
      font-size: 11px;
      color: $color-text-secondary;
      cursor: pointer;
      transition: color 0.15s;

      &:hover { color: $color-accent; }
    }
    .quiz-rubric {
      margin: 0;
      font-size: 12px;
      line-height: 1.7;
      color: $color-text-secondary;
      background: rgba(51, 143, 242, 0.08);
      border: 1px dashed rgba(51, 143, 242, 0.4);
      border-radius: 10px;
      padding: 8px 12px;
    }
    .quiz-essay-input-row {
      display: flex;
      gap: 8px;
      align-items: flex-end;

      .quiz-essay-input {
        flex: 1;
        border: 1px solid $color-border;
        border-radius: 10px;
        padding: 8px 12px;
        font-size: 13px;
        font-family: $font-sans;
        line-height: 1.6;
        color: $color-text;
        resize: none;
        background: #fff;
        outline: none;
        transition: border-color 0.15s;

        &:focus { border-color: $color-accent; }
        &:disabled { opacity: 0.55; cursor: not-allowed; }
      }
      .quiz-essay-submit {
        flex-shrink: 0;
        padding: 8px 18px;
        border-radius: 10px;
        border: none;
        background: linear-gradient(135deg, $color-primary, $color-primary-light);
        color: #fff;
        font-size: 13px;
        font-weight: 500;
        cursor: pointer;
        transition: all 0.15s;

        &:hover:not(:disabled) { transform: translateY(-1px); box-shadow: 0 4px 12px rgba(24, 58, 99, 0.3); }
        &:disabled { opacity: 0.55; cursor: not-allowed; }
      }
    }
  }
}

// ── 快捷 chips ──
.hp-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  justify-content: center;
  padding: 14px 0 2px;
  flex-shrink: 0;

  .chip {
    font-size: 12px;
    padding: 7px 15px;
    border-radius: 20px;
    border: 1px solid rgba(24, 58, 99, 0.15);
    background: rgba(255, 255, 255, 0.85);
    color: $color-primary;
    cursor: pointer;
    transition: all 0.15s;
    font-family: $font-sans;

    &:hover:not(:disabled) {
      border-color: $color-accent;
      background: rgba(51, 143, 242, 0.1);
      transform: translateY(-1px);
    }
    &:disabled { opacity: 0.5; cursor: not-allowed; }
  }
}

// ── 任务阶段提示条 ──
.task-phase-bar {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  width: fit-content;
  max-width: 100%;
  margin: 0 auto 8px;
  padding: 7px 18px;
  border-radius: 999px;
  background: rgba(24, 58, 99, 0.06);
  border: 1px solid rgba(24, 58, 99, 0.12);
  color: $color-primary;
  font-size: 12.5px;
  flex-shrink: 0;

  .tpb-dots { display: inline-flex; gap: 4px; }
  .tpb-dot {
    width: 5px;
    height: 5px;
    border-radius: 50%;
    background: $color-accent;
    animation: tdot 1.2s ease infinite;

    &:nth-child(2) { animation-delay: 0.2s; }
    &:nth-child(3) { animation-delay: 0.4s; }
  }
  .tpb-status.fail { color: #c0392b; font-weight: 500; }
}

// ── 输入栏 ──
.hp-input { flex-shrink: 0; }
.input-box {
  border-radius: 18px;
  background: #fff;
  border: 1px solid $color-border;
  box-shadow: 0 4px 20px rgba(24, 58, 99, 0.06);
  padding: 12px 14px 10px;
  transition: border-color 0.15s;

  &:focus-within { border-color: rgba(24, 58, 99, 0.35); }
}
.input-ta {
  width: 100%;
  border: none;
  outline: none;
  resize: none;
  font-size: 13.5px;
  font-family: $font-sans;
  color: $color-text;
  line-height: 1.6;
  background: transparent;

  &::placeholder { color: #B5B0A6; }
}
.input-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 6px;

  .ia-btn {
    width: 32px; height: 32px;
    border-radius: 10px;
    border: none;
    background: transparent;
    color: $color-text-secondary;
    cursor: pointer;
    display: flex; align-items: center; justify-content: center;
    transition: all 0.15s;

    &:hover:not(:disabled) { background: rgba(24, 58, 99, 0.06); color: $color-primary; }
    &.on { background: rgba(51, 143, 242, 0.15); color: $color-accent; }
    &:disabled { opacity: 0.5; }
  }
  .ia-attach { position: relative; }
  .attach-menu {
    position: absolute;
    bottom: calc(100% + 8px);
    left: 0;
    width: 240px;
    border-radius: 14px;
    background: #fff;
    border: 1px solid $color-border;
    box-shadow: 0 12px 32px rgba(24, 58, 99, 0.14);
    padding: 6px;
    opacity: 0;
    transform: translateY(6px);
    pointer-events: none;
    transition: all 0.18s;
    z-index: 20;

    &.open { opacity: 1; transform: translateY(0); pointer-events: auto; }
  }
  .attach-item {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 9px 10px;
    border-radius: 10px;
    cursor: pointer;
    transition: background 0.12s;

    &:hover { background: rgba(51, 143, 242, 0.08); }

    .t { font-size: 12.5px; font-weight: 600; color: $color-text; }
    .d { font-size: 10.5px; color: $color-text-secondary; margin-top: 1px; }
  }
  .send-btn {
    margin-left: auto;
    width: 38px; height: 38px;
    border-radius: 12px;
    border: none;
    background: #D1E3F5;
    cursor: not-allowed;
    display: flex; align-items: center; justify-content: center;
    transition: all 0.18s;

    &.active {
      background: linear-gradient(135deg, #338FF2, #26507f);
      cursor: pointer;
      &:hover { transform: translateY(-1px); box-shadow: 0 6px 16px rgba(24, 58, 99, 0.3); }
    }
  }
}
.input-hint {
  text-align: center;
  font-size: 10.5px;
  color: #B5B0A6;
  margin-top: 8px;
}

/* ── 难度曲线 ── */
.curve-btn {
  margin-left: 10px;
  padding: 3px 10px;
  font-size: 12px;
  line-height: 1;
  color: #338FF2;
  background: #fff;
  border: 1px solid rgba(24,58,99,.25);
  border-radius: 12px;
  cursor: pointer;
  white-space: nowrap;
}
.curve-btn:hover { background: #eef4fb; }
.curve-dialog .el-dialog__body { padding-top: 8px; }
.curve-loading { text-align: center; color: #888; padding: 30px 0; }
.curve-wrap { display: flex; flex-direction: column; }
.curve-svg { width: 100%; height: auto; background: #fbfdff; border: 1px solid #e6eef7; border-radius: 10px; }
.grid-line { stroke: #e3ebf4; stroke-width: 1; }
.grid-label { font-size: 11px; fill: #90a4b8; }
.curve-line { stroke: #2f6fae; stroke-width: 2.5; stroke-linejoin: round; stroke-linecap: round; opacity:.85; }
.pt-correct { fill: #2f9e63; stroke:#fff; stroke-width:1.2; }
.pt-wrong { fill: #d9534f; stroke:#fff; stroke-width:1.2; }
.pt-current { fill: #ffb020; stroke:#338FF2; stroke-width:2; }
.cur-label { font-size: 11px; fill: #b26a00; font-weight: 600; }
.curve-legend { display:flex; gap:16px; justify-content:center; margin-top:8px; font-size:12px; color:#555; }
.curve-legend .dot { display:inline-block; width:10px; height:10px; border-radius:50%; margin-right:4px; vertical-align:-1px; }
.curve-status { margin-top: 14px; display:flex; align-items:center; justify-content:space-between; gap:12px;
  background:#f4f8fd; border:1px solid #dfe9f5; border-radius:10px; padding:10px 14px; }
.curve-status-text { font-size: 13px; color: #338FF2; line-height:1.5; }


/* ── 动态难度曲线按钮（更醒目） ── */
.curve-btn {
  margin-left: 10px;
  padding: 5px 12px;
  font-size: 12px;
  font-weight: 600;
  line-height: 1.2;
  color: #fff;
  background: linear-gradient(135deg, #2f6fae, #7a5af8);
  border: none;
  border-radius: 14px;
  cursor: pointer;
  white-space: nowrap;
  box-shadow: 0 2px 6px rgba(47,111,174,.35);
  transition: transform .12s ease, box-shadow .12s ease;
}
.curve-btn:hover { transform: translateY(-1px); box-shadow: 0 4px 10px rgba(122,90,248,.4); }

/* ── 主题完成三选卡片 ── */
.done-panel {
  margin: 0 0 10px;
  padding: 14px 16px;
  background: linear-gradient(135deg, #fff7ea, #f3f8ff);
  border: 1px solid #e9d9b8;
  border-radius: 14px;
  box-shadow: 0 4px 14px rgba(51,143,242,.18);
}
.done-title { font-size: 15px; font-weight: 700; color: #b26a00; }
.done-sub { font-size: 12px; color: #8a7a5a; margin: 4px 0 10px; }
.done-actions { display: flex; gap: 10px; flex-wrap: wrap; }
.done-btn {
  flex: 1 1 150px;
  display: inline-flex; align-items: center; justify-content: center; gap: 6px;
  padding: 9px 10px;
  font-size: 13px; color: #338FF2;
  background: #fff; border: 1px solid #d7e3f2; border-radius: 10px;
  cursor: pointer; transition: all .12s ease;
}
.done-btn:hover { border-color: #2f6fae; background: #eef5fc; transform: translateY(-1px); }
.done-btn.sandbox { color: #9a3412; border-color: #f0c6a8; }
.done-btn.sandbox:hover { background: #fff3ec; border-color: #d97b3c; }
.done-btn.chat { color: #256029; border-color: #cfe6d3; }
.done-btn.chat:hover { background: #eff9f0; border-color: #4c9a56; }
.done-emoji { font-size: 16px; }
.done-go { margin-left: auto; opacity: .7; }


/* ── 升星瞬时提示 ── */
.bump-tip {
  position: sticky;
  top: 4px;
  z-index: 20;
  margin: 0 auto 6px;
  width: fit-content;
  padding: 6px 14px;
  font-size: 13px;
  font-weight: 600;
  color: #fff;
  background: linear-gradient(135deg, #2f6fae, #7a5af8);
  border-radius: 999px;
  box-shadow: 0 4px 12px rgba(122,90,248,.4);
  animation: bump-pop .3s ease;
}
@keyframes bump-pop { from { transform: translateY(-6px); opacity: 0; } to { transform: translateY(0); opacity: 1; } }
.fade-enter-active, .fade-leave-active { transition: opacity .4s ease; }
.fade-enter-from, .fade-leave-to { opacity: 0; }


/* ── 对话顶部掌握度进度条 ── */
.tb-mastery { display:inline-flex; align-items:center; gap:6px; margin-left:10px; font-size:12px; color:#338FF2; }
.tb-mastery b { color:#7a5af8; }
.tb-mbar { display:inline-block; width:64px; height:6px; background:#e6e9f4; border-radius:3px; overflow:hidden; vertical-align:-1px; }
.tb-mbar u { display:block; height:100%; background:linear-gradient(90deg,#2f6fae,#7a5af8); border-radius:3px; }
/* ── 完成框 AI 评分 ── */
.done-mastery { display:flex; gap:18px; flex-wrap:wrap; margin:8px 0 2px; font-size:13px; color:#338FF2; }
.done-mastery b { color:#7a5af8; }


/* 顶部条图标与文字垂直对齐 */
.tb-label { display:inline-flex; align-items:center; gap:4px; }
.curve-btn { display:inline-flex; align-items:center; gap:4px; }


/* 语音输入 */
.ia-btn.on { color: #338FF2; }
.home-mic-tag { font-size: 11px; color: #256CA7; background: rgba(51,143,242,.12);
  border-radius: 10px; padding: 2px 8px; white-space: nowrap; }

</style>
