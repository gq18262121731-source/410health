import { computed, ref, type Ref } from "vue";
import type { SessionUser } from "../api/client";

export type PageKey = "community" | "family" | "relation" | "debug" | "none";

const pageHash: Record<Exclude<PageKey, "none">, string> = {
  community: "#/community",
  family: "#/family",
  relation: "#/relation",
  debug: "#/debug",
};

export function useHashRouting(sessionUser: Ref<SessionUser | null>) {
  const activePage = ref<PageKey>("none");
  const canAccessDebug = computed(
    () => sessionUser.value?.role === "community" || sessionUser.value?.role === "admin",
  );
  const allowedPages = computed<PageKey[]>(() => {
    if (!sessionUser.value) return [];
    if (sessionUser.value.role === "family") return ["family"];
    if (sessionUser.value.role === "community" || sessionUser.value.role === "admin") {
      return ["community", "relation"];
    }
    return [];
  });

  let hashListener: (() => void) | null = null;

  function routeTo(page: PageKey) {
    if (page === "none") return;
    if (page === "debug" && !canAccessDebug.value) return;
    if (page !== "debug" && !allowedPages.value.includes(page)) return;
    activePage.value = page;
    window.location.hash = pageHash[page];
  }

  function initHashRouting() {
    const requested = window.location.hash
      ? (Object.entries(pageHash).find(([, hash]) => hash === window.location.hash)?.[0] as PageKey | undefined)
      : undefined;
    const fallback = sessionUser.value?.role === "family"
      ? "family"
      : sessionUser.value?.role === "community" || sessionUser.value?.role === "admin"
        ? "community"
        : "none";
    const nextPage = requested && (requested === "debug" ? canAccessDebug.value : allowedPages.value.includes(requested))
      ? requested
      : fallback;

    activePage.value = nextPage;
    window.location.hash = nextPage === "none" ? "" : pageHash[nextPage];
    hashListener = () => {
      const found = Object.entries(pageHash).find(([, hash]) => hash === window.location.hash)?.[0] as PageKey | undefined;
      if (!found) return;
      if (found === "debug") {
        if (canAccessDebug.value) activePage.value = found;
        return;
      }
      if (allowedPages.value.includes(found)) activePage.value = found;
    };
    window.addEventListener("hashchange", hashListener);
  }

  function disposeHashRouting() {
    if (hashListener) window.removeEventListener("hashchange", hashListener);
    hashListener = null;
  }

  function resetToDefaultPage() {
    activePage.value = "none";
    window.location.hash = "";
  }

  return {
    activePage,
    allowedPages,
    canAccessDebug,
    disposeHashRouting,
    initHashRouting,
    resetToDefaultPage,
    routeTo,
  };
}
