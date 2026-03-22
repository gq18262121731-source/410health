import { computed, ref } from "vue";
import { ApiError, api } from "../api/client";

export type AuthFlowStep =
  | "login"
  | "role-select"
  | "register-account"
  | "register-profile"
  | "register-complete";

export type AuthFlowRole = "elder" | "family" | "community";
export type AuthBindPlan = "now" | "later";
export type AuthLandingChoice = "overview" | "report" | "alarm";
export type AuthShiftChoice = "day" | "night" | "flex";

interface AuthCompletedCredentials {
  username: string;
  password: string;
  role: AuthFlowRole;
}

const authRoleOptions = [
  {
    key: "elder",
    badge: "老人",
    label: "老人账号",
    description: "先创建账号，再补充房间号和基础资料，用于后续设备归属和健康监测演示。",
    accountHint: "老人账号默认直接使用手机号登录，尽量降低首登理解成本。",
    profileTitle: "完善老人资料",
    profileDescription: "补充房间号和基础信息，方便后续演示设备绑定与照护关系。",
  },
  {
    key: "family",
    badge: "家属",
    label: "家属账号",
    description: "先创建账号，再补充关系与关注重点，进入系统后优先查看状态、报告和异常链路。",
    accountHint: "家属账号支持自定义登录名，也可以直接使用手机号。",
    profileTitle: "完善家属资料",
    profileDescription: "补充关系类型和首屏关注项，完成后会回到登录卡片并自动回填。",
  },
  {
    key: "community",
    badge: "社区",
    label: "社区工作人员",
    description: "创建社区值守账号，再补充分工与首屏偏好，方便现场切换到社区总览。",
    accountHint: "社区账号建议保留一个清晰的登录名，方便值守席位现场切换。",
    profileTitle: "完善值守资料",
    profileDescription: "补充值守班次与站点说明，让完成态更完整，但不伪造后端未提供的数据。",
  },
] as const satisfies ReadonlyArray<{
  key: AuthFlowRole;
  badge: string;
  label: string;
  description: string;
  accountHint: string;
  profileTitle: string;
  profileDescription: string;
}>;

const authSteps = [
  { key: "login", title: "登录", subtitle: "进入系统入口" },
  { key: "role-select", title: "身份选择", subtitle: "确认注册对象" },
  { key: "register-account", title: "注册账号", subtitle: "只创建登录账号" },
  { key: "register-profile", title: "资料完善", subtitle: "补充进入系统前的信息" },
  { key: "register-complete", title: "完成态", subtitle: "回到登录并自动回填" },
] as const satisfies ReadonlyArray<{
  key: AuthFlowStep;
  title: string;
  subtitle: string;
}>;

function formatError(error: unknown, fallback: string) {
  if (error instanceof ApiError && error.detail) {
    if (error.status === 404) {
      return "当前后端还没有开放该公共注册接口，请先确认后端服务和公开注册路由已启动。";
    }
    return error.detail;
  }
  if (error instanceof Error && error.message) return error.message;
  return fallback;
}

