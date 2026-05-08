<script setup lang="ts">
import { computed } from "vue";
import {
  Activity,
  BrainCircuit,
  Cpu,
  LogOut,
  Network,
  ShieldCheck,
  SquareTerminal,
  type LucideIcon,
  UsersRound,
} from "lucide-vue-next";
import type { SessionUser } from "../../api/client";
import type { PageKey } from "../../composables/useHashRouting";

const props = defineProps<{
  sessionUser: SessionUser;
  activeAlarmCount: number;
  activePage?: PageKey;
}>();

const emit = defineEmits<{
  logout: [];
}>();

const roleLabel = computed(() => {
  switch (props.sessionUser.role) {
    case "community":
      return "社区值守";
    case "family":
      return "家属查看";
    case "admin":
      return "系统管理";
    default:
      return "成员账号";
  }
});

type HeaderPageMeta = {
  label: string;
  description: string;
  eyebrow: string;
  icon: LucideIcon;
};

const pageMetaMap: Record<string, HeaderPageMeta> = {
  overview: {
    label: "总览监护",
    description: "实时曲线与告警",
    eyebrow: "社区监护态势",
    icon: Activity,
  },
  topology: {
    label: "设备拓扑",
    description: "老人、家属与设备关系",
    eyebrow: "设备关系网络",
    icon: Network,
  },
  members: {
    label: "成员设备",
    description: "注册、绑定与台账",
    eyebrow: "成员设备管理",
    icon: UsersRound,
  },
  agent: {
    label: "智能体工作台",
    description: "问答、分析与工具",
    eyebrow: "社区智能体",
    icon: SquareTerminal,
  },
  finetune: {
    label: "模型微调中心",
    description: "面向健康监测、告警解释与智能问答场景的领域模型训练工作台",
    eyebrow: "模型训练工作台",
    icon: BrainCircuit,
  },
  family: {
    label: "家属视图",
    description: "家庭成员查看页面",
    eyebrow: "家属协同查看",
    icon: Cpu,
  },
};

const activePageMeta = computed<HeaderPageMeta>(() => {
  if (props.activePage && pageMetaMap[props.activePage]) {
    return pageMetaMap[props.activePage];
  }
  return {
    label: "智慧康养健康监测平台",
    description: "社区监护、拓扑、成员设备等智能体分区协作",
    eyebrow: "AIoT Care Console",
    icon: Activity,
  };
});
</script>

<template>
  <header class="modern-global-header">
    <div class="modern-global-header__brand">
      <div class="modern-global-header__icon">
        <component :is="activePageMeta.icon" :size="22" />
      </div>
      <div class="modern-global-header__text">
        <p class="modern-global-header__eyebrow">{{ activePageMeta.eyebrow }}</p>
        <h1 class="modern-global-header__title">{{ activePageMeta.label }}</h1>
        <p class="modern-global-header__description">{{ activePageMeta.description }}</p>
      </div>
    </div>

    <div class="modern-global-header__actions">
      <div class="modern-global-header__user-info">
        <span class="modern-global-header__user-name">{{ props.sessionUser.name }}</span>
        <span class="modern-global-header__user-role">
          <ShieldCheck :size="14" />
          {{ roleLabel }}
        </span>
      </div>
      
      <button type="button" class="modern-global-header__logout-btn" @click="emit('logout')">
        <LogOut :size="16" />
        <span>退出</span>
      </button>
    </div>
  </header>
</template>

<style scoped>
.modern-global-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 24px;
  padding: 16px 24px;
  background: linear-gradient(135deg, #ffffff 0%, #f8fafc 100%);
  border: 1px solid #e2e8f0;
  border-radius: 20px;
  box-shadow: 0 4px 12px rgba(15, 23, 42, 0.04);
  margin-bottom: 20px;
}

.modern-global-header__brand {
  display: flex;
  align-items: center;
  gap: 14px;
}

.modern-global-header__icon {
  width: 48px;
  height: 48px;
  border-radius: 14px;
  background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  color: #ffffff;
  font-size: 1.3rem;
  font-weight: 800;
  box-shadow: 0 4px 12px rgba(59, 130, 246, 0.3);
  flex-shrink: 0;
}

.modern-global-header__text {
  display: grid;
  gap: 2px;
}

.modern-global-header__eyebrow {
  margin: 0;
  font-size: 0.7rem;
  color: #3b82f6;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.modern-global-header__title {
  margin: 0;
  font-size: 1.15rem;
  font-weight: 800;
  color: #0f172a;
  letter-spacing: -0.02em;
  line-height: 1.2;
}

.modern-global-header__description {
  margin: 0;
  font-size: 0.84rem;
  color: #64748b;
  line-height: 1.45;
}

.modern-global-header__actions {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.modern-global-header__user-info {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 16px;
  border-radius: 12px;
  background: #ffffff;
  border: 1px solid #e2e8f0;
}

.modern-global-header__user-name {
  font-size: 0.9rem;
  font-weight: 700;
  color: #0f172a;
  white-space: nowrap;
}

.modern-global-header__user-role {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 4px 10px;
  border-radius: 8px;
  background: #eff6ff;
  color: #1e40af;
  font-size: 0.8rem;
  font-weight: 600;
  white-space: nowrap;
}

.modern-global-header__logout-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 18px;
  border: 2px solid #e2e8f0;
  border-radius: 12px;
  background: #ffffff;
  color: #64748b;
  font-size: 0.9rem;
  font-weight: 700;
  cursor: pointer;
  transition: all 200ms ease;
  white-space: nowrap;
}

.modern-global-header__logout-btn:hover {
  background: #ef4444;
  border-color: #ef4444;
  color: #ffffff;
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(239, 68, 68, 0.3);
}

@media (max-width: 1024px) {
  .modern-global-header {
    flex-direction: column;
    align-items: stretch;
  }

  .modern-global-header__actions {
    justify-content: space-between;
  }
}

@media (max-width: 640px) {
  .modern-global-header {
    padding: 14px 16px;
  }

  .modern-global-header__actions {
    flex-direction: column;
    align-items: stretch;
  }
}
</style>
