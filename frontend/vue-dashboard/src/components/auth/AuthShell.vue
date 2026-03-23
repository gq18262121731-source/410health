<template>
  <section class="login-shell login-shell--immersive">
    <div class="login-background" aria-hidden="true">
      <div class="login-background-photo"></div>
      <div class="login-background-overlay"></div>
      <div class="login-background-scan"></div>
      <svg class="login-ecg-layer login-ecg-layer--primary" viewBox="0 0 1600 900" preserveAspectRatio="none">
        <defs>
          <filter id="loginEcgGlowPrimary" x="-20%" y="-60%" width="140%" height="220%">
            <feGaussianBlur stdDeviation="4.5" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>
        <path
          class="login-ecg-base"
          d="M-80 594H238L272 594L304 574L332 646L366 498L402 594H876L910 594L942 576L970 632L1004 520L1038 594H1680"
        />
        <path
          class="login-ecg-highlight"
          d="M-80 594H238L272 594L304 574L332 646L366 498L402 594H876L910 594L942 576L970 632L1004 520L1038 594H1680"
          filter="url(#loginEcgGlowPrimary)"
        />
      </svg>
    </div>

    <div class="login-content-shell">
      <div class="auth-shell-layout auth-shell-layout--centered">
        <header v-if="$slots.hero" class="auth-shell-hero auth-shell-hero--centered">
          <slot name="hero" />
        </header>
        <div class="auth-shell-content auth-shell-content--centered">
          <slot />
        </div>
      </div>
    </div>
  </section>
</template>