export function useAuthFlow() {
  const currentStep = ref<AuthFlowStep>("login");
  const selectedRole = ref<AuthFlowRole>("family");
  const showHelp = ref(false);
  const prefillNotice = ref("");
  const registrationSubmitting = ref(false);
  const registrationError = ref("");
  const registrationSuccess = ref("");
  const completedCredentials = ref<AuthCompletedCredentials | null>(null);

  const accountDraft = ref({
    name: "",
    phone: "",
    password: "123456",
    confirmPassword: "123456",
    loginUsername: "",
  });

  const profileDraft = ref({
    age: "78",
    apartment: "",
    relationship: "daughter",
    bindPlan: "later" as AuthBindPlan,
    landingChoice: "report" as AuthLandingChoice,
    shift: "day" as AuthShiftChoice,
    stationLabel: "海棠苑社区值守台",
  });

  const activeRole = computed(
    () => authRoleOptions.find((item) => item.key === selectedRole.value) ?? authRoleOptions[1],
  );

  const stepItems = computed(() =>
    authSteps.map((item) => ({
      ...item,
      active: authSteps.findIndex((step) => step.key === currentStep.value) >= authSteps.findIndex((step) => step.key === item.key),
      current: item.key === currentStep.value,
    })),
  );

  const currentLoginAccount = computed(() => {
    if (selectedRole.value === "elder") return accountDraft.value.phone.trim();
    return accountDraft.value.loginUsername.trim() || accountDraft.value.phone.trim();
  });

  const bindPlanCopy = computed(() =>
    profileDraft.value.bindPlan === "now"
      ? "当前只记录“需要尽快绑定设备”的引导意图，真实绑定仍由社区端成员与设备页完成。"
      : "当前选择稍后绑定，注册完成后可继续由社区端补齐设备归属流程。",
  );

  const profileSummary = computed(() => {
    if (selectedRole.value === "elder") {
      return [
        `房间号：${profileDraft.value.apartment || "未填写"}`,
        `年龄：${profileDraft.value.age || "未填写"}`,
        `设备计划：${profileDraft.value.bindPlan === "now" ? "尽快绑定设备" : "稍后绑定设备"}`,
      ];
    }
    if (selectedRole.value === "family") {
      return [
        `关系类型：${profileDraft.value.relationship}`,
        `首屏优先查看：${profileDraft.value.landingChoice === "report" ? "健康报告" : profileDraft.value.landingChoice === "alarm" ? "异常提醒" : "当前状态概览"}`,
        `设备计划：${profileDraft.value.bindPlan === "now" ? "尽快绑定设备" : "稍后绑定设备"}`,
      ];
    }
    return [
      `值守班次：${profileDraft.value.shift === "day" ? "日间值守" : profileDraft.value.shift === "night" ? "夜间值守" : "灵活值守"}`,
      `值守站点：${profileDraft.value.stationLabel || "未填写"}`,
      `首屏偏好：${profileDraft.value.landingChoice === "alarm" ? "异常提醒" : profileDraft.value.landingChoice === "report" ? "结构化报告" : "社区总览"}`,
    ];
  });

  function resetRegistrationState() {
    registrationError.value = "";
    registrationSuccess.value = "";
    completedCredentials.value = null;
  }

  function resetAccountDraft() {
    accountDraft.value = {
      name: "",
      phone: "",
      password: "123456",
      confirmPassword: "123456",
      loginUsername: "",
    };
  }

  function resetProfileDraft() {
    profileDraft.value = {
      age: "78",
      apartment: "",
      relationship: "daughter",
      bindPlan: "later",
      landingChoice: "report",
      shift: "day",
      stationLabel: "海棠苑社区值守台",
    };
  }

  function goToLogin() {
    currentStep.value = "login";
    showHelp.value = false;
    registrationError.value = "";
  }

  function openRoleSelect(initialRole?: AuthFlowRole) {
    if (initialRole) selectedRole.value = initialRole;
    resetRegistrationState();
    currentStep.value = "role-select";
  }

  function selectRole(role: AuthFlowRole) {
    selectedRole.value = role;
    registrationError.value = "";
  }

  function goToRegisterAccount() {
    registrationError.value = "";
    currentStep.value = "register-account";
  }

  function validateAccountDraft() {
    if (!accountDraft.value.name.trim() || !accountDraft.value.phone.trim()) {
      registrationError.value = "请先完整填写姓名和手机号。";
      return false;
    }
    if (!accountDraft.value.password.trim()) {
      registrationError.value = "请输入密码。";
      return false;
    }
    if (accountDraft.value.password !== accountDraft.value.confirmPassword) {
      registrationError.value = "两次输入的密码不一致，请重新确认。";
      return false;
    }
    registrationError.value = "";
    return true;
  }

  function goToRegisterProfile() {
    if (!validateAccountDraft()) return false;
    currentStep.value = "register-profile";
    return true;
  }

  function goBack(step: AuthFlowStep) {
    registrationError.value = "";
    currentStep.value = step;
  }

  async function submitRegistration() {
    registrationError.value = "";
    registrationSuccess.value = "";

    if (selectedRole.value === "elder" && !profileDraft.value.apartment.trim()) {
      registrationError.value = "请补充老人房间号后再完成注册。";
      return false;
    }
    if (selectedRole.value === "family" && !profileDraft.value.relationship.trim()) {
      registrationError.value = "请先选择家属关系类型。";
      return false;
    }
    if (selectedRole.value === "community" && !profileDraft.value.stationLabel.trim()) {
      registrationError.value = "请先填写值守站点或岗位说明。";
      return false;
    }

    registrationSubmitting.value = true;
    try {
      if (selectedRole.value === "elder") {
        await api.publicRegisterElder({
          name: accountDraft.value.name.trim(),
          phone: accountDraft.value.phone.trim(),
          password: accountDraft.value.password,
          age: Number(profileDraft.value.age) || 78,
          apartment: profileDraft.value.apartment.trim(),
          community_id: "community-haitang",
        });
        completedCredentials.value = {
          username: accountDraft.value.phone.trim(),
          password: accountDraft.value.password,
          role: selectedRole.value,
        };
        registrationSuccess.value = "老人账号已创建完成。回到登录页后，系统会自动回填手机号和密码。";
      } else if (selectedRole.value === "family") {
        await api.publicRegisterFamily({
          name: accountDraft.value.name.trim(),
          phone: accountDraft.value.phone.trim(),
          password: accountDraft.value.password,
          relationship: profileDraft.value.relationship,
          community_id: "community-haitang",
          login_username: accountDraft.value.loginUsername.trim() || null,
        });
        completedCredentials.value = {
          username: currentLoginAccount.value,
          password: accountDraft.value.password,
          role: selectedRole.value,
        };
        registrationSuccess.value = "家属账号已创建完成。回到登录页后，系统会自动回填可用账号和密码。";
      } else {
        await api.publicRegisterCommunityStaff({
          name: accountDraft.value.name.trim(),
          phone: accountDraft.value.phone.trim(),
          password: accountDraft.value.password,
          community_id: "community-haitang",
          login_username: accountDraft.value.loginUsername.trim() || null,
        });
        completedCredentials.value = {
          username: currentLoginAccount.value,
          password: accountDraft.value.password,
          role: selectedRole.value,
        };
        registrationSuccess.value = "社区工作人员账号已创建完成。回到登录页后，系统会自动回填可用账号和密码。";
      }

      currentStep.value = "register-complete";
      return true;
    } catch (error) {
      registrationError.value = formatError(error, "注册失败，请稍后重试。");
      return false;
    } finally {
      registrationSubmitting.value = false;
    }
  }

  function consumePrefillPayload() {
    if (!completedCredentials.value) return null;
    const payload = completedCredentials.value;
    prefillNotice.value =
      payload.role === "community"
        ? "社区账号已回填。确认账号无误后，直接点击“登录”即可进入社区总览。"
        : payload.role === "elder"
          ? "老人账号已回填。可先登录验证首登链路，再继续演示后续流程。"
          : "家属账号已回填。确认无误后点击“登录”，即可进入家属端健康主链。";
    currentStep.value = "login";
    return payload;
  }

  function clearPrefillNotice() {
    prefillNotice.value = "";
  }

  function resetRegistrationDrafts() {
    resetRegistrationState();
    resetAccountDraft();
    resetProfileDraft();
    selectedRole.value = "family";
    currentStep.value = "login";
  }

  return {
    currentStep,
    selectedRole,
    showHelp,
    prefillNotice,
    registrationSubmitting,
    registrationError,
    registrationSuccess,
    completedCredentials,
    accountDraft,
    profileDraft,
    authRoleOptions,
    stepItems,
    activeRole,
    currentLoginAccount,
    bindPlanCopy,
    profileSummary,
    goToLogin,
    openRoleSelect,
    selectRole,
    goToRegisterAccount,
    goToRegisterProfile,
    goBack,
    submitRegistration,
    consumePrefillPayload,
    clearPrefillNotice,
    resetRegistrationDrafts,
  };
}
