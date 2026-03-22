from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
APP_VUE = PROJECT_ROOT / "frontend" / "vue-dashboard" / "src" / "App.vue"
PUBLIC_REGISTRATION_PANEL = PROJECT_ROOT / "frontend" / "vue-dashboard" / "src" / "components" / "PublicRegistrationPanel.vue"


def test_app_currently_mounts_dedicated_login_page_view() -> None:
    app_source = APP_VUE.read_text(encoding="utf-8")

    assert 'import LoginPage from "./views/LoginPage.vue";' in app_source
    assert "<LoginPage" in app_source
    assert 'v-if="!isLoggedIn"' in app_source
    assert '@submit-login="void handleLoginSubmit()"' in app_source
    assert ':login-username="loginUsername"' in app_source


def test_public_registration_panel_wires_all_three_public_registration_routes() -> None:
    panel_source = PUBLIC_REGISTRATION_PANEL.read_text(encoding="utf-8")

    assert 'type RegistrationRole = "elder" | "family" | "community"' in panel_source
    assert 'api.publicRegisterElder' in panel_source
    assert 'api.publicRegisterFamily' in panel_source
    assert 'api.publicRegisterCommunityStaff' in panel_source


def test_public_registration_panel_preserves_role_branching_and_login_prefill_flow() -> None:
    panel_source = PUBLIC_REGISTRATION_PANEL.read_text(encoding="utf-8")

    assert 'registrationStep = ref<RegistrationStep>(1)' in panel_source
    assert 'registrationStep.value = 3' in panel_source
    assert 'emit("prefillLogin"' in panel_source
    assert 'function switchRole(role: RegistrationRole)' in panel_source
    assert '@click="switchRole(role.key)"' in panel_source
    assert 'const registrationRoleOptions = [' in panel_source


def test_public_registration_panel_still_supports_login_prefill_after_success() -> None:
    panel_source = PUBLIC_REGISTRATION_PANEL.read_text(encoding="utf-8")

    assert 'emit("prefillLogin"' in panel_source
    assert 'registrationStep.value = 3' in panel_source


def test_public_registration_panel_keeps_bind_now_vs_later_affordance_honest() -> None:
    panel_source = PUBLIC_REGISTRATION_PANEL.read_text(encoding="utf-8")

    assert 'profileForm.value.bindPlan === "now"' in panel_source or "profileForm.bindPlan === 'now'" in panel_source
    assert "profileForm.bindPlan === 'later'" in panel_source
    assert 'data-testid="registration-bind-later"' in panel_source
    assert 'data-testid="registration-bind-now"' in panel_source
