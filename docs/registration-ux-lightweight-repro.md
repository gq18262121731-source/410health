# Registration UX Lightweight Repro

Last updated: 2026-03-22
Related task: `TE-006`

## Scope

This repro covers the current browser-visible login and public registration chain.

Primary verification sources:

- browser runtime at `http://127.0.0.1:5173/`
- frontend wiring regression in `tests/test_frontend_registration_flow_contract.py`
- public registration API regression in `tests/test_care_auth_api.py`

Browser artifacts produced in this round:

- `tests/artifacts/te006-browser/te006-login-page-1600x900.png`
- `tests/artifacts/te006-browser/te006-registration-panel-1600x900.png`
- `tests/artifacts/te006-browser/te006-elder-profile-1600x900.png`
- `tests/artifacts/te006-browser/te006-elder-complete-1600x900.png`
- `tests/artifacts/te006-browser/te006-family-profile-1600x900.png`
- `tests/artifacts/te006-browser/te006-family-complete-1600x900.png`
- `tests/artifacts/te006-browser/te006-community-profile-1600x900.png`
- `tests/artifacts/te006-browser/te006-community-complete-1600x900.png`
- `tests/artifacts/te006-browser/te006-browser-report.json`

Screenshot standard used:

- desktop ratio `16:9`
- size `1600x900`
- browser zoom `100%`

## Preconditions

1. Start backend and frontend locally.
2. Open the unauthenticated login page in a real browser.
3. Ensure public registration APIs are reachable.

## Browser Verification Summary

### 1. Login page exposes registration entry

Observed in browser:

- Login page title: `智慧养老系统登录与注册`
- Visible registration CTA: `立即注册并完成资料引导`
- Supporting copy explicitly says registration is part of the main flow.

Result:

- Pass.

### 2. Registration entry opens the role-selection step

Observed in browser after clicking the registration CTA:

- The page enters a dedicated registration panel.
- Step sequence is visible:
  - identity selection
  - account registration
  - profile completion
  - completion and login prefill
- Visible role options:
  - 老人
  - 家属
  - 社区工作人员

Result:

- Pass.

### 3. Elder public registration flow

Observed in browser:

1. Select `老人`
2. Enter account fields
3. Enter profile fields:
   - 房间号
   - 年龄
   - 绑定计划
4. Submit registration
5. Completion state appears
6. Return to login with auto-prefill

Observed result:

- Browser login field was prefilled with the elder phone number.
- Password field was prefilled.
- Completion text remained coherent in browser.

Result:

- Pass.

### 4. Family public registration flow

Observed in browser:

1. Select `家属`
2. Enter account fields including custom login username
3. Enter profile fields:
   - relationship
   - preferred landing choice
   - binding plan
4. Submit registration
5. Completion state appears
6. Return to login with auto-prefill

Observed result:

- Browser login field was prefilled with the custom family login username.
- Password field was prefilled.
- Completion state stayed readable and coherent.

Result:

- Pass.

### 5. Community-staff public registration flow

Observed in browser:

1. Select `社区工作人员`
2. Enter account fields including custom login username
3. Enter profile fields:
   - shift
   - station label
   - preferred landing choice
4. Submit registration
5. Completion state appears
6. Return to login with auto-prefill

Observed result:

- Browser login field was prefilled with the custom community login username.
- Password field was prefilled.
- Completion state stayed readable and coherent.

Result:

- Pass.

### 6. Bind-now / bind-later wording

Observed in browser:

- Elder and family flows both expose bind-planning choices.
- Wording stays honest:
  - the UI records intent
  - it does not claim that self-service device binding is already completed

Result:

- Pass.

## Important Runtime Note

Browser validation also surfaced a separate runtime warning cluster unrelated to `TE-006` itself:

- Vue console warnings repeatedly report unresolved components such as:
  - `TrendChart`
  - `CommunityAssistantPanel`
  - `HealthEvaluationPanel`
  - `AlarmEscalationPanel`
  - `AssistantPanel`

These warnings did not block the login/registration chain in this round, but they should be treated as frontend follow-up risk.

## Conclusion

- Login page registration entry is present in the real browser.
- Elder, family, and community-staff all have working public registration paths.
- Completion and login auto-prefill behavior work in the real browser.
- Browser-visible Chinese copy in this chain is readable.
- `TE-006` is satisfied by browser verification plus regression coverage.
